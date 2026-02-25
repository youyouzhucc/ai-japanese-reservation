"""短信通知服务"""
from datetime import datetime
from config import settings


async def send_reservation_sms(phone: str, order_no: str, success: bool,
                               restaurant_name: str, reservation_datetime: datetime) -> bool:
    """
    发送预约结果短信
    success: True=预约成功, False=预约失败
    """
    dt_str = reservation_datetime.strftime("%Y-%m-%d %H:%M")
    if success:
        content = f"【AI预约】您的预约已成功！餐厅：{restaurant_name}，时间：{dt_str}。订单号：{order_no}"
    else:
        content = f"【AI预约】抱歉，预约未成功。餐厅：{restaurant_name}，时间：{dt_str}。订单号：{order_no}，请稍后重试或致电餐厅。"

    if settings.twilio_account_sid and settings.twilio_auth_token:
        return await _twilio_sms(phone, content)
    if settings.aliyun_access_key and settings.aliyun_access_secret:
        return await _aliyun_sms(phone, content, success)
    # 模拟模式
    print(f"[模拟短信] 发送至 {phone}: {content}")
    return True


async def _twilio_sms(phone: str, content: str) -> bool:
    """Twilio 短信"""
    try:
        try:
            from twilio.rest import Client
        except ImportError:
            print("twilio 未安装")
            return False
        client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
        client.messages.create(
            body=content,
            from_=settings.twilio_phone_number,
            to=phone,
        )
        return True
    except Exception as e:
        print(f"Twilio SMS error: {e}")
        return False


async def _aliyun_sms(phone: str, content: str, success: bool) -> bool:
    """阿里云短信"""
    try:
        try:
            from alibabacloud_dysmsapi20170525.client import Client as DysmsClient
        except ImportError:
            print("阿里云短信 SDK 未安装")
            return False
        from alibabacloud_dysmsapi20170525 import models
        from alibabacloud_tea_openapi import models as open_models
        from alibabacloud_dysmsapi20170525 import models as sms_models

        config = open_models.Config(
            access_key_id=settings.aliyun_access_key,
            access_key_secret=settings.aliyun_access_secret,
            endpoint="dysmsapi.aliyuncs.com",
        )
        client = DysmsClient(config)
        req = sms_models.SendSmsRequest(
            phone_numbers=phone,
            sign_name=settings.aliyun_sms_sign_name,
            template_code=settings.aliyun_sms_template_code,
            template_param={"content": content, "status": "成功" if success else "失败"},
        )
        resp = client.send_sms(req)
        return resp.body.code == "OK"
    except Exception as e:
        print(f"Aliyun SMS error: {e}")
        return False
