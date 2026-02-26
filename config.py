"""配置管理"""
from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite+aiosqlite:///./reservations.db"

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
    jwt_expire_hours: int = 168  # 7 天
    # 阿里云短信
    aliyun_access_key: str = ""
    aliyun_access_secret: str = ""
    aliyun_sms_sign_name: str = ""
    aliyun_sms_template_code: str = ""
    aliyun_sms_verify_template_code: str = ""  # 验证码模板（登录/注册用）

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
