"""
AI 日语电话预约系统 - 主入口
"""
import asyncio
from pathlib import Path
import uuid
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

BASE_DIR = Path(__file__).resolve().parent

from config import settings
from models import Reservation, ReservationStatus, get_engine, get_session_maker, init_db
from schemas import ReservationCreate, ReservationResponse, PaymentRequest, PaymentResponse, CallbackRequest
from services import create_payment, initiate_call, send_reservation_sms

engine = get_engine(settings.database_url)
SessionLocal = get_session_maker(engine)


async def get_db():
    async with SessionLocal() as session:
        yield session


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


# ============ API ============

@app.post("/api/reservations", response_model=ReservationResponse)
async def create_reservation(data: ReservationCreate, db=Depends(get_db)):
    """① 创建预约单（待支付）"""
    dt = _parse_datetime(data.reservation_datetime)
    # 校验十分钟间隔
    if dt.minute % 10 != 0:
        raise HTTPException(400, "预约时间需为十分钟整点，如 18:00、18:10、18:20")
    order_no = _gen_order_no()
    r = Reservation(
        order_no=order_no,
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
async def pay(req: PaymentRequest, db=Depends(get_db)):
    """② 支付并触发 AI 电话"""
    from sqlalchemy import select
    result = await db.execute(select(Reservation).where(Reservation.order_no == req.order_no))
    r = result.scalar_one_or_none()
    if not r:
        raise HTTPException(404, "订单不存在")
    if r.status != ReservationStatus.PENDING.value:
        raise HTTPException(400, f"订单状态不可支付: {r.status}")

    pay_result = await create_payment(req.order_no, req.amount_cents or 100)
    if not pay_result["success"]:
        raise HTTPException(400, pay_result["message"])

    r.payment_id = pay_result["payment_id"]
    r.amount_cents = req.amount_cents or 100
    r.status = ReservationStatus.RESERVING.value
    await db.commit()

    # ③ 异步发起 AI 电话
    asyncio.create_task(_run_ai_call_and_notify(r.id))
    return PaymentResponse(**pay_result)


async def _run_ai_call_and_notify(reservation_id: int):
    """后台：AI 打电话 -> 更新状态 -> 发短信"""
    from sqlalchemy import select
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
        # 模拟模式直接成功；真实模式需通过 webhook 回调更新
        if call_result.get("status") == "simulated":
            r.status = ReservationStatus.SUCCESS.value
            r.ai_call_result = "模拟预约成功"
        else:
            r.ai_call_result = str(call_result)
        await db.commit()
        await db.refresh(r)
        # ④ 发短信
        ok = await send_reservation_sms(
            r.guest_phone, r.order_no,
            r.status == ReservationStatus.SUCCESS.value,
            r.restaurant_name, r.reservation_datetime,
        )
        if ok:
            r.sms_sent = True
            r.sms_sent_at = datetime.utcnow()
            await db.commit()


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


@app.get("/api/reservations/{order_no}", response_model=ReservationResponse)
async def get_reservation(order_no: str, db=Depends(get_db)):
    """查询预约单"""
    from sqlalchemy import select
    result = await db.execute(select(Reservation).where(Reservation.order_no == order_no))
    r = result.scalar_one_or_none()
    if not r:
        raise HTTPException(404, "订单不存在")
    return r


@app.get("/api/reservations", response_model=list[ReservationResponse])
async def list_reservations(skip: int = 0, limit: int = 50, db=Depends(get_db)):
    """预约列表"""
    from sqlalchemy import select
    result = await db.execute(select(Reservation).order_by(Reservation.id.desc()).offset(skip).limit(limit))
    return result.scalars().all()


# 静态文件
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


@app.get("/")
async def index():
    return FileResponse(BASE_DIR / "static" / "index.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
