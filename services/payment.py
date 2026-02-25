"""支付服务 - 支持模拟模式"""
from config import settings


async def create_payment(order_no: str, amount_cents: int) -> dict:
    """
    创建支付，返回 payment_id
    模拟模式：直接返回成功
    """
    if settings.payment_mode == "mock":
        return {
            "success": True,
            "payment_id": f"mock_pay_{order_no}_{amount_cents}",
            "message": "模拟支付成功",
        }
    # 可扩展 Stripe / 支付宝 / 微信支付
    return {
        "success": False,
        "payment_id": "",
        "message": "未配置支付",
    }
