"""
Twilio Media Stream <-> OpenAI Realtime API 桥接
支付成功后，Twilio 拨打餐厅电话，接通后通过 WebSocket 将音频流转发给 OpenAI，
AI 用日语与店员对话完成预约。
"""
import asyncio
import json
import logging
from datetime import datetime

import websockets

from config import settings

log = logging.getLogger(__name__)

# OpenAI Realtime 使用 g711 ulaw (pcmu)，与 Twilio Media Stream 格式一致，无需转换
OPENAI_REALTIME_URL = "wss://api.openai.com/v1/realtime?model=gpt-realtime"
VOICE = "alloy"  # alloy, ash, ballad, coral, echo, sage, shimmer, verse 等


def _build_system_prompt(
    restaurant_name: str,
    guest_name: str,
    guest_phone: str,
    reservation_datetime: datetime,
    adults: int,
    children: int,
    notes: str,
) -> str:
    """生成 AI 日语预约系统提示词"""
    dt_str = reservation_datetime.strftime("%Y年%m月%d日 %H時%M分")
    people = f"{adults}名" + (f"、お子様{children}名" if children > 0 else "")
    return f"""あなたは日本のレストランへの電話予約代行アシスタントです。
必ず日本語で話してください。丁寧で自然な敬語を使い、店員と会話して予約を完了させてください。

【予約情報】
- 店名: {restaurant_name}
- 予約希望日時: {dt_str}
- 人数: {people}
- お客様名: {guest_name}
- 連絡先: {guest_phone}
{f'- 備考: {notes}' if notes else ''}

【手順】
1. 電話が取れたら「こんにちは、{restaurant_name}でございますか。予約代行サービスです。」と挨拶する
2. 上記の希望日時・人数・お客様名・連絡先を伝える
3. 店員の確認や質問に応答する
4. 予約が確定したら「ありがとうございます。よろしくお願いいたします。」と締めくくる

短く、簡潔に話してください。店員が話している間は遮らず、聞き取ってから応答してください。"""


async def handle_media_stream(websocket, order_no: str, get_reservation_fn):
    """
    处理 Twilio Media Stream WebSocket，连接 OpenAI Realtime API
    get_reservation_fn: 异步函数，接收 order_no，返回 Reservation 或 None
    """
    await websocket.accept()
    stream_sid = None

    # 获取预约信息
    reservation = await get_reservation_fn(order_no)
    if not reservation:
        log.warning("[AI] 未找到预约 order_no=%s", order_no)
        await websocket.close()
        return

    system_prompt = _build_system_prompt(
        restaurant_name=reservation.restaurant_name,
        guest_name=reservation.guest_name,
        guest_phone=reservation.guest_phone,
        reservation_datetime=reservation.reservation_datetime,
        adults=reservation.adults,
        children=reservation.children,
        notes=reservation.notes or "",
    )

    if not settings.openai_api_key:
        log.error("[AI] 未配置 OPENAI_API_KEY，无法连接 Realtime API")
        await websocket.close()
        return

    try:
        async with websockets.connect(
            OPENAI_REALTIME_URL,
            additional_headers={
                "Authorization": f"Bearer {settings.openai_api_key}",
                "OpenAI-Beta": "realtime=v1",
            },
            ping_interval=20,
            ping_timeout=10,
        ) as openai_ws:
            # 发送 session 配置（audio/pcmu = g711 ulaw，与 Twilio 一致）
            session_update = {
                "type": "session.update",
                "session": {
                    "modalities": ["text", "audio"],
                    "instructions": system_prompt,
                    "output_modalities": ["audio"],
                    "audio": {
                        "input": {
                            "format": {"type": "audio/pcmu"},
                            "turn_detection": {"type": "server_vad"},
                        },
                        "output": {
                            "format": {"type": "audio/pcmu"},
                            "voice": VOICE,
                        },
                    },
                },
            }
            await openai_ws.send(json.dumps(session_update))
            log.info("[AI] 已发送 session.update: order_no=%s", order_no)

            async def receive_from_twilio():
                nonlocal stream_sid
                try:
                    async for message in websocket.iter_text():
                        data = json.loads(message)
                        if data.get("event") == "start":
                            stream_sid = data.get("start", {}).get("streamSid")
                            log.info("[AI] Twilio stream started: %s", stream_sid)
                        elif data.get("event") == "media" and stream_sid:
                            payload = data.get("media", {}).get("payload")
                            if payload:
                                await openai_ws.send(
                                    json.dumps({
                                        "type": "input_audio_buffer.append",
                                        "audio": payload,
                                    })
                                )
                        elif data.get("event") == "stop":
                            log.info("[AI] Twilio stream stopped")
                except Exception as e:
                    log.warning("[AI] receive_from_twilio: %s", e)

            async def send_to_twilio():
                nonlocal stream_sid
                try:
                    async for msg in openai_ws:
                        try:
                            response = json.loads(msg)
                        except json.JSONDecodeError:
                            continue
                        if response.get("type") == "response.output_audio.delta" and response.get("delta"):
                            if stream_sid:
                                audio_delta = {
                                    "event": "media",
                                    "streamSid": stream_sid,
                                    "media": {"payload": response["delta"]},
                                }
                                await websocket.send_json(audio_delta)
                        elif response.get("type") == "response.audio.delta" and response.get("delta"):
                            # 兼容旧版 API 事件名
                            if stream_sid:
                                audio_delta = {
                                    "event": "media",
                                    "streamSid": stream_sid,
                                    "media": {"payload": response["delta"]},
                                }
                                await websocket.send_json(audio_delta)
                        elif response.get("type") in ("response.done", "error"):
                            log.info("[AI] OpenAI event: %s", response.get("type"))
                except Exception as e:
                    log.warning("[AI] send_to_twilio: %s", e)

            await asyncio.gather(receive_from_twilio(), send_to_twilio())
    except Exception as e:
        log.exception("[AI] Media stream error: %s", e)
    finally:
        try:
            await websocket.close()
        except Exception:
            pass
