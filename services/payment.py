"""支付服务 - 支持模拟模式、支付宝当面付、易付通 V2"""
import time
from urllib.parse import urlencode

from config import settings


def _normalize_pem_key(key: str) -> bytes:
    """规范化 PEM 密钥：处理环境变量中的 \\n 字面量、多余空格等"""
    if not key:
        return b""
    s = key.strip()
    if isinstance(s, str):
        # 环境变量中常将换行存为字面量 \n，需转为真实换行
        s = s.replace("\\n", "\n").replace("\\r", "")
    if not s.endswith("\n"):
        s += "\n"
    return s.encode("utf-8") if isinstance(s, str) else s


def _qiufk_load_private_key(private_key: str):
    """加载商户私钥，支持 PKCS#1/PKCS#8 及环境变量中的 \\n 字面量"""
    import base64
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.hazmat.backends import default_backend
    key_bytes = _normalize_pem_key(private_key)
    try:
        return serialization.load_pem_private_key(
            key_bytes,
            password=None,
            backend=default_backend(),
        )
    except Exception as e:
        # 尝试 PKCS#8 格式（部分平台可能导出 PKCS#8 但带 RSA 头）
        if b"BEGIN RSA PRIVATE KEY" in key_bytes or b"BEGIN PRIVATE KEY" in key_bytes:
            raise ValueError(
                f"私钥格式错误: {e}. "
                "请检查 Railway 变量 QIUFK_PRIVATE_KEY：1) 完整 PEM 含 BEGIN/END 行；"
                "2) 多行时用 \\n 或直接换行；3) 确认是易付通商户后台生成的 RSA 私钥"
            ) from e
        raise


def _qiufk_sign(params: dict, private_key: str) -> str:
    """易付通 RSA 签名：参数按 ASCII 排序，排除 sign，空值不参与，SHA256WithRSA + Base64"""
    filtered = {k: v for k, v in params.items() if v is not None and v != "" and k != "sign"}
    sign_str = "&".join(f"{k}={v}" for k, v in sorted(filtered.items()))
    import base64
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding
    key = _qiufk_load_private_key(private_key)
    sig = key.sign(sign_str.encode("utf-8"), padding.PKCS1v15(), hashes.SHA256())
    return base64.b64encode(sig).decode()


def _qiufk_verify(data: dict, sign: str, public_key: str) -> bool:
    """易付通验签：验证平台返回/异步通知的签名"""
    filtered = {k: v for k, v in data.items() if v is not None and v != "" and k not in ("sign", "sign_type")}
    sign_str = "&".join(f"{k}={v}" for k, v in sorted(filtered.items()))
    import base64
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.hazmat.backends import default_backend
    key_bytes = _normalize_pem_key(public_key)
    key = serialization.load_pem_public_key(
        key_bytes,
        backend=default_backend(),
    )
    try:
        key.verify(base64.b64decode(sign), sign_str.encode("utf-8"), padding.PKCS1v15(), hashes.SHA256())
        return True
    except Exception:
        return False


def _get_alipay_client():
    """获取支付宝客户端"""
    from alipay import AliPay
    from alipay.utils import AliPayConfig
    return AliPay(
        appid=settings.alipay_app_id,
        app_notify_url=settings.alipay_notify_url or None,
        app_private_key_string=settings.alipay_private_key,
        alipay_public_key_string=settings.alipay_public_key,
        sign_type="RSA2",
        debug=settings.alipay_sandbox,
        config=AliPayConfig(timeout=15),
    )


