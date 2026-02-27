"""配置管理"""
import os

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Railway PostgreSQL 可能用 DATABASE_URL、DATABASE_PRIVATE_URL、POSTGRES_URL 等
    database_url: str = Field(
        default="sqlite+aiosqlite:///./reservations.db",
        description="数据库连接，Railway 需添加 PostgreSQL 并引用 DATABASE_URL",
    )

    @field_validator("database_url", mode="before")
    @classmethod
    def resolve_database_url(cls, v: str) -> str:
        """Railway 可能用不同变量名，若当前为 sqlite 则尝试其他 env"""
        if v and "sqlite" not in v.lower():
            return v
        url = (
            os.environ.get("DATABASE_URL")
            or os.environ.get("DATABASE_PRIVATE_URL")
            or os.environ.get("POSTGRES_URL")
            or os.environ.get("POSTGRES_PRIVATE_URL")
        )
        return url if url else (v or "sqlite+aiosqlite:///./reservations.db")

    @field_validator("database_url", mode="after")
    @classmethod
    def normalize_database_url(cls, v: str) -> str:
        """Railway 注入的 postgresql:// 需改为 postgresql+asyncpg://"""
        if v.startswith("postgresql://") and "+asyncpg" not in v:
            return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v
    payment_mode: str = "mock"
    # 支付宝当面付
    alipay_app_id: str = ""
    alipay_private_key: str = ""
    alipay_public_key: str = ""
    alipay_notify_url: str = ""
    alipay_sandbox: bool = False
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_phone_number: str = ""
    openai_api_key: str = ""
    # 餐厅搜索（可选，配置后优先使用，更稳定）
    google_places_api_key: str = ""
    foursquare_api_key: str = ""  # 推荐：每月 $200 免费额度，无需绑卡
    # 登录认证
    jwt_secret: str = "change-me-in-production"
    jwt_expire_hours: int = 720  # 30 天，登录后长期有效
    # 阿里云短信
    aliyun_access_key: str = ""
    aliyun_access_secret: str = ""
    aliyun_sms_sign_name: str = ""
    aliyun_sms_template_code: str = ""
    aliyun_sms_verify_template_code: str = ""  # 验证码模板（登录/注册用）
    aliyun_sms_mode: str = ""  # dysmsapi=短信服务, dypnsapi=融合认证套餐包（号码认证）
    aliyun_pnvs_instance_id: str = ""  # 融合认证实例资源ID（控制台可见，如 dypns_omniVerifySolution_public_cn-xxx）


settings = Settings()
