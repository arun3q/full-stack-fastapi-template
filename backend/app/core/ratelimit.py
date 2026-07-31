"""Rate limiting (slowapi) + failed-login lockout helpers.

Storage defaults to an in-memory backend so it works with zero configuration;
point ``RATE_LIMIT_STORAGE`` at Redis for multi-worker deployments.
Lockout counters live in Redis and are skipped gracefully when Redis is down.
"""

import logging

from slowapi import Limiter
from starlette.requests import Request

from app.core.config import settings
from app.core.redis import redis_client

logger = logging.getLogger(__name__)


def _rate_key(request: Request) -> str:
    """Use the first X-Forwarded-For IP when present (trusted proxy), else remote."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


limiter = Limiter(
    key_func=_rate_key,
    storage_uri=settings.RATE_LIMIT_STORAGE,
)

_FAILURE_PREFIX = "login_fail:"


async def record_login_failure(email: str) -> int:
    try:
        key = f"{_FAILURE_PREFIX}{email.lower()}"
        count = await redis_client.incr(key)
        if count == 1:
            await redis_client.expire(key, settings.LOGIN_FAILURE_WINDOW_SECONDS)
        return int(count)
    except Exception:
        logger.debug("Redis unavailable; login lockout disabled")
        return 0


async def is_login_locked(email: str) -> bool:
    try:
        key = f"{_FAILURE_PREFIX}{email.lower()}"
        count = int(await redis_client.get(key) or 0)
        return count >= settings.LOGIN_FAILURE_LIMIT
    except Exception:
        return False


async def clear_login_failures(email: str) -> None:
    try:
        await redis_client.delete(f"{_FAILURE_PREFIX}{email.lower()}")
    except Exception:
        pass
