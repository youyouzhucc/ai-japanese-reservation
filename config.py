"""配置管理"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite+aiosqlite:///./reservations.db"
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
