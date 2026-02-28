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
    dt_str = reservation_datetime.strftime("%Y年%m月%d日 %H:%M")
    people = f"{adults}位大人" + (f"、{children}位小孩" if children > 0 else "")
    return f"""你是一个餐厅电话预约代行助手。请全程使用中文与对方对话，语气礼貌、自然。

【预约信息】
- 餐厅: {restaurant_name}
- 预约时间: {dt_str}
- 人数: {people}
- 预约人: {guest_name}
- 联系电话: {guest_phone}
{f'- 备注: {notes}' if notes else ''}

【对话流程】
1. 对方接听后说"您好，我想预约一下餐位"
2. 告诉对方预约时间、人数、预约人姓名和联系电话
3. 回答对方的确认问题
4. 预约确认后说"好的，谢谢，到时候见"

说话简短、清晰。对方说话时不要打断，听完再回答。"""


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
                "firstMessage": "您好，我想预约一下餐位。",
                "model": {
                    "provider": "openai",
                    "model": "gpt-4o",
                    "messages": [{"role": "system", "content": system_prompt}],
                },
                "transcriber": {
                    "provider": "deepgram",
                    "language": "zh-CN",
                    "model": "nova-2",
                },
                "voice": {
                    "provider": "openai",
                    "voiceId": "alloy",
                },
                "endCallMessage": "好的，谢谢，再见。",
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
