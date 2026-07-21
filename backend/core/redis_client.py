"""
OmniEngine — Async Redis Client

Provides Redis connection management for:
  - Session state caching (ephemeral, TTL-based)
  - Rate limiting (sliding window)
  - PubSub for real-time events
  - Cost tracking accumulation per session
"""

from __future__ import annotations

import json
import logging
from typing import Any

import redis.asyncio as aioredis

from backend.core.config import get_settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level Redis pool
# ---------------------------------------------------------------------------
_redis_pool: aioredis.Redis | None = None


def get_redis() -> aioredis.Redis:
    """Return the global Redis client. Raises if not initialized."""
    if _redis_pool is None:
        raise RuntimeError(
            "Redis not initialized. Call init_redis() first."
        )
    return _redis_pool


async def init_redis() -> aioredis.Redis:
    """
    Initialize the async Redis connection pool.

    Called during FastAPI lifespan startup.
    """
    global _redis_pool  # noqa: PLW0603

    settings = get_settings()
    logger.info("Initializing Redis connection", extra={"url": settings.redis_url.split("@")[-1]})

    _redis_pool = aioredis.from_url(
        settings.redis_url,
        decode_responses=True,
        max_connections=50,
        retry_on_timeout=True,
        socket_timeout=5.0,
        socket_connect_timeout=5.0,
        health_check_interval=30,
    )

    # Verify connectivity
    await _redis_pool.ping()
    logger.info("Redis connection verified successfully")

    return _redis_pool


async def close_redis() -> None:
    """Close the Redis connection pool. Called during shutdown."""
    global _redis_pool  # noqa: PLW0603

    if _redis_pool is not None:
        logger.info("Closing Redis connection pool")
        await _redis_pool.aclose()
        _redis_pool = None
        logger.info("Redis connection pool closed")


# =============================================================================
# Session Cache Operations
# =============================================================================

class SessionCache:
    """Redis-backed session state cache with TTL management."""

    PREFIX = "session:"

    def __init__(self, redis: aioredis.Redis) -> None:
        self._redis = redis
        self._settings = get_settings()

    def _key(self, session_id: str) -> str:
        return f"{self.PREFIX}{session_id}"

    async def get(self, session_id: str) -> dict[str, Any] | None:
        """Retrieve cached session state."""
        data = await self._redis.get(self._key(session_id))
        if data is None:
            return None
        return json.loads(data)

    async def set(
        self,
        session_id: str,
        state: dict[str, Any],
        ttl: int | None = None,
    ) -> None:
        """Store session state with TTL (default from settings)."""
        ttl = ttl or self._settings.redis_session_ttl
        await self._redis.set(
            self._key(session_id),
            json.dumps(state, default=str),
            ex=ttl,
        )

    async def delete(self, session_id: str) -> None:
        """Remove session from cache."""
        await self._redis.delete(self._key(session_id))

    async def exists(self, session_id: str) -> bool:
        """Check if session exists in cache."""
        return bool(await self._redis.exists(self._key(session_id)))

    async def touch(self, session_id: str) -> None:
        """Reset TTL on an active session."""
        await self._redis.expire(
            self._key(session_id),
            self._settings.redis_session_ttl,
        )

    async def get_all_session_keys(self) -> list[str]:
        """List all active session keys (for cleanup)."""
        keys: list[str] = []
        async for key in self._redis.scan_iter(match=f"{self.PREFIX}*", count=100):
            keys.append(key)
        return keys


# =============================================================================
# Rate Limiter (Sliding Window)
# =============================================================================

class RateLimiter:
    """Redis-based sliding window rate limiter."""

    PREFIX = "ratelimit:"

    def __init__(self, redis: aioredis.Redis) -> None:
        self._redis = redis
        self._settings = get_settings()

    async def check_rate_limit(
        self,
        identifier: str,
        max_requests: int | None = None,
        window_seconds: int = 60,
    ) -> tuple[bool, int, int]:
        """
        Check if the identifier is within rate limits.

        Args:
            identifier: The API key or user ID to rate limit.
            max_requests: Maximum requests per window. Defaults to RATE_LIMIT_RPM.
            window_seconds: Size of the sliding window in seconds.

        Returns:
            Tuple of (is_allowed, remaining_requests, reset_seconds).
        """
        import time

        max_requests = max_requests or self._settings.rate_limit_rpm
        key = f"{self.PREFIX}{identifier}"
        now = time.time()
        window_start = now - window_seconds

        pipe = self._redis.pipeline()
        # Remove expired entries
        pipe.zremrangebyscore(key, "-inf", window_start)
        # Count current requests
        pipe.zcard(key)
        # Add current request
        pipe.zadd(key, {str(now): now})
        # Set expiry on the key
        pipe.expire(key, window_seconds)

        results = await pipe.execute()
        current_count = results[1]  # zcard result

        is_allowed = current_count < max_requests
        remaining = max(0, max_requests - current_count - 1)
        reset_seconds = window_seconds

        if not is_allowed:
            # Remove the request we just added since it's denied
            await self._redis.zrem(key, str(now))
            remaining = 0

        return is_allowed, remaining, reset_seconds


# =============================================================================
# Cost Tracker
# =============================================================================

class CostTracker:
    """
    Redis-backed per-session cost accumulator for cost-cap enforcement.

    Tracks cumulative cost per session. If the cost exceeds the configured
    cap, the agent workflow is forcefully terminated.
    """

    PREFIX = "cost:"

    def __init__(self, redis: aioredis.Redis) -> None:
        self._redis = redis
        self._settings = get_settings()

    def _key(self, session_id: str) -> str:
        return f"{self.PREFIX}{session_id}"

    async def add_cost(self, session_id: str, cost_usd: float) -> float:
        """
        Add cost to a session's running total.

        Returns:
            The new cumulative cost for the session.
        """
        new_total = await self._redis.incrbyfloat(self._key(session_id), cost_usd)
        # Set TTL if this is the first cost entry
        ttl = await self._redis.ttl(self._key(session_id))
        if ttl == -1:  # No TTL set
            await self._redis.expire(
                self._key(session_id), self._settings.redis_session_ttl
            )
        return float(new_total)

    async def get_cost(self, session_id: str) -> float:
        """Get the current cumulative cost for a session."""
        cost = await self._redis.get(self._key(session_id))
        return float(cost) if cost else 0.0

    async def check_cost_cap(self, session_id: str) -> tuple[bool, float, float]:
        """
        Check if session has exceeded its cost cap.

        Returns:
            Tuple of (is_within_cap, current_cost, cap_limit).
        """
        current = await self.get_cost(session_id)
        cap = self._settings.session_cost_cap_usd
        return current <= cap, current, cap

    async def is_alert_threshold(self, session_id: str) -> bool:
        """Check if session cost has reached the alert threshold."""
        current = await self.get_cost(session_id)
        cap = self._settings.session_cost_cap_usd
        threshold = self._settings.cost_alert_threshold
        return current >= (cap * threshold)

    async def reset(self, session_id: str) -> None:
        """Reset cost tracking for a session."""
        await self._redis.delete(self._key(session_id))
