"""
AI 日语电话预约系统 - 主入口
"""
import asyncio
from pathlib import Path
import uuid
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends, Request, Header
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, PlainTextResponse

BASE_DIR = Path(__file__).resolve().parent


class StaticFilesCache(StaticFiles):
    """StaticFiles with Cache-Control for faster repeat visits"""

    def __init__(self, *args, cache_control: str = "public, max-age=86400", **kwargs):
        self.cache_control = cache_control
        super().__init__(*args, **kwargs)

    def file_response(self, *args, **kwargs):
        resp = super().file_response(*args, **kwargs)
        resp.headers.setdefault("Cache-Control", self.cache_control)
        return resp

from config import settings
from models import User, Reservation, ReservationStatus, get_engine, get_session_maker, init_db
from schemas import (
    AuthSendCodeRequest, AuthVerifyRequest, AuthResponse,
    ReservationCreate, ReservationResponse, PaymentRequest, PaymentResponse,
    CallbackRequest, ReservationStatusUpdate, UserResponse,
)
from services import create_payment, initiate_call, send_reservation_sms
from services.restaurant_search import search_restaurants
from services.payment import verify_alipay_notify
from services.auth import store_verification_code, verify_code, create_token, decode_token
from services.sms import send_verification_code

engine = get_engine(settings.database_url)
SessionLocal = get_session_maker(engine)


async def get_db():
    async with SessionLocal() as session:
        yield session


