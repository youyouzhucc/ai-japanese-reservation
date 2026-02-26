"""短信通知服务"""
import asyncio
from datetime import datetime
from config import settings


def _normalize_phone_aliyun(phone: str) -> str:
    """阿里云国内短信：推荐 11 位无前缀格式"""
    p = phone.strip().replace(" ", "").replace("-", "")
    if p.startswith("+86"):
        p = p[3:].lstrip()
    elif p.startswith("0086"):
        p = p[4:].lstrip()
    elif p.startswith("86") and len(p) > 11:
        p = p[2:].lstrip()
    return p


async def send_verification_code(phone: str, code: str) -> bool:
    """发送验证码短信（登录/注册）"""
    content = f"【AI预约】您的验证码是 {code}，5 分钟内有效，请勿泄露。"
    if settings.twilio_account_sid and settings.twilio_auth_token:
        return await _twilio_sms(phone, content)
    if settings.aliyun_access_key and settings.aliyun_access_secret and getattr(settings, "aliyun_sms_verify_template_code", ""):
        mode = getattr(settings, "aliyun_sms_mode", "").lower()
        if mode == "dypnsapi":
            return await _aliyun_dypnsapi_verify_sms(phone, code)
        return await _aliyun_verify_sms(phone, code)
    # 模拟模式：打印缺失的配置项，便于在 Railway 中排查
    missing = []
    if not settings.aliyun_access_key:
        missing.append("ALIYUN_ACCESS_KEY")
    if not settings.aliyun_access_secret:
        missing.append("ALIYUN_ACCESS_SECRET")
    if not getattr(settings, "aliyun_sms_verify_template_code", ""):
        missing.append("ALIYUN_SMS_VERIFY_TEMPLATE_CODE")
    mode = getattr(settings, "aliyun_sms_mode", "").strip()
    if mode.lower() != "dypnsapi":
        missing.append(f"ALIYUN_SMS_MODE(当前={repr(mode) or '空'},需=dypnsapi)")
    print(f"[模拟短信] 验证码发送至 {phone}: {code} | 缺失: {missing}")
    return True


async def _aliyun_dypnsapi_verify_sms(phone: str, code: str) -> bool:
    """阿里云号码认证服务（融合认证套餐包）- 使用赠送签名/模板"""
    try:
        try:
            from alibabacloud_dypnsapi20170525.client import Client as DypnsClient
        except ImportError:
            print("[阿里云] SDK 未安装: pip install alibabacloud-dypnsapi20170525")
            return False
        from alibabacloud_tea_openapi import models as open_models
        from alibabacloud_dypnsapi20170525 import models as dypns_models

        phone_num = _normalize_phone_aliyun(phone)
        print(f"[阿里云] 发送验证码: phone={phone_num}, sign={settings.aliyun_sms_sign_name}, template={settings.aliyun_sms_verify_template_code}")
        config = open_models.Config(
            access_key_id=settings.aliyun_access_key,
            access_key_secret=settings.aliyun_access_secret,
            endpoint="dypnsapi.aliyuncs.com",
            region_id="cn-hangzhou",
        )
        client = DypnsClient(config)
        req = dypns_models.SendSmsVerifyCodeRequest(
            phone_number=phone_num,
            sign_name=settings.aliyun_sms_sign_name,
            template_code=settings.aliyun_sms_verify_template_code,
            template_param='{"code":"' + code + '","min":"5"}',
        )

        def _send():
            return client.send_sms_verify_code(req)

        resp = await asyncio.to_thread(_send)
        code_val = getattr(resp.body, "code", None) or getattr(resp.body, "Code", None)
        if code_val != "OK":
            msg = getattr(resp.body, "message", "") or getattr(resp.body, "Message", "")
            print(f"[阿里云] 发送失败: Code={code_val}, Message={msg}")
            return False
        print(f"[阿里云] 发送成功: phone={phone_num}")
        return True
    except Exception as e:
        import traceback
        err_msg = str(e)
        err_code = getattr(e, "code", None) or getattr(e, "Code", None)
        err_data = getattr(e, "data", None)
        print(f"[阿里云] 异常: {type(e).__name__} | code={err_code} | message={err_msg}")
        if err_data:
            print(f"[阿里云] data={err_data}")
        traceback.print_exc()
        return False


async def _aliyun_verify_sms(phone: str, code: str) -> bool:
    """阿里云短信服务（Dysmsapi）- 需单独申请签名和模板"""
    try:
        try:
            from alibabacloud_dysmsapi20170525.client import Client as DysmsClient
        except ImportError:
            print("阿里云短信 SDK 未安装，请执行: pip install alibabacloud_dysmsapi20170525")
            return False
        from alibabacloud_tea_openapi import models as open_models
        from alibabacloud_dysmsapi20170525 import models as sms_models

        phone_num = _normalize_phone_aliyun(phone)
        config = open_models.Config(
            access_key_id=settings.aliyun_access_key,
            access_key_secret=settings.aliyun_access_secret,
            endpoint="dysmsapi.aliyuncs.com",
        )
        client = DysmsClient(config)
        req = sms_models.SendSmsRequest(
            phone_numbers=phone_num,
            sign_name=settings.aliyun_sms_sign_name,
            template_code=settings.aliyun_sms_verify_template_code,
            template_param='{"code":"' + code + '"}',
        )
        resp = client.send_sms(req)
        return resp.body.code == "OK"
    except Exception as e:
        print(f"Aliyun verify SMS error: {e}")
        return False


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
            phone_numbers=_normalize_phone_aliyun(phone),
            sign_name=settings.aliyun_sms_sign_name,
            template_code=settings.aliyun_sms_template_code,
            template_param={"content": content, "status": "成功" if success else "失败"},
        )
        resp = client.send_sms(req)
        return resp.body.code == "OK"
    except Exception as e:
        print(f"Aliyun SMS error: {e}")
        return False
