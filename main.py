"""
AI 日语电话预约系统 - 主入口
"""
import asyncio
import logging
from pathlib import Path
import uuid
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends, Request, Header, WebSocket, WebSocketDisconnect
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
from services.ai_voice_stream import handle_media_stream
from services.restaurant_search import search_restaurants
from services.payment import verify_alipay_notify, verify_qiufk_notify
from services.auth import store_verification_code, verify_code, create_token, decode_token, generate_nickname
from services.sms import send_verification_code

engine = get_engine(settings.database_url)
SessionLocal = get_session_maker(engine)
log = logging.getLogger(__name__)


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
        raise HTTPException(401, "登录已过期，请重新登录")
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


@app.get("/api/ai-phone-status")
async def ai_phone_status():
    """调试用：检查 AI 电话配置（不暴露密钥）"""
    vapi_ok = bool(settings.vapi_api_key)
    twilio_ok = bool(settings.twilio_account_sid and settings.twilio_auth_token and settings.twilio_phone_number)
    openai_ok = bool(settings.openai_api_key)
    base_ok = bool(settings.app_base_url)
    if vapi_ok:
        mode = "vapi"
        hint = "Vapi.ai 已配置" + ("（含电话号码）" if settings.vapi_phone_number_id else "（未配置电话号码ID，将使用 Vapi 免费号码）")
    elif twilio_ok and openai_ok:
        mode = "twilio+openai"
        hint = "Twilio + OpenAI 已配置"
    else:
        mode = "mock"
        hint = "模拟模式（未配置 VAPI_API_KEY 或 Twilio）"
    return {
        "mode": mode,
        "vapi_configured": vapi_ok,
        "vapi_phone_number_id": settings.vapi_phone_number_id[:8] + "..." if settings.vapi_phone_number_id else "",
        "twilio_configured": twilio_ok,
        "openai_configured": openai_ok,
        "app_base_url": settings.app_base_url or "(未设置)",
        "hint": hint,
    }


@app.post("/api/vapi/webhook")
async def vapi_webhook(request: Request, db=Depends(get_db)):
    """Vapi.ai 通话状态回调"""
    from sqlalchemy import select
    try:
        data = await request.json()
    except Exception:
        return {"ok": True}
    event_type = data.get("message", {}).get("type", "")
    call_data = data.get("message", {}).get("call", {})
    call_id = call_data.get("id", "")
    metadata = call_data.get("assistant", {}).get("metadata", {}) or {}
    order_no = metadata.get("order_no", "")

    if not call_id and not order_no:
        return {"ok": True}

    log.info("[Vapi] webhook: event=%s, call_id=%s, order_no=%s", event_type, call_id, order_no)

    if event_type == "end-of-call-report":
        ended_reason = data.get("message", {}).get("endedReason", "")
        transcript = data.get("message", {}).get("transcript", "")
        summary = data.get("message", {}).get("summary", "")

        if order_no:
            result = await db.execute(select(Reservation).where(Reservation.order_no == order_no))
        elif call_id:
            result = await db.execute(select(Reservation).where(Reservation.ai_call_sid == call_id))
        else:
            return {"ok": True}
        r = result.scalar_one_or_none()
        if not r:
            return {"ok": True}

        call_result = summary or transcript or ended_reason
        if ended_reason in ("assistant-ended-call", "customer-ended-call"):
            r.status = ReservationStatus.SUCCESS.value
            r.ai_call_result = f"AI 通话完成\n{call_result}" if call_result else "AI 通话完成"
        else:
            r.status = ReservationStatus.FAILED.value
            r.ai_call_result = f"通话未完成: {ended_reason}\n{call_result}" if call_result else f"通话未完成: {ended_reason}"
        await db.commit()
        await db.refresh(r)

        if r.status == ReservationStatus.SUCCESS.value:
            await send_reservation_sms(
                r.guest_phone, r.order_no, True,
                r.restaurant_name, r.reservation_datetime,
            )

    return {"ok": True}


@app.get("/api/payment-status")
async def payment_status():
    """调试用：检查支付配置（不暴露密钥）"""
    mode = settings.payment_mode or "mock"
    ok = False
    hint = ""
    if mode == "mock":
        ok = True
        hint = "模拟模式：无需真实支付"
    elif mode == "alipay":
        ok = bool(settings.alipay_app_id and settings.alipay_private_key and settings.alipay_public_key and settings.alipay_notify_url)
        hint = "支付宝当面付" if ok else "缺少 ALIPAY_APP_ID / ALIPAY_PRIVATE_KEY / ALIPAY_PUBLIC_KEY / ALIPAY_NOTIFY_URL"
    elif mode == "qiufk_v2":
        ok = bool(
            settings.qiufk_pid and settings.qiufk_private_key and settings.qiufk_public_key
            and settings.qiufk_api_url and settings.qiufk_notify_url
        )
        hint = "易付通 V2" if ok else "缺少 QIUFK_PID / QIUFK_PRIVATE_KEY / QIUFK_PUBLIC_KEY / QIUFK_API_URL / QIUFK_NOTIFY_URL"
    elif mode in ("epay", "vmq"):
        ok = False
        hint = f"当前代码不支持 {mode}，请使用 mock、alipay 或 qiufk_v2"
    else:
        hint = f"未知 payment_mode={mode}，支持: mock, alipay"
    return {"payment_mode": mode, "configured": ok, "hint": hint}


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
        user = User(phone=phone, nickname=generate_nickname())
        db.add(user)
        await db.commit()
        await db.refresh(user)
    elif not user.nickname:
        user.nickname = generate_nickname()
        await db.commit()
        await db.refresh(user)
    token = create_token(user.id, user.phone)
    return AuthResponse(token=token, user_id=user.id, phone=user.phone, nickname=user.nickname or "")


