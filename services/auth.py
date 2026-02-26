"""认证服务：验证码存储、JWT 签发"""
import random
import string
import time
from datetime import datetime, timedelta
from typing import Optional

from config import settings

# 内存存储：phone -> (code, expires_at)，生产环境可换 Redis
_verify_codes: dict[str, tuple[str, float]] = {}
_CODE_EXPIRE_SEC = 300  # 5 分钟


def _normalize_phone(phone: str) -> str:
    return phone.strip().replace(" ", "").replace("-", "")


def store_verification_code(phone: str) -> str:
    """生成并存储验证码，返回 6 位数字"""
    phone = _normalize_phone(phone)
    code = "".join(random.choices(string.digits, k=6))
    _verify_codes[phone] = (code, time.time() + _CODE_EXPIRE_SEC)
    return code


def verify_code(phone: str, code: str) -> bool:
    """校验验证码，成功则清除"""
    phone = _normalize_phone(phone)
    now = time.time()
    if phone not in _verify_codes:
        return False
    stored_code, expires = _verify_codes[phone]
    if now > expires:
        del _verify_codes[phone]
        return False
    if stored_code != code.strip():
        return False
    del _verify_codes[phone]
    return True


def create_token(user_id: int, phone: str) -> str:
    """签发 JWT"""
    import jwt
    payload = {
        "sub": str(user_id),
        "phone": phone,
        "exp": datetime.utcnow() + timedelta(hours=settings.jwt_expire_hours),
        "iat": datetime.utcnow(),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_token(token: str) -> Optional[dict]:
    """解析 JWT，失败返回 None"""
    import jwt
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    except Exception:
        return None