async def get_current_user(
    authorization: str | None = Header(None),
    db=Depends(get_db),
) -> User:
    """从 Authorization: Bearer <token> 获取当前用户"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "请先登录")
    token = authorization[7:].strip()
    payload = decode_token(token)
    if not payload:
        raise HTTPException(401, "登录已过期，请重新登录")
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(401, "无效的登录信息")
    from sqlalchemy import select
    result = await db.execute(select(User).where(User.id == int(user_id)))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(401, "用户不存在")
    return user


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db(engine)
    yield
    await engine.dispose()


app = FastAPI(title="AI 日语电话预约系统", lifespan=lifespan)


def _gen_order_no() -> str:
    return datetime.now().strftime("%Y%m%d") + uuid.uuid4().hex[:8].upper()


def _parse_datetime(s: str) -> datetime:
    return datetime.strptime(s.strip(), "%Y-%m-%d %H:%M")


# ============ 认证 API ============

@app.get("/api/auth/sms-status")
async def auth_sms_status():
    """调试用：检查短信配置是否生效（不暴露密钥）"""
    import os
    from config import settings
    env_vars = ["ALIYUN_ACCESS_KEY", "ALIYUN_ACCESS_SECRET", "ALIYUN_SMS_SIGN_NAME", "ALIYUN_SMS_VERIFY_TEMPLATE_CODE", "ALIYUN_SMS_MODE"]
    env_present = {k: k in os.environ and bool(os.environ.get(k)) for k in env_vars}
    has_key = bool(settings.aliyun_access_key and settings.aliyun_access_secret)
    has_template = bool(getattr(settings, "aliyun_sms_verify_template_code", ""))
    mode = getattr(settings, "aliyun_sms_mode", "").lower()
    # 列出进程内 env 键样本，确认 Railway 是否注入了变量
    aliyun_keys = [k for k in os.environ.keys() if "ALIYUN" in k.upper()]
    return {
        "aliyun_configured": has_key and has_template,
        "aliyun_mode": mode or "(未设置)",
        "using_dypnsapi": mode == "dypnsapi",
        "sign_name": settings.aliyun_sms_sign_name or "(未设置)",
        "template_code": settings.aliyun_sms_verify_template_code or "(未设置)",
        "env_in_process": env_present,
        "aliyun_keys_in_env": aliyun_keys,
        "env_total_count": len(os.environ),
        "hint": "若 env_in_process 全为 false：1) 点击 Variables 页的 Deploy 按钮保存 2) 确认变量在正确 Environment(Production) 3) Redeploy 服务",
    }


@app.post("/api/auth/send-code")
async def auth_send_code(data: AuthSendCodeRequest):
    """发送验证码到手机"""
    phone = data.phone.strip().replace(" ", "").replace("-", "")
    if len(phone) < 8:
        raise HTTPException(400, "手机号格式不正确")
    code = store_verification_code(phone)
    ok = await send_verification_code(phone, code)
    if not ok:
        raise HTTPException(
            500,
            "验证码发送失败。请确认：1) 手机号已在阿里云控制台「测试手机号」中绑定；2) 查看服务端日志获取详细错误",
        )
    return {"message": "验证码已发送"}


@app.post("/api/auth/verify", response_model=AuthResponse)
async def auth_verify(data: AuthVerifyRequest, db=Depends(get_db)):
    """验证码登录/注册，返回 token"""
    phone = data.phone.strip().replace(" ", "").replace("-", "")
    if not verify_code(phone, data.code):
        raise HTTPException(400, "验证码错误或已过期")
    from sqlalchemy import select
    result = await db.execute(select(User).where(User.phone == phone))
    user = result.scalar_one_or_none()
    if not user:
        user = User(phone=phone)
        db.add(user)
        await db.commit()
        await db.refresh(user)
    token = create_token(user.id, user.phone)
    return AuthResponse(token=token, user_id=user.id, phone=user.phone)


@app.get("/api/auth/me")
async def auth_me(user: User = Depends(get_current_user)):
    """获取当前登录用户"""
    return {"user_id": user.id, "phone": user.phone}


# ============ 预约 API ============

@app.post("/api/reservations", response_model=ReservationResponse)
async def create_reservation(data: ReservationCreate, db=Depends(get_db), user: User = Depends(get_current_user)):
    """创建预约单（待支付），支付成功后发起 AI 电话"""
    dt = _parse_datetime(data.reservation_datetime)
    # 校验十分钟间隔
    if dt.minute % 10 != 0:
        raise HTTPException(400, "预约时间需为十分钟整点，如 18:00、18:10、18:20")
    order_no = _gen_order_no()
    r = Reservation(
        order_no=order_no,
        user_id=user.id,
        restaurant_name=data.restaurant_name,
        restaurant_phone=data.restaurant_phone,
        guest_name=data.guest_name,
        guest_phone=data.guest_phone,
        reservation_datetime=dt,
        adults=data.adults,
        children=data.children,
        notes=data.notes,
        status=ReservationStatus.PENDING.value,
        amount_cents=100,
    )
    db.add(r)
    await db.commit()
    await db.refresh(r)
    return r


@app.post("/api/pay", response_model=PaymentResponse)
async def pay(req: PaymentRequest, db=Depends(get_db), user: User = Depends(get_current_user)):
    """② 创建支付订单。模拟模式直接成功并触发 AI 电话；支付宝模式返回二维码，等 notify 回调后触发"""
    from sqlalchemy import select
    result = await db.execute(select(Reservation).where(Reservation.order_no == req.order_no))
    r = result.scalar_one_or_none()
    if not r:
        raise HTTPException(404, "订单不存在")
    if r.user_id and r.user_id != user.id:
        raise HTTPException(403, "无权操作此订单")
    if r.status != ReservationStatus.PENDING.value:
        raise HTTPException(400, f"订单状态不可支付: {r.status}")

    subject = f"AI日语预约-{r.restaurant_name}"
    pay_result = await create_payment(req.order_no, req.amount_cents or 100, subject)
    if not pay_result["success"]:
        raise HTTPException(400, pay_result["message"])

    r.payment_id = pay_result["payment_id"]
    r.amount_cents = req.amount_cents or 100
    await db.commit()

    # 模拟模式：直接触发 AI 电话；支付宝：等 /api/alipay/notify 回调
    if settings.payment_mode == "mock":
        r.status = ReservationStatus.RESERVING.value
        await db.commit()
        asyncio.create_task(_run_ai_call_and_notify(r.id))

    return PaymentResponse(
        success=pay_result["success"],
        payment_id=pay_result["payment_id"],
        qr_code=pay_result.get("qr_code", ""),
        message=pay_result["message"],
    )


async def _run_ai_call_and_notify(reservation_id: int):
    """后台：AI 打电话 -> 更新状态 -> 发短信。仅当真实通话返回结果时更新为成功/失败"""
    from sqlalchemy import select
    try:
        async with SessionLocal() as db:
            result = await db.execute(select(Reservation).where(Reservation.id == reservation_id))
            r = result.scalar_one_or_none()
            if not r:
                return
            call_result = await initiate_call(
                r.order_no, r.restaurant_phone, r.restaurant_name,
                r.guest_name, r.guest_phone, r.reservation_datetime,
                r.adults, r.children, r.notes,
            )
            r.ai_call_sid = call_result.get("call_sid", "")
            status = call_result.get("status", "")
            # 仅真实通话返回结果时更新状态；模拟模式保持预约中
            if status == "simulated":
                r.ai_call_result = "模拟模式：未实际拨打电话，状态保持预约中"
                # 保持 status = reserving，不改为 success
            elif status == "error":
                r.status = ReservationStatus.FAILED.value
                r.ai_call_result = call_result.get("error", str(call_result))
            elif status == "initiated":
                r.ai_call_result = "已发起通话，等待 webhook 回调"
                # 保持 status = reserving，由 callback 更新
            else:
                r.ai_call_result = str(call_result)
            await db.commit()
            await db.refresh(r)
            # 发短信（仅成功时）
            if r.status == ReservationStatus.SUCCESS.value:
                ok = await send_reservation_sms(
                    r.guest_phone, r.order_no,
                    True,
                    r.restaurant_name, r.reservation_datetime,
                )
                if ok:
                    r.sms_sent = True
                    r.sms_sent_at = datetime.utcnow()
                    await db.commit()
    except Exception as e:
        async with SessionLocal() as db:
            result = await db.execute(select(Reservation).where(Reservation.id == reservation_id))
            r = result.scalar_one_or_none()
            if r:
                r.status = ReservationStatus.FAILED.value
                r.ai_call_result = f"系统异常: {e}"
                await db.commit()


@app.post("/api/alipay/notify")
async def alipay_notify(request: Request, db=Depends(get_db)):
    """支付宝当面付异步通知回调。支付成功后更新状态并触发 AI 电话"""
    from sqlalchemy import select
    body = await request.body()
    # 支付宝发送 application/x-www-form-urlencoded
    from urllib.parse import parse_qs
    data = {k: v[0] if isinstance(v, list) else v for k, v in parse_qs(body.decode()).items()}
    if not data:
        return PlainTextResponse("fail")
    ok, order_no = verify_alipay_notify(dict(data))
    if not ok or not order_no:
        return PlainTextResponse("fail")
    result = await db.execute(select(Reservation).where(Reservation.order_no == order_no))
    r = result.scalar_one_or_none()
    if not r or r.status != ReservationStatus.PENDING.value:
        return PlainTextResponse("success")
    r.status = ReservationStatus.RESERVING.value
    r.payment_id = data.get("trade_no", r.payment_id)
    await db.commit()
    asyncio.create_task(_run_ai_call_and_notify(r.id))
    return PlainTextResponse("success")


@app.post("/api/callback/call")
async def callback_ai_call(req: CallbackRequest, db=Depends(get_db)):
    """AI 通话完成回调（真实 Twilio 时使用）"""
    from sqlalchemy import select
    result = await db.execute(select(Reservation).where(Reservation.order_no == req.order_no))
    r = result.scalar_one_or_none()
    if not r:
        raise HTTPException(404, "订单不存在")
    r.status = ReservationStatus.SUCCESS.value if req.success else ReservationStatus.FAILED.value
    r.ai_call_result = req.result_message
    await db.commit()
    # 发短信
    await send_reservation_sms(
        r.guest_phone, r.order_no, req.success,
        r.restaurant_name, r.reservation_datetime,
    )
    return {"ok": True}


@app.get("/api/restaurants/search")
async def restaurant_search(q: str = ""):
    """搜索餐厅，返回名称、电话、地址。有电话时前端可自动填充"""
    results = await search_restaurants(
        q,
        google_key=settings.google_places_api_key or None,
        foursquare_key=settings.foursquare_api_key or None,
    )
    return {"results": results}


@app.get("/api/reservations/{order_no}", response_model=ReservationResponse)
async def get_reservation(order_no: str, db=Depends(get_db), user: User = Depends(get_current_user)):
    """查询预约单（仅本人）"""
    from sqlalchemy import select
    result = await db.execute(select(Reservation).where(Reservation.order_no == order_no))
    r = result.scalar_one_or_none()
    if not r:
        raise HTTPException(404, "订单不存在")
    if r.user_id and r.user_id != user.id:
        raise HTTPException(403, "无权查看此订单")
    return r


@app.get("/api/reservations", response_model=list[ReservationResponse])
async def list_reservations(skip: int = 0, limit: int = 50, db=Depends(get_db), user: User = Depends(get_current_user)):
    """我的预约列表（仅当前用户）"""
    from sqlalchemy import select
    result = await db.execute(
        select(Reservation)
        .where(Reservation.user_id == user.id)
        .order_by(Reservation.id.desc())
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()


@app.get("/api/admin/db-status")
async def admin_db_status():
    """管理后台：数据库状态（用于排查数据丢失）"""
    import os

    url = settings.database_url
    env_has = {
        "DATABASE_URL": bool(os.environ.get("DATABASE_URL")),
        "DATABASE_PRIVATE_URL": bool(os.environ.get("DATABASE_PRIVATE_URL")),
        "POSTGRES_URL": bool(os.environ.get("POSTGRES_URL")),
    }
    if "sqlite" in url:
        return {
            "type": "sqlite",
            "warning": "SQLite 数据在 Railway 重启/redeploy 后会丢失",
            "hint": "在 Web Service 的 Variables 中添加 DATABASE_URL，值引用 PostgreSQL 服务（如 ${{Postgres.DATABASE_URL}}），然后 Redeploy",
            "env_check": env_has,
        }
    return {"type": "postgresql", "ok": True}


@app.get("/api/admin/users", response_model=list[UserResponse])
async def admin_list_users(skip: int = 0, limit: int = 200, db=Depends(get_db)):
    """管理后台：注册用户列表"""
    from sqlalchemy import select
    result = await db.execute(
        select(User).order_by(User.id.desc()).offset(skip).limit(limit)
    )
    return result.scalars().all()


@app.get("/api/admin/reservations", response_model=list[ReservationResponse])
async def admin_list_reservations(skip: int = 0, limit: int = 100, db=Depends(get_db)):
    """管理后台：全部预约列表（无用户过滤）"""
    from sqlalchemy import select
    result = await db.execute(
        select(Reservation).order_by(Reservation.id.desc()).offset(skip).limit(limit)
    )
    return result.scalars().all()


@app.get("/api/admin/reservations/{order_no}", response_model=ReservationResponse)
async def admin_get_reservation(order_no: str, db=Depends(get_db)):
    """管理后台：查询任意预约单"""
    from sqlalchemy import select
    result = await db.execute(select(Reservation).where(Reservation.order_no == order_no))
    r = result.scalar_one_or_none()
    if not r:
        raise HTTPException(404, "订单不存在")
    return r


@app.patch("/api/admin/reservations/{order_no}", response_model=ReservationResponse)
async def admin_update_reservation(order_no: str, data: ReservationStatusUpdate, db=Depends(get_db)):
    """管理后台：更新预约状态（如取消）"""
    from sqlalchemy import select
    result = await db.execute(select(Reservation).where(Reservation.order_no == order_no))
    r = result.scalar_one_or_none()
    if not r:
        raise HTTPException(404, "订单不存在")
    if data.status == "cancelled":
        if r.status not in (ReservationStatus.PENDING.value, ReservationStatus.RESERVING.value):
            raise HTTPException(400, f"当前状态不可取消: {r.status}")
        r.status = ReservationStatus.CANCELLED.value
    else:
        raise HTTPException(400, f"不支持的状态: {data.status}")
    await db.commit()
    await db.refresh(r)
    return r


@app.patch("/api/reservations/{order_no}", response_model=ReservationResponse)
async def update_reservation(order_no: str, data: ReservationStatusUpdate, db=Depends(get_db), user: User = Depends(get_current_user)):
    """更新预约状态（如取消），仅本人"""
    from sqlalchemy import select
    result = await db.execute(select(Reservation).where(Reservation.order_no == order_no))
    r = result.scalar_one_or_none()
    if not r:
        raise HTTPException(404, "订单不存在")
    if r.user_id and r.user_id != user.id:
        raise HTTPException(403, "无权操作此订单")
    if data.status == "cancelled":
        if r.status not in (ReservationStatus.PENDING.value, ReservationStatus.RESERVING.value):
            raise HTTPException(400, f"当前状态不可取消: {r.status}")
        r.status = ReservationStatus.CANCELLED.value
    else:
        raise HTTPException(400, f"不支持的状态: {data.status}")
    await db.commit()
    await db.refresh(r)
    return r


# 静态文件（带缓存头，加速重复访问）
app.mount("/static", StaticFilesCache(directory=str(BASE_DIR / "static")), name="static")


@app.get("/")
async def index():
    return FileResponse(BASE_DIR / "static" / "index.html")


@app.get("/admin")
async def admin():
    """预约单管理后台"""
    return FileResponse(BASE_DIR / "static" / "admin.html")


@app.get("/my-reservations")
async def my_reservations_page():
    """我的预约单页面"""
    return FileResponse(BASE_DIR / "static" / "my-reservations.html")


@app.get("/my-account")
async def my_account_page():
    """我的账号页面"""
    return FileResponse(BASE_DIR / "static" / "my-account.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
