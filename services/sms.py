"""短信通知服务"""
import asyncio
import hashlib
import hmac
import base64
import uuid
from datetime import datetime
from urllib.parse import quote, urlencode
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


def _aliyun_rpc_sign(secret: str, method: str, query: str) -> str:
    """阿里云 RPC 签名，使用 UTF-8"""
    string_to_sign = method + "&" + quote("/", safe="") + "&" + quote(query, safe="")
    h = hmac.new((secret + "&").encode("utf-8"), string_to_sign.encode("utf-8"), hashlib.sha1)
    return base64.b64encode(h.digest()).decode("utf-8")


async def _aliyun_dypnsapi_verify_sms(phone: str, code: str) -> bool:
    """阿里云号码认证服务（融合认证套餐包）- 使用 httpx 直接调用，避免 SDK latin-1 编码问题"""
    try:
        import httpx
        from datetime import datetime, timezone

        phone_num = _normalize_phone_aliyun(phone)
        print(f"[阿里云] 发送验证码: phone={phone_num}, sign={settings.aliyun_sms_sign_name}, template={settings.aliyun_sms_verify_template_code}")

        params = {
            "Action": "SendSmsVerifyCode",
            "PhoneNumber": phone_num,
            "SignName": settings.aliyun_sms_sign_name,
            "TemplateCode": settings.aliyun_sms_verify_template_code,
            "TemplateParam": '{"code":"' + code + '","min":"5"}',
            "Format": "JSON",
            "Version": "2017-05-25",
            "AccessKeyId": settings.aliyun_access_key,
            "SignatureMethod": "HMAC-SHA1",
            "SignatureVersion": "1.0",
            "SignatureNonce": str(uuid.uuid4()),
            "Timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        # 按 key 排序后拼接，使用 UTF-8 编码
        sorted_keys = sorted(params.keys())
        query_parts = []
        for k in sorted_keys:
            v = params[k]
            query_parts.append(f"{quote(k, safe='')}={quote(str(v), safe='')}")
        query_str = "&".join(query_parts)
        signature = _aliyun_rpc_sign(settings.aliyun_access_secret, "POST", query_str)
        params["Signature"] = signature

        body_bytes = urlencode(params, encoding="utf-8").encode("utf-8")
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                "https://dypnsapi.aliyuncs.com/",
                content=body_bytes,
                headers={"Content-Type": "application/x-www-form-urlencoded; charset=utf-8"},
            )
        body = resp.json()
        code_val = body.get("Code", body.get("code", ""))
        if code_val != "OK":
            msg = body.get("Message", body.get("message", ""))
            print(f"[阿里云] 发送失败: Code={code_val}, Message={msg}")
            if code_val == "InvalidAccessKeyId":
                ak = settings.aliyun_access_key or ""
                masked = f"{ak[:6]}...{ak[-4:]}" if len(ak) >= 10 else "(过短)"
                print(f"[阿里云] 当前 AccessKey 前6后4: {masked} | 请核对与阿里云控制台是否一致，且为【中国站】账号")
            return False
        print(f"[阿里云] 发送成功: phone={phone_num}")
        return True
    except Exception as e:
        import traceback
        print(f"[阿里云] 异常: {type(e).__name__} | {e}")
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
