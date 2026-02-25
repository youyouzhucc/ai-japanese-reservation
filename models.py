"""预约数据模型"""
from datetime import datetime
from enum import Enum
from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class ReservationStatus(str, Enum):
    """预约状态"""
    PENDING = "pending"           # 待支付
    RESERVING = "reserving"       # 预约中（已支付，AI 正在打电话）
    SUCCESS = "success"          # 预约成功
    FAILED = "failed"            # 预约失败
    CANCELLED = "cancelled"      # 已取消


class Reservation(Base):
    """预约单"""
    __tablename__ = "reservations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    order_no = Column(String(32), unique=True, nullable=False, index=True)

    # 餐厅信息
    restaurant_name = Column(String(200), nullable=False)
    restaurant_phone = Column(String(50), nullable=False)

    # 预约人信息
    guest_name = Column(String(100), nullable=False)
    guest_phone = Column(String(50), nullable=False)  # 含区号

    # 预约时间
    reservation_datetime = Column(DateTime, nullable=False)
    adults = Column(Integer, default=1)
    children = Column(Integer, default=0)
    notes = Column(Text, default="")

    # 状态与支付
    status = Column(String(20), default=ReservationStatus.PENDING.value)
    payment_id = Column(String(100), default="")
    amount_cents = Column(Integer, default=0)  # 预约费，单位分

    # AI 通话
    ai_call_sid = Column(String(100), default="")
    ai_call_result = Column(Text, default="")  # 成功/失败原因

    # 短信通知
    sms_sent = Column(Boolean, default=False)
    sms_sent_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


def get_engine(database_url: str):
    return create_async_engine(database_url, echo=False)


def get_session_maker(engine):
    return async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def init_db(engine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
