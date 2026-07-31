from redis.asyncio import Redis

from app.core.config import settings

# Shared async Redis client, usable for caching and job queueing.
redis_client = Redis.from_url(settings.REDIS_URL, decode_responses=True)


async def close_redis() -> None:
    await redis_client.aclose()
