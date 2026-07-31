"""Lightweight Redis cache helpers with graceful fallback when Redis is down."""

import functools
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from app.core.redis import redis_client

logger = logging.getLogger(__name__)

T = TypeVar("T")

CACHE_PREFIX = "cache:"


async def cache_get(key: str) -> Any | None:
    try:
        raw = await redis_client.get(f"{CACHE_PREFIX}{key}")
        return json.loads(raw) if raw else None
    except Exception:
        return None


async def cache_set(key: str, value: Any, ttl_seconds: int = 60) -> None:
    try:
        await redis_client.set(
            f"{CACHE_PREFIX}{key}", json.dumps(value, default=str), ex=ttl_seconds
        )
    except Exception:
        logger.debug("Redis cache unavailable for key: %s", key)


async def cache_delete(key: str) -> None:
    try:
        await redis_client.delete(f"{CACHE_PREFIX}{key}")
    except Exception:
        pass


def cached(
    key_builder: Callable[..., str], ttl_seconds: int = 60
) -> Callable[[Callable[..., Awaitable[T]]], Callable[..., Awaitable[T]]]:
    """Cache an async function's result by a dynamic key.

    Uses ``functools.wraps`` so FastAPI can still introspect the endpoint
    signature for dependency injection.
    """

    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            key = key_builder(*args, **kwargs)
            cached_value = await cache_get(key)
            if cached_value is not None:
                return cached_value
            value = await func(*args, **kwargs)
            await cache_set(key, value, ttl_seconds)
            return value

        return wrapper

    return decorator
