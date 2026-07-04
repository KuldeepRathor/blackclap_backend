"""
Simple Redis cache for read-heavy API endpoints (e.g. reels feed).

Separate from the pub/sub Redis connection used by WebSockets so that
cache failures never impact real-time delivery.
"""

import logging
from typing import cast

import redis.asyncio as aioredis

from app.core.config.settings import settings

logger = logging.getLogger(__name__)


class RedisCache:
    def __init__(self) -> None:
        self._redis: aioredis.Redis | None = None

    async def start(self) -> None:
        self._redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        logger.info("RedisCache connected (%s)", settings.REDIS_URL)

    async def stop(self) -> None:
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None
            logger.info("RedisCache disconnected")

    async def get(self, key: str) -> str | None:
        if self._redis is None:
            return None
        try:
            # decode_responses=True guarantees str, but redis-py types it as bytes
            return cast(str | None, await self._redis.get(key))
        except Exception:
            logger.exception("RedisCache.get(%s) failed", key)
            return None

    async def setex(self, key: str, seconds: int, value: str) -> None:
        if self._redis is None:
            return
        try:
            await self._redis.setex(key, seconds, value)
        except Exception:
            logger.exception("RedisCache.setex(%s) failed", key)

    async def delete(self, key: str) -> None:
        if self._redis is None:
            return
        try:
            await self._redis.delete(key)
        except Exception:
            logger.exception("RedisCache.delete(%s) failed", key)

    async def incr(self, key: str) -> int:
        """Atomically increment a counter, returning the new value (0 on failure)."""
        if self._redis is None:
            return 0
        try:
            return int(await self._redis.incr(key))
        except Exception:
            logger.exception("RedisCache.incr(%s) failed", key)
            return 0

    async def expire(self, key: str, seconds: int) -> None:
        if self._redis is None:
            return
        try:
            await self._redis.expire(key, seconds)
        except Exception:
            logger.exception("RedisCache.expire(%s) failed", key)

    async def delete_pattern(self, pattern: str) -> None:
        """Delete all keys matching a glob pattern (use sparingly — O(N) scan)."""
        if self._redis is None:
            return
        try:
            keys = await self._redis.keys(pattern)
            if keys:
                await self._redis.delete(*keys)
        except Exception:
            logger.exception("RedisCache.delete_pattern(%s) failed", pattern)


cache = RedisCache()
