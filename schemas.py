"""API 请求/响应模型"""
from datetime import datetime
from pydantic import BaseModel, Field


class AuthSendCodeRequest(BaseModel):
    """发送验证码"""
    phone: str = Field(..., min_length=8, max_length=50, description="手机号（含区号）")


class AuthVerifyRequest(BaseModel):
    """验证码登录/注册"""
    phone: str = Field(..., min_length=8, max_length=50)
    code: str = Field(..., min_length=4, max_length=8)


class AuthResponse(BaseModel):
    """登录成功响应"""
    token: str
    user_id: int
    phone: str
    nickname: str = ""


class ReservationCreate(BaseModel):
    """创建预约请求"""
    restaurant_name: str = Field(..., min_length=1, max_length=200, description="餐厅名称-必填")
    restaurant_phone: str = Field(..., min_length=1, max_length=50, description="餐厅电话-必填")
    guest_name: str = Field(..., min_length=1, max_length=100, description="预约人姓名")
    guest_phone: str = Field(..., min_length=1, max_length=50, description="预约人电话-含区号")
    reservation_datetime: str = Field(..., description="预约时间 YYYY-MM-DD HH:mm")
    adults: int = Field(default=1, ge=1, le=20, description="成人人数")
    children: int = Field(default=0, ge=0, le=20, description="儿童人数")
    notes: str = Field(default="", max_length=500, description="预约备注")


class ReservationResponse(BaseModel):
    """预约单响应"""
    id: int
    order_no: str
    user_id: int | None = None
    restaurant_name: str
    restaurant_phone: str
    guest_name: str
    guest_phone: str
    reservation_datetime: datetime
    adults: int
    children: int
    notes: str
    status: str
    payment_id: str
    amount_cents: int
    ai_call_result: str
    sms_sent: bool
    created_at: datetime

    class Config:
        from_attributes = True


class PaymentRequest(BaseModel):
    """支付请求"""
    order_no: str
    amount_cents: int = Field(default=100, description="金额(分)，默认100=1元")


class PaymentResponse(BaseModel):
    """支付响应"""
    success: bool
    payment_id: str
    qr_code: str = ""
    message: str


class CallbackRequest(BaseModel):
    """AI 通话回调"""
    order_no: str
    success: bool
    result_message: str = ""


class ReservationStatusUpdate(BaseModel):
    """预约状态更新"""
    status: str = Field(..., description="新状态: cancelled 等")


class UserResponse(BaseModel):
    """注册用户响应"""
    id: int
    phone: str
    nickname: str = ""
    created_at: datetime

    class Config:
        from_attributes = True
