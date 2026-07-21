"""
OmniEngine — FastAPI Application Factory

Entry point for the backend API. Manages the application lifecycle:
  - Startup: Initialize database, Redis, Qdrant, logging
  - Runtime: Route requests, stream responses, enforce guardrails
  - Shutdown: Gracefully close connections

Run with:
    uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from backend.core.config import get_settings
from backend.core.exceptions import register_exception_handlers
from backend.core.logging_config import (
    configure_logging,
    correlation_id_var,
    generate_correlation_id,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan manager.

    Startup: Initialize all connections and services.
    Shutdown: Gracefully close all connections.
    """
    logger = logging.getLogger(__name__)

    # =========================================================================
    # STARTUP
    # =========================================================================
    logger.info("Starting OmniEngine...")

    # Initialize database
    from backend.core.database import close_database, init_database

    try:
        await init_database()
        logger.info("✓ PostgreSQL connected")
    except Exception as e:
        logger.error("✗ PostgreSQL connection failed: %s", str(e))
        raise

    # Initialize Redis
    from backend.core.redis_client import close_redis, init_redis

    try:
        await init_redis()
        logger.info("✓ Redis connected")
    except Exception as e:
        logger.warning("✗ Redis connection failed (non-fatal): %s", str(e))

    # Initialize Qdrant collection
    settings = get_settings()
    try:
        from qdrant_client import AsyncQdrantClient
        from qdrant_client.models import Distance, VectorParams

        qdrant = AsyncQdrantClient(
            host=settings.qdrant_host,
            port=settings.qdrant_port,
        )
        collections = await qdrant.get_collections()
        collection_names = [c.name for c in collections.collections]

        if settings.qdrant_collection_name not in collection_names:
            await qdrant.create_collection(
                collection_name=settings.qdrant_collection_name,
                vectors_config=VectorParams(
                    size=settings.qdrant_embedding_dim,
                    distance=Distance.COSINE,
                ),
            )
            logger.info(
                "✓ Qdrant collection '%s' created",
                settings.qdrant_collection_name,
            )
        else:
            logger.info(
                "✓ Qdrant collection '%s' exists",
                settings.qdrant_collection_name,
            )

        await qdrant.close()
    except Exception as e:
        logger.warning("✗ Qdrant initialization failed (non-fatal): %s", str(e))

    # Start background cleanup task
    import asyncio

    cleanup_task: asyncio.Task | None = None
    if settings.cleanup_interval_seconds > 0:
        try:
            from backend.core.cleanup import periodic_cleanup

            cleanup_task = asyncio.create_task(periodic_cleanup())
            logger.info("✓ Background cleanup task started")
        except ImportError:
            logger.info("⊘ Cleanup module not yet available (Phase 4)")

    logger.info(
        "OmniEngine started successfully (env=%s, version=%s)",
        settings.environment,
        settings.app_version,
    )

    # =========================================================================
    # YIELD — Application is running
    # =========================================================================
    yield

    # =========================================================================
    # SHUTDOWN
    # =========================================================================
    logger.info("Shutting down OmniEngine...")

    # Cancel cleanup task
    if cleanup_task is not None:
        cleanup_task.cancel()
        try:
            await cleanup_task
        except asyncio.CancelledError:
            pass

    await close_redis()
    await close_database()

    logger.info("OmniEngine shut down gracefully")


def create_app() -> FastAPI:
    """
    Application factory — creates and configures the FastAPI instance.

    Returns:
        A fully configured FastAPI application.
    """
    # Configure structured logging first
    configure_logging()

    settings = get_settings()

    app = FastAPI(
        title="OmniEngine API",
        description=(
            "Production-grade multi-model multi-agent conversational AI system. "
            "Supports streaming chat via SSE, session management, and tool-augmented responses."
        ),
        version=settings.app_version,
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        openapi_url="/openapi.json" if not settings.is_production else None,
        lifespan=lifespan,
    )

    # =========================================================================
    # Middleware
    # =========================================================================

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=[
            "X-Correlation-ID",
            "X-RateLimit-Remaining",
            "X-RateLimit-Reset",
        ],
    )

    # GZip compression for responses > 500 bytes
    app.add_middleware(GZipMiddleware, minimum_size=500)

    # Correlation ID middleware
    @app.middleware("http")
    async def correlation_id_middleware(request: Request, call_next) -> Response:
        """Inject correlation ID into request/response cycle."""
        cid = request.headers.get("X-Correlation-ID", generate_correlation_id())
        correlation_id_var.set(cid)

        response: Response = await call_next(request)
        response.headers["X-Correlation-ID"] = cid

        # Inject rate limit headers if available
        remaining = getattr(request.state, "rate_limit_remaining", None)
        if remaining is not None:
            response.headers["X-RateLimit-Remaining"] = str(remaining)
            response.headers["X-RateLimit-Reset"] = str(
                getattr(request.state, "rate_limit_reset", 60)
            )

        return response

    # =========================================================================
    # Exception Handlers
    # =========================================================================
    register_exception_handlers(app)

    # =========================================================================
    # Routes
    # =========================================================================
    from backend.api.routes.chat import router as chat_router
    from backend.api.routes.health import router as health_router
    from backend.api.routes.sessions import router as sessions_router

    app.include_router(health_router)
    app.include_router(chat_router)
    app.include_router(sessions_router)

    return app


# ---------------------------------------------------------------------------
# Module-level app instance for uvicorn
# ---------------------------------------------------------------------------
app = create_app()


def run() -> None:
    """Entry point for the `omni-server` console script."""
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=not settings.is_production,
        log_level=settings.log_level.lower(),
        access_log=True,
        proxy_headers=True,
        forwarded_allow_ips="*",
    )
