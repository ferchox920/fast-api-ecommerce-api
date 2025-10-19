from __future__ import annotations

import asyncio
import importlib
import time
from dataclasses import dataclass
from typing import Any, Callable, Awaitable

from fastapi import HTTPException, Request, status

from app.core.config import settings

redis_async: Any | None
redis_exceptions: Any | None
try:
    redis_async = importlib.import_module("redis.asyncio")
    redis_exceptions = importlib.import_module("redis.exceptions")
except ImportError:  # pragma: no cover - optional dependency
    redis_async = None
    redis_exceptions = None


@dataclass
class RateLimitExceeded(Exception):
    reset_in: float


class RateLimiter:
    """Simple rate limiter with optional Redis backend."""

    def __init__(self, redis_url: str | None = None, prefix: str = "rl") -> None:
        self._prefix = prefix
        self._memory_store: dict[str, tuple[int, float]] = {}
        self._lock = asyncio.Lock()
        self._redis = None
        if redis_url and redis_async:
            try:
                self._redis = redis_async.from_url(
                    redis_url,
                    encoding="utf-8",
                    decode_responses=True,
                )
            except Exception:  # pragma: no cover - redis misconfig
                self._redis = None

    async def _hit_redis(self, key: str, limit: int, period_seconds: int) -> float | None:
        if not self._redis:
            return None

        redis_key = f"{self._prefix}:{key}:{period_seconds}"
        try:
            async with self._redis.pipeline() as pipe:
                while True:
                    try:
                        await pipe.watch(redis_key)
                        current = await pipe.get(redis_key)
                        ttl = await pipe.ttl(redis_key)
                        if current is None:
                            pipe.multi()
                            pipe.set(redis_key, 1, ex=period_seconds, nx=True)
                            await pipe.execute()
                            return period_seconds

                        if int(current) >= limit:
                            ttl = ttl if ttl and ttl > 0 else period_seconds
                            raise RateLimitExceeded(reset_in=float(ttl))

                        pipe.multi()
                        pipe.incr(redis_key, 1)
                        if ttl == -1:
                            pipe.expire(redis_key, period_seconds)
                            ttl = period_seconds
                        await pipe.execute()
                        return float(ttl if ttl and ttl > 0 else period_seconds)
                    except Exception as exc:  # pragma: no cover - redis race
                        if redis_exceptions and isinstance(exc, redis_exceptions.WatchError):
                            continue
                        raise
        except RateLimitExceeded:
            raise
        except Exception:
            return None

    async def check(self, key: str, limit: int, period_seconds: int) -> float:
        """Increment the counter and return the remaining window in seconds."""
        ttl = await self._hit_redis(key, limit, period_seconds)
        if ttl is not None:
            return ttl

        now = time.monotonic()
        async with self._lock:
            count, reset_at = self._memory_store.get(key, (0, now + period_seconds))
            if now > reset_at:
                count = 0
                reset_at = now + period_seconds
            if count >= limit:
                raise RateLimitExceeded(reset_in=max(0.0, reset_at - now))
            self._memory_store[key] = (count + 1, reset_at)
            return max(0.0, reset_at - now)


_rate_limiter: RateLimiter | None = None


def get_rate_limiter() -> RateLimiter:
    global _rate_limiter
    if _rate_limiter is None:
        redis_url = getattr(settings, "REDIS_URL", None)
        _rate_limiter = RateLimiter(redis_url=redis_url)
    return _rate_limiter


def rate_limit(
    limit: int,
    period_seconds: int = 60,
    scope: str = "default",
    identifier: Callable[[Request], str] | None = None,
) -> Callable[[Request], Awaitable[None]]:
    identifier = identifier or (lambda request: request.client.host if request.client else "anonymous")

    async def dependency(request: Request) -> None:
        key = f"{scope}:{identifier(request)}"
        limiter = get_rate_limiter()
        try:
            reset_in = await limiter.check(key, limit=limit, period_seconds=period_seconds)
        except RateLimitExceeded as exc:
            headers = {"Retry-After": str(int(max(1, round(exc.reset_in))))}
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests, please slow down.",
                headers=headers,
            ) from exc
        request.state.rate_limit_reset_in = reset_in
        return None

    return dependency
