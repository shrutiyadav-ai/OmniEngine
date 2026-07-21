"""
OmniEngine — Health Check Routes

Provides liveness and readiness endpoints for Kubernetes probes
and operational monitoring.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter

from backend.core.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    summary="Liveness probe",
    description="Returns 200 if the service process is alive.",
)
async def health_check() -> dict[str, str]:
    """Basic liveness check — always returns OK if the process is running."""
    settings = get_settings()
    return {
        "status": "healthy",
        "version": settings.app_version,
        "environment": settings.environment,
    }


@router.get(
    "/health/ready",
    summary="Readiness probe",
    description="Checks connectivity to PostgreSQL, Redis, and Qdrant.",
)
async def readiness_check() -> dict:
    """
    Deep readiness check.

    Verifies that all backing services are reachable:
      - PostgreSQL: Executes a simple query
      - Redis: Sends PING
      - Qdrant: Checks collection info
    """
    settings = get_settings()
    checks: dict[str, bool] = {}
    overall_healthy = True

    # --- PostgreSQL ---
    try:
        from backend.core.database import get_engine

        engine = get_engine()
        async with engine.connect() as conn:
            from sqlalchemy import text

            await conn.execute(text("SELECT 1"))
        checks["postgresql"] = True
    except Exception as e:
        logger.error("PostgreSQL readiness check failed: %s", str(e))
        checks["postgresql"] = False
        overall_healthy = False

    # --- Redis ---
    try:
        from backend.core.redis_client import get_redis

        redis = get_redis()
        await redis.ping()
        checks["redis"] = True
    except Exception as e:
        logger.error("Redis readiness check failed: %s", str(e))
        checks["redis"] = False
        overall_healthy = False

    # --- Qdrant ---
    try:
        from qdrant_client import AsyncQdrantClient

        qdrant = AsyncQdrantClient(
            host=settings.qdrant_host,
            port=settings.qdrant_port,
            timeout=5.0,
        )
        await qdrant.get_collections()
        await qdrant.close()
        checks["qdrant"] = True
    except Exception as e:
        logger.error("Qdrant readiness check failed: %s", str(e))
        checks["qdrant"] = False
        overall_healthy = False

    status_str = "healthy" if overall_healthy else "degraded"
    status_code = 200 if overall_healthy else 503

    from fastapi.responses import JSONResponse

    return JSONResponse(
        status_code=status_code,
        content={
            "status": status_str,
            "version": settings.app_version,
            "environment": settings.environment,
            "checks": checks,
        },
    )
