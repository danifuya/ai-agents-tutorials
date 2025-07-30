import redis.asyncio as redis
import os
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = os.getenv("REDIS_PORT", "6379")
REDIS_DB = os.getenv("REDIS_DB", 0)
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)


class RedisService:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(RedisService, cls).__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self):
        self.r: Optional[redis.Redis] = None
        self._initialized = False

    async def initialize(self):
        """Initialize Redis connection during startup."""
        if self._initialized:
            return

        logger.info(
            f"🛠️  Creating Redis client "
            f"(host={REDIS_HOST}, port={REDIS_PORT}, "
            f"password_set={bool(REDIS_PASSWORD)})"
        )

        try:
            self.r = redis.Redis(
                host=REDIS_HOST,
                port=int(REDIS_PORT),
                db=REDIS_DB,
                password=REDIS_PASSWORD,
                decode_responses=True,
            )

            # Test the connection
            if await self.ping():
                logger.info(f"✅ Redis connected to {REDIS_HOST}:{REDIS_PORT}")
                self._initialized = True
            else:
                raise Exception("Redis ping failed")

        except Exception as e:
            logger.error(f"❌ Redis connection failed: {e}")
            raise

    def is_available(self) -> bool:
        """Check if Redis is initialized and available."""
        return self._initialized and self.r is not None

    async def close(self):
        """Close Redis connection during shutdown."""
        if self.r:
            await self.r.close()
            logger.info("Redis connection closed")

    async def ping(self) -> bool:
        """Check if Redis connection is healthy."""
        try:
            if not self.r:
                return False
            return await self.r.ping()
        except Exception as e:
            logger.error(f"Redis ping failed: {e}")
            return False

    async def get_info(self) -> dict:
        """Get Redis server info."""
        try:
            if not self.r:
                return {}
            return await self.r.info()
        except Exception as e:
            logger.error(f"Redis info failed: {e}")
            return {}

    async def get(self, key: str) -> Optional[str]:
        """Get a value from Redis by key."""
        try:
            if not self.r:
                logger.warning("Redis not initialized")
                return None
            return await self.r.get(key)
        except Exception as e:
            logger.error(f"Redis get failed for key {key}: {e}")
            return None

    async def set(
        self, key: str, value: Any, ex: Optional[int] = None, nx: bool = False
    ) -> bool:
        """Set a value in Redis with optional expiration time in seconds."""
        try:
            if not self.r:
                logger.warning("Redis not initialized")
                return False
            return await self.r.set(key, value, ex=ex, nx=nx)
        except Exception as e:
            logger.error(f"Redis set failed for key {key}: {e}")
            return False

    async def delete(self, key: str) -> int:
        """Delete a key from Redis. Returns the number of keys deleted (0 or 1)."""
        try:
            if not self.r:
                logger.warning("Redis not initialized")
                return 0
            return await self.r.delete(key)
        except Exception as e:
            logger.error(f"Redis delete failed for key {key}: {e}")
            return 0

    async def lpush(self, key: str, *values: Any) -> int:
        """Push values to the left (beginning) of a Redis list. Returns the length of the list after the operation."""
        try:
            if not self.r:
                logger.warning("Redis not initialized")
                return 0
            return await self.r.lpush(key, *values)
        except Exception as e:
            logger.error(f"Redis lpush failed for key {key}: {e}")
            return 0

    async def expire(self, key: str, time: int) -> bool:
        """Set a timeout on a Redis key. Time is in seconds."""
        try:
            if not self.r:
                logger.warning("Redis not initialized")
                return False
            return await self.r.expire(key, time)
        except Exception as e:
            logger.error(f"Redis expire failed for key {key}: {e}")
            return False

    async def lrange(self, key: str, start: int, end: int) -> list:
        """Get a range of elements from a Redis list by index."""
        try:
            if not self.r:
                logger.warning("Redis not initialized")
                return []
            return await self.r.lrange(key, start, end)
        except Exception as e:
            logger.error(f"Redis lrange failed for key {key}: {e}")
            return []