@app.get("/api/auth/me")
async def auth_me(user: User = Depends(get_current_user)):
    """获取当前登录用户"""
    return {"user_id": user.id, "phone": user.phone, "nickname": user.nickname or ""}


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
        amount_cents=1,
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
    pay_result = await create_payment(req.order_no, req.amount_cents or 1, subject)
    if not pay_result["success"]:
        msg = pay_result["message"]
        log.warning("[支付] 创建失败: order_no=%s, mode=%s, msg=%s", req.order_no, settings.payment_mode, msg)
        raise HTTPException(400, msg)

    r.payment_id = pay_result["payment_id"]
    r.amount_cents = req.amount_cents or 1
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


@app.api_route("/api/qiufk/notify", methods=["GET", "POST"])
async def qiufk_notify(request: Request, db=Depends(get_db)):
    """易付通 V2 异步通知回调。支付成功后更新状态并触发 AI 电话"""
    from sqlalchemy import select
    if request.method == "GET":
        data = dict(request.query_params)
    else:
        body = await request.body()
        from urllib.parse import parse_qs
        data = {k: v[0] if isinstance(v, list) else v for k, v in parse_qs(body.decode()).items()}
    if not data:
        return PlainTextResponse("fail")
    ok, order_no = verify_qiufk_notify(dict(data))
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


# ============ Twilio AI 电话 ============

@app.get("/api/twiml/{order_no}")
async def twiml_for_call(order_no: str, request: Request, db=Depends(get_db)):
    """Twilio 接通餐厅后请求此 URL，返回 TwiML 连接 Media Stream"""
    from twilio.twiml.voice_response import VoiceResponse, Connect, Stream
    from sqlalchemy import select

    result = await db.execute(select(Reservation).where(Reservation.order_no == order_no))
    r = result.scalar_one_or_none()
    if not r:
        return PlainTextResponse("Order not found", status_code=404)

    base = (settings.app_base_url or "").strip()
    if not base:
        # 从 request 推导
        base = str(request.url).replace(request.url.path, "").rstrip("/")
    if base.startswith("http://"):
        base = "wss://" + base[7:]
    elif base.startswith("https://"):
        base = "wss://" + base[8:]
    elif base and not base.startswith("wss://"):
        base = "wss://" + base

    stream_url = f"{base}/media-stream?order_no={order_no}"
    response = VoiceResponse()
    connect = Connect()
    connect.stream(url=stream_url)
    response.append(connect)
    return PlainTextResponse(str(response), media_type="application/xml")


@app.websocket("/media-stream")
async def media_stream_ws(websocket: WebSocket):
    """Twilio Media Stream WebSocket，桥接 OpenAI Realtime API"""
    order_no = websocket.query_params.get("order_no", "")
    if not order_no:
        await websocket.close()
        return

    async def get_reservation(ono: str):
        from sqlalchemy import select
        async with SessionLocal() as sess:
            result = await sess.execute(select(Reservation).where(Reservation.order_no == ono))
            return result.scalar_one_or_none()

    try:
        await handle_media_stream(websocket, order_no, get_reservation)
    except WebSocketDisconnect:
        log.info("[AI] WebSocket disconnected: order_no=%s", order_no)


@app.api_route("/api/twilio/status", methods=["GET", "POST"])
async def twilio_status_callback(request: Request, db=Depends(get_db)):
    """Twilio 通话状态回调（completed/busy/failed/no-answer 等）"""
    from sqlalchemy import select

    if request.method == "GET":
        data = dict(request.query_params)
    else:
        body = await request.body()
        from urllib.parse import parse_qs
        data = {k: v[0] if isinstance(v, list) else v for k, v in parse_qs(body.decode()).items()}

    call_sid = data.get("CallSid", "")
    call_status = data.get("CallStatus", "")
    if not call_sid:
        return PlainTextResponse("OK")

    result = await db.execute(select(Reservation).where(Reservation.ai_call_sid == call_sid))
    r = result.scalar_one_or_none()
    if not r:
        return PlainTextResponse("OK")

    if call_status == "completed":
        r.status = ReservationStatus.SUCCESS.value
        r.ai_call_result = "AI 通话完成，预约成功"
        await db.commit()
        await db.refresh(r)
        # 发送成功短信
        await send_reservation_sms(
            r.guest_phone, r.order_no, True,
            r.restaurant_name, r.reservation_datetime,
        )
    elif call_status in ("busy", "failed", "no-answer", "canceled"):
        r.status = ReservationStatus.FAILED.value
        r.ai_call_result = f"通话未接通: {call_status}"
        await db.commit()
    else:
        await db.commit()
    return PlainTextResponse("OK")


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
