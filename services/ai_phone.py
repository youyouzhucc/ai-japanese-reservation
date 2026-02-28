"""
AI 电话服务 - 拨打餐厅进行日语预约
支持：模拟模式（本地测试）、Vapi.ai（AI 电话一站式）、Twilio + OpenAI Realtime
"""
import asyncio
import logging
from datetime import datetime

import httpx

from config import settings

log = logging.getLogger(__name__)


def _build_system_prompt(restaurant_name: str, guest_name: str, guest_phone: str,
                         reservation_datetime: datetime, adults: int, children: int, notes: str) -> str:
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
1. 電話が取れたら「こんにちは、予約をお願いしたいのですが。」と挨拶する
2. 上記の希望日時・人数・お客様名・連絡先を伝える
3. 店員の確認や質問に応答する
4. 予約が確定したら「ありがとうございます。よろしくお願いいたします。」と締めくくる

短く、簡潔に話してください。店員が話している間は遮らず、聞き取ってから応答してください。"""


async def initiate_call(order_no: str, restaurant_phone: str, restaurant_name: str,
                        guest_name: str, guest_phone: str, reservation_datetime: datetime,
                        adults: int, children: int, notes: str) -> dict:
    prompt = _build_system_prompt(
        restaurant_name, guest_name, guest_phone,
        reservation_datetime, adults, children, notes
    )

    if settings.vapi_api_key:
        return await _vapi_call(restaurant_phone, prompt, order_no)
    elif settings.twilio_account_sid and settings.twilio_auth_token:
        return await _twilio_call(restaurant_phone, prompt, order_no)
    else:
        return await _simulate_call(order_no, restaurant_phone, prompt)


async def _simulate_call(order_no: str, restaurant_phone: str, script: str) -> dict:
    await asyncio.sleep(5)
    return {"call_sid": f"sim_{order_no}", "status": "simulated", "script": script.strip()}


async def _vapi_call(restaurant_phone: str, system_prompt: str, order_no: str) -> dict:
    """通过 Vapi.ai 发起 AI 电话"""
    try:
        base_url = (settings.app_base_url or "").strip().rstrip("/")
        server_url = f"{base_url}/api/vapi/webhook" if base_url else None

        payload = {
            "assistant": {
                "firstMessage": "こんにちは、予約をお願いしたいのですが。",
                "model": {
                    "provider": "openai",
                    "model": "gpt-4o",
                    "messages": [{"role": "system", "content": system_prompt}],
                },
                "transcriber": {
                    "provider": "deepgram",
                    "language": "ja",
                    "model": "nova-2",
                },
                "voice": {
                    "provider": "openai",
                    "voiceId": "alloy",
                },
                "endCallMessage": "ありがとうございます。失礼いたします。",
                "maxDurationSeconds": 300,
                "metadata": {"order_no": order_no},
            },
            "customer": {"number": restaurant_phone},
        }

        if settings.vapi_phone_number_id:
            payload["phoneNumberId"] = settings.vapi_phone_number_id

        if server_url:
            payload["assistant"]["serverUrl"] = server_url

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://api.vapi.ai/call/phone",
                headers={
                    "Authorization": f"Bearer {settings.vapi_api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )

        if resp.status_code == 201:
            data = resp.json()
            call_id = data.get("id", "")
            log.info("[Vapi] 电话已发起: call_id=%s, order_no=%s", call_id, order_no)
            return {"call_sid": call_id, "status": "initiated"}
        else:
            error_msg = resp.text[:500]
            log.error("[Vapi] 发起电话失败: status=%s, body=%s", resp.status_code, error_msg)
            return {"call_sid": "", "status": "error", "error": f"Vapi API {resp.status_code}: {error_msg}"}
    except Exception as e:
        log.exception("[Vapi] 发起电话异常")
        return {"call_sid": "", "status": "error", "error": str(e)}


async def _twilio_call(restaurant_phone: str, script: str, order_no: str) -> dict:
    try:
        from twilio.rest import Client
        base = (settings.app_base_url or "").strip().rstrip("/")
        if not base:
            return {"call_sid": "", "status": "error", "error": "未配置 APP_BASE_URL"}
        client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
        call = client.calls.create(
            to=restaurant_phone,
            from_=settings.twilio_phone_number,
            url=f"{base}/api/twiml/{order_no}",
            status_callback=f"{base}/api/twilio/status",
            status_callback_event=["initiated", "ringing", "answered", "completed"],
        )
        return {"call_sid": call.sid, "status": "initiated"}
    except Exception as e:
        return {"call_sid": "", "status": "error", "error": str(e)}