async def create_payment(order_no: str, amount_cents: int, subject: str = "AI日语预约") -> dict:
    """
    创建支付，返回 payment_id 或 qr_code
    当面付：返回 qr_code 供用户扫码
    """
    if settings.payment_mode == "mock":
        return {
            "success": True,
            "payment_id": f"mock_pay_{order_no}_{amount_cents}",
            "qr_code": "",
            "message": "模拟支付成功",
        }
    if settings.payment_mode == "alipay" and settings.alipay_app_id and settings.alipay_private_key:
        try:
            alipay = _get_alipay_client()
            # 当面付金额单位：元
            total_amount = str(round(amount_cents / 100, 2))
            result = alipay.api_alipay_trade_precreate(
                subject=subject,
                out_trade_no=order_no,
                total_amount=total_amount,
                notify_url=settings.alipay_notify_url or None,
            )
            if result.get("code") == "10000":
                return {
                    "success": True,
                    "payment_id": result.get("trade_no", order_no),
                    "qr_code": result.get("qr_code", ""),
                    "message": "支付订单已创建",
                }
            return {
                "success": False,
                "payment_id": "",
                "qr_code": "",
                "message": result.get("msg", "支付宝接口调用失败"),
            }
        except Exception as e:
            return {
                "success": False,
                "payment_id": "",
                "qr_code": "",
                "message": str(e),
            }
    if settings.payment_mode == "qiufk_v2" and settings.qiufk_pid and settings.qiufk_private_key and settings.qiufk_public_key and settings.qiufk_api_url and settings.qiufk_notify_url:
        try:
            import httpx
            ts = str(int(time.time()))
            money = str(round(amount_cents / 100, 2))
            base_url = settings.qiufk_api_url.rstrip("/")
            return_url = settings.qiufk_notify_url.replace("/api/qiufk/notify", "/").rstrip("/") + "/" or (base_url + "/")
            params = {
                "pid": settings.qiufk_pid,
                "method": "web",
                "device": "pc",
                "type": "alipay",
                "out_trade_no": order_no,
                "notify_url": settings.qiufk_notify_url,
                "return_url": return_url,
                "name": (subject or "AI日语预约")[:127],
                "money": money,
                "clientip": "127.0.0.1",
                "timestamp": ts,
                "sign_type": "RSA",
            }
            params["sign"] = _qiufk_sign(params, settings.qiufk_private_key)
            url = f"{base_url}/api/pay/create"
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(url, data=params, headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"})
            data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
            if data.get("code") == 0:
                pay_info = data.get("pay_info", "")
                pay_type = data.get("pay_type", "")
                trade_no = data.get("trade_no", order_no)
                # qrcode=二维码内容; jump=跳转URL，也可生成二维码供扫码
                qr_code = pay_info if pay_type in ("qrcode", "jump") and pay_info else ""
                return {
                    "success": True,
                    "payment_id": trade_no,
                    "qr_code": qr_code,
                    "message": "支付订单已创建",
                }
            return {
                "success": False,
                "payment_id": "",
                "qr_code": "",
                "message": data.get("msg", "易付通接口调用失败"),
            }
        except Exception as e:
            return {
                "success": False,
                "payment_id": "",
                "qr_code": "",
                "message": str(e),
            }
    return {
        "success": False,
        "payment_id": "",
        "qr_code": "",
        "message": "未配置支付",
    }


def verify_alipay_notify(data: dict) -> tuple[bool, str]:
    """
    验证支付宝异步通知签名
    返回 (是否验证通过, out_trade_no)
    """
    if not settings.alipay_app_id or not settings.alipay_public_key:
        return False, ""
    try:
        from alipay import AliPay
        from alipay.utils import AliPayConfig
        alipay = AliPay(
            appid=settings.alipay_app_id,
            app_notify_url=None,
            app_private_key_string=settings.alipay_private_key,
            alipay_public_key_string=settings.alipay_public_key,
            sign_type="RSA2",
            debug=settings.alipay_sandbox,
            config=AliPayConfig(timeout=15),
        )
        signature = data.pop("sign", None)
        data.pop("sign_type", None)  # 验签时需排除
        if not signature:
            return False, ""
        success = alipay.verify(data, signature)
        out_trade_no = data.get("out_trade_no", "")
        trade_status = data.get("trade_status", "")
        if success and trade_status in ("TRADE_SUCCESS", "TRADE_FINISHED"):
            return True, out_trade_no
        return False, out_trade_no
    except Exception:
        return False, ""


def verify_qiufk_notify(data: dict) -> tuple[bool, str]:
    """
    验证易付通异步通知签名
    返回 (是否验证通过, out_trade_no)
    """
    if not settings.qiufk_public_key:
        return False, ""
    sign = data.get("sign")
    if not sign:
        return False, ""
    if data.get("trade_status") != "TRADE_SUCCESS":
        return False, data.get("out_trade_no", "")
    try:
        ok = _qiufk_verify(data, sign, settings.qiufk_public_key)
        return ok, data.get("out_trade_no", "")
    except Exception:
        return False, ""
