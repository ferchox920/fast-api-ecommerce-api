from __future__ import annotations

import importlib
import time
from typing import Any

from app.core.config import settings

redis_module: Any | None
try:
    redis_module = importlib.import_module("redis")
except ImportError:  # pragma: no cover - optional dependency
    redis_module = None


class TokenBlacklist:
    """Simple token blacklist with optional Redis backend."""

    def __init__(self, redis_url: str | None = None, prefix: str = "jwt-bl") -> None:
        self._prefix = prefix
        self._store: dict[str, float] = {}
        self._redis = None
        if redis_url and redis_module:
            try:
                self._redis = redis_module.Redis.from_url(redis_url, decode_responses=True)
            except Exception:  # pragma: no cover - redis misconfig
                self._redis = None

    def _key(self, jti: str) -> str:
        return f"{self._prefix}:{jti}"

    def add(self, jti: str, ttl_seconds: int) -> None:
        ttl = max(int(ttl_seconds), 1)
        expires_at = time.time() + ttl
        if self._redis:
            try:
                self._redis.setex(self._key(jti), ttl, "1")
                return
            except Exception:
                pass
        self._store[jti] = expires_at

    def contains(self, jti: str) -> bool:
        if self._redis:
            try:
                return bool(self._redis.exists(self._key(jti)))
            except Exception:
                pass
        expires_at = self._store.get(jti)
        if not expires_at:
            return False
        if expires_at < time.time():
            self._store.pop(jti, None)
            return False
        return True


_blacklist: TokenBlacklist | None = None


def _get_blacklist() -> TokenBlacklist:
    global _blacklist
    if _blacklist is None:
        _blacklist = TokenBlacklist(redis_url=getattr(settings, "REDIS_URL", None))
    return _blacklist


def revoke_token(jti: str, expires_in_seconds: int) -> None:
    if not settings.JWT_BLACKLIST_ENABLED or not jti:
        return
    ttl = max(int(expires_in_seconds) + settings.JWT_BLACKLIST_TTL_LEEWAY_SECONDS, 1)
    _get_blacklist().add(jti, ttl)


def is_token_revoked(jti: str) -> bool:
    if not settings.JWT_BLACKLIST_ENABLED or not jti:
        return False
    return _get_blacklist().contains(jti)
