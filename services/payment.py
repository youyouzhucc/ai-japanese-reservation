"""支付服务 - 支持模拟模式、支付宝当面付"""
from config import settings


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
