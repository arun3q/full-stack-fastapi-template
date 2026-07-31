"""Job queue plumbing: Redis settings, the shared pool and the enqueue helper."""

import logging
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from app.core.config import settings

logger = logging.getLogger(__name__)

_redis_pool: ArqRedis | None = None


def redis_settings() -> RedisSettings:
    parts = urlparse(settings.REDIS_URL)
    return RedisSettings(
        host=parts.hostname or "localhost",
        port=parts.port or 6379,
        database=int((parts.path or "/0").lstrip("/") or 0),
        username=parts.username,
        password=parts.password,
        ssl=parts.scheme == "rediss",
    )


def set_redis_pool(pool: ArqRedis | None) -> None:
    global _redis_pool
    _redis_pool = pool


def get_redis_pool() -> ArqRedis | None:
    return _redis_pool


async def create_redis_pool() -> ArqRedis:
    return await create_pool(redis_settings())


async def enqueue_job(job_name: str, *args: Any, **kwargs: Any) -> str | None:
    """Enqueue a job for the worker. Returns the job id, or None if unavailable."""
    if _redis_pool is None:
        logger.warning("Background worker unavailable, skipping job: %s", job_name)
        return None
    try:
        job = await _redis_pool.enqueue_job(job_name, *args, **kwargs)
        return job.job_id if job else None
    except Exception:
        logger.exception("Failed to enqueue job: %s", job_name)
        return None


def get_utc_now() -> datetime:
    return datetime.now(UTC)
