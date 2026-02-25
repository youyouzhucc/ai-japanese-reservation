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
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_phone_number: str = ""
    openai_api_key: str = ""
    # 阿里云短信
    aliyun_access_key: str = ""
    aliyun_access_secret: str = ""
    aliyun_sms_sign_name: str = ""
    aliyun_sms_template_code: str = ""

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
