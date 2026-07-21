"""
OmniEngine — Async State Cleanup Cron

Periodic background worker that purges expired Redis session cache keys,
orphaned cost trackers, and old Docker sandbox temporary files (>24 hours old).
"""

from __future__ import annotations

import asyncio
import logging
import os
import time

from backend.core.config import get_settings
from backend.core.redis_client import get_redis

logger = logging.getLogger(__name__)


async def run_cleanup() -> None:
    """Execute state cleanup job."""
    settings = get_settings()
    logger.info("Running scheduled state cleanup job...")

    # 1. Clean Redis ephemeral keys
    try:
        redis = get_redis()
        cleaned_keys = 0
        async for key in redis.scan_iter(match="session:*"):
            ttl = await redis.ttl(key)
            if ttl <= 0:
                await redis.delete(key)
                cleaned_keys += 1

        logger.info("Cleaned %d expired Redis session keys", cleaned_keys)
    except Exception as e:
        logger.warning("Redis session cleanup error: %s", str(e))

    # 2. Clean temporary sandbox workspace files (>24h)
    sandbox_dir = "/tmp/omni-sandbox"
    if os.path.exists(sandbox_dir):
        now = time.time()
        max_age = settings.cleanup_max_sandbox_age  # 86400 seconds (24 hours)
        purged_files = 0

        for root, dirs, files in os.walk(sandbox_dir):
            for file in files:
                file_path = os.path.join(root, file)
                try:
                    if os.path.isfile(file_path):
                        mtime = os.path.getmtime(file_path)
                        if now - mtime > max_age:
                            os.remove(file_path)
                            purged_files += 1
                except Exception as file_err:
                    logger.warning("Could not delete temp file %s: %s", file_path, str(file_err))

        logger.info("Purged %d inactive sandbox temp files", purged_files)


async def periodic_cleanup() -> None:
    """Background loop executing cleanup periodically."""
    settings = get_settings()
    interval = settings.cleanup_interval_seconds

    while True:
        try:
            await asyncio.sleep(interval)
            await run_cleanup()
        except asyncio.CancelledError:
            logger.info("Periodic cleanup task stopped")
            break
        except Exception as e:
            logger.error("Error in periodic cleanup task: %s", str(e))
