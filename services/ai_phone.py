"""
AI 电话服务 - 拨打餐厅进行日语预约
支持：模拟模式（本地测试）、Twilio + 语音 AI
"""
import asyncio
from datetime import datetime
from config import settings


def _build_japanese_script(restaurant_name: str, guest_name: str, guest_phone: str,
                           reservation_datetime: datetime, adults: int, children: int, notes: str) -> str:
    """生成 AI 日语预约话术"""
    dt_str = reservation_datetime.strftime("%Y年%m月%d日 %H時%M分")
    people = f"{adults}名" + (f"、お子様{children}名" if children > 0 else "")
    return f"""
【AI 预约话术 - 日语】
こんにちは、{restaurant_name}でございますか。
こちらは予約代行サービスです。
{dt_str}に、{people}でご予約をお願いいたします。
お客様名：{guest_name}
連絡先：{guest_phone}
{f'備考：{notes}' if notes else ''}
よろしくお願いいたします。
"""


async def initiate_call(order_no: str, restaurant_phone: str, restaurant_name: str,
                        guest_name: str, guest_phone: str, reservation_datetime: datetime,
                        adults: int, children: int, notes: str) -> dict:
    """
    发起 AI 电话
    返回: {"call_sid": "...", "status": "initiated"|"simulated"}
    """
    script = _build_japanese_script(
        restaurant_name, guest_name, guest_phone,
        reservation_datetime, adults, children, notes
    )

    if settings.twilio_account_sid and settings.twilio_auth_token:
        # 真实 Twilio 通话（需配置 TwiML / 语音 AI 端点）
        return await _twilio_call(restaurant_phone, script, order_no)
    else:
        # 模拟模式：延迟后返回"成功"
        return await _simulate_call(order_no, restaurant_phone, script)


async def _simulate_call(order_no: str, restaurant_phone: str, script: str) -> dict:
    """模拟通话 - 5秒后返回成功"""
    await asyncio.sleep(5)
    return {
        "call_sid": f"sim_{order_no}",
        "status": "simulated",
        "script": script.strip(),
    }


async def _twilio_call(restaurant_phone: str, script: str, order_no: str) -> dict:
    """Twilio 真实通话（需配置 TwiML 服务器）"""
    try:
        try:
            from twilio.rest import Client
        except ImportError:
            return {"call_sid": "", "status": "error", "error": "twilio 未安装，请 pip install twilio"}
        client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
        call = client.calls.create(
            to=restaurant_phone,
            from_=settings.twilio_phone_number,
            url=f"https://your-server.com/twiml/{order_no}",  # 需部署 TwiML 端点
        )
        return {"call_sid": call.sid, "status": "initiated"}
    except Exception as e:
        return {"call_sid": "", "status": "error", "error": str(e)}
