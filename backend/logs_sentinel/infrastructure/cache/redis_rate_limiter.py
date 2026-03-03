from __future__ import annotations

from datetime import timedelta

import redis.asyncio as redis


class RedisRateLimiter:
    """Simple fixed-window counter rate limiter based on Redis INCR and EXPIRE."""

    def __init__(self, client: redis.Redis) -> None:
        self._client = client

    async def check_and_increment(self, key: str, limit: int, window_seconds: int) -> bool:
        """Increment usage for key and return True if under limit."""

        window = timedelta(seconds=window_seconds)
        ttl = int(window.total_seconds())

        async with self._client.pipeline(transaction=True) as pipe:
            pipe.incr(key, 1)
            pipe.expire(key, ttl)
            current, _ = await pipe.execute()

        return int(current) <= limit


def create_redis_client(url: str) -> redis.Redis:
    """Create a shared async Redis client."""

    return redis.from_url(url, encoding="utf-8", decode_responses=True)

