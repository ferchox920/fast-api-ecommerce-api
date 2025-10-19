from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Union
from uuid import uuid4

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings
from app.core.token_blacklist import is_token_revoked

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
ALGORITHM = settings.JWT_ALGORITHM
_RESERVED_EXTRA_CLAIMS = {"sub", "exp", "type", "jti", "iat"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def hash_password(password: str) -> str:
    return get_password_hash(password)


def _apply_extra_claims(payload: dict[str, Any], extra: dict[str, Any] | None) -> None:
    if not extra:
        return
    for key, value in extra.items():
        if key in _RESERVED_EXTRA_CLAIMS:
            continue
        payload[key] = value


def _ensure_header_algorithm(token: str) -> None:
    try:
        header = jwt.get_unverified_header(token)
    except JWTError as exc:
        raise JWTError("Invalid token header") from exc
    alg = header.get("alg")
    if alg != ALGORITHM:
        raise JWTError("Token signed with unexpected algorithm")


def _candidate_secrets(primary: str | None, fallbacks: list[str]) -> list[str]:
    seen: list[str] = []
    for item in [primary, *fallbacks]:
        if not item:
            continue
        if item not in seen:
            seen.append(item)
    return seen


def _decode_with_rotation(token: str, primary: str | None, fallbacks: list[str]) -> dict[str, Any]:
    _ensure_header_algorithm(token)
    last_error: JWTError | None = None
    for secret in _candidate_secrets(primary, fallbacks):
        try:
            return jwt.decode(token, secret, algorithms=[ALGORITHM])
        except JWTError as exc:
            last_error = exc
    raise last_error or JWTError("Unable to decode token with provided secrets")


def _raise_if_revoked(payload: dict[str, Any]) -> None:
    if not settings.JWT_BLACKLIST_ENABLED:
        return
    jti = payload.get("jti")
    if not jti:
        return
    if is_token_revoked(jti):
        raise JWTError("Token has been revoked")


def create_access_token(
    subject: Union[str, int],
    expires_minutes: int | None = None,
    extra: dict[str, Any] | None = None,
) -> str:
    exp_min = expires_minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES
    now = _now()
    payload: dict[str, Any] = {
        "sub": str(subject),
        "type": "access",
        "exp": now + timedelta(minutes=exp_min),
        "iat": int(now.timestamp()),
        "jti": uuid4().hex,
    }
    _apply_extra_claims(payload, extra)
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(
    subject: Union[str, int],
    expires_days: int | None = None,
    extra: dict[str, Any] | None = None,
) -> str:
    exp_days = expires_days or settings.REFRESH_TOKEN_EXPIRE_DAYS
    secret = settings.REFRESH_SECRET_KEY or settings.SECRET_KEY
    now = _now()
    payload: dict[str, Any] = {
        "sub": str(subject),
        "type": "refresh",
        "exp": now + timedelta(days=exp_days),
        "iat": int(now.timestamp()),
        "jti": uuid4().hex,
    }
    _apply_extra_claims(payload, extra)
    return jwt.encode(payload, secret, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    data = _decode_with_rotation(token, settings.SECRET_KEY, settings.SECRET_KEY_FALLBACKS)
    if data.get("type") != "access":
        raise JWTError("Invalid token type")
    _raise_if_revoked(data)
    return data


def decode_refresh_token(token: str) -> dict[str, Any]:
    primary = settings.REFRESH_SECRET_KEY or settings.SECRET_KEY
    fallbacks: list[str] = list(settings.REFRESH_SECRET_KEY_FALLBACKS)
    if settings.REFRESH_SECRET_KEY:
        fallbacks.extend(settings.SECRET_KEY_FALLBACKS + [settings.SECRET_KEY])
    else:
        fallbacks.extend(settings.SECRET_KEY_FALLBACKS)
    data = _decode_with_rotation(token, primary, fallbacks)
    if data.get("type") != "refresh":
        raise JWTError("Invalid token type")
    _raise_if_revoked(data)
    return data


def create_email_verification_token(user_id: str) -> str:
    now = _now()
    payload = {
        "sub": str(user_id),
        "type": "verify_email",
        "exp": now + timedelta(hours=settings.VERIFY_TOKEN_EXPIRE_HOURS),
        "iat": int(now.timestamp()),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def decode_email_verification_token(token: str) -> str:
    data = _decode_with_rotation(token, settings.SECRET_KEY, settings.SECRET_KEY_FALLBACKS)
    if data.get("type") != "verify_email":
        raise JWTError("Invalid token type")
    return str(data["sub"])
