# app/core/security.py
from datetime import datetime, timedelta, timezone
from typing import Any, Union
from jose import jwt, JWTError
from passlib.context import CryptContext
from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
ALGORITHM = settings.JWT_ALGORITHM

def _now() -> datetime:
    return datetime.now(timezone.utc)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

# Alias compat
def hash_password(password: str) -> str:
    return get_password_hash(password)

def create_access_token(subject: Union[str, int], expires_minutes: int | None = None, extra: dict[str, Any] | None = None) -> str:
    exp_min = expires_minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES
    payload: dict[str, Any] = {"sub": str(subject), "exp": _now() + timedelta(minutes=exp_min), "type": "access"}
    if extra: payload.update(extra)
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)

def create_refresh_token(subject: Union[str, int], expires_days: int | None = None, extra: dict[str, Any] | None = None) -> str:
    exp_days = expires_days or settings.REFRESH_TOKEN_EXPIRE_DAYS
    secret = settings.REFRESH_SECRET_KEY or settings.SECRET_KEY
    payload: dict[str, Any] = {"sub": str(subject), "exp": _now() + timedelta(days=exp_days), "type": "refresh"}
    if extra: payload.update(extra)
    return jwt.encode(payload, secret, algorithm=ALGORITHM)

def decode_refresh_token(token: str) -> dict[str, Any]:
    secret = settings.REFRESH_SECRET_KEY or settings.SECRET_KEY
    data = jwt.decode(token, secret, algorithms=[ALGORITHM])
    if data.get("type") != "refresh":
        raise JWTError("Invalid token type")
    return data

# Email verification tokens
def create_email_verification_token(user_id: str) -> str:
    payload = {
        "sub": str(user_id),
        "type": "verify_email",
        "exp": _now() + timedelta(hours=settings.VERIFY_TOKEN_EXPIRE_HOURS),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)

def decode_email_verification_token(token: str) -> str:
    data = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    if data.get("type") != "verify_email":
        raise JWTError("Invalid token type")
    return str(data["sub"])
