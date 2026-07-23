"""
OmniEngine — Async Database Connection Management

Provides async SQLAlchemy engine, session factory, and FastAPI dependency
for database session injection. Uses connection pooling optimized for
high-concurrency agentic workloads.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager, suppress
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from backend.core.config import get_settings

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Module-level engine and session factory (initialized at startup)
# ---------------------------------------------------------------------------
_engine: AsyncEngine | None = None
_async_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """Return the global async engine. Raises if not initialized."""
    if _engine is None:
        raise RuntimeError("Database engine not initialized. Call init_database() first.")
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the global session factory. Raises if not initialized."""
    if _async_session_factory is None:
        raise RuntimeError("Session factory not initialized. Call init_database() first.")
    return _async_session_factory


async def init_database() -> AsyncEngine:
    """
    Initialize the async database engine and session factory.

    Called during FastAPI lifespan startup. Configures connection pooling
    based on application settings.

    Returns:
        The initialized AsyncEngine instance.
    """
    global _engine, _async_session_factory  # noqa: PLW0603

    settings = get_settings()

    logger.info(
        "Initializing database connection",
        extra={
            "pool_size": settings.db_pool_size,
            "max_overflow": settings.db_max_overflow,
            "pool_recycle": settings.db_pool_recycle,
        },
    )

    _engine = create_async_engine(
        settings.database_url,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_recycle=settings.db_pool_recycle,
        pool_pre_ping=True,  # Verify connections before checkout
        pool_timeout=30,
        echo=settings.db_echo,
        # Performance: use prepared statements cache
        connect_args={
            "prepared_statement_cache_size": 256,
            "statement_cache_size": 0,  # Disable asyncpg's statement cache (use SQLAlchemy's)
        }
        if "asyncpg" in settings.database_url
        else {},
    )

    _async_session_factory = async_sessionmaker(
        bind=_engine,
        class_=AsyncSession,
        expire_on_commit=False,  # Avoid lazy-load issues in async context
        autoflush=False,
        autocommit=False,
    )

    # Verify connectivity
    async with _engine.begin() as conn:
        await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
    logger.info("Database connection verified successfully")

    return _engine


async def close_database() -> None:
    """
    Dispose of the engine and release all connections.

    Called during FastAPI lifespan shutdown.
    """
    global _engine, _async_session_factory  # noqa: PLW0603

    if _engine is not None:
        logger.info("Closing database connection pool")
        await _engine.dispose()
        _engine = None
        _async_session_factory = None
        logger.info("Database connection pool closed")


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that provides an async database session.

    Usage in routes:
        @router.get("/items")
        async def list_items(db: AsyncSession = Depends(get_db_session)):
            ...

    The session is automatically committed on success and rolled back on error.
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            try:
                await session.commit()
            except Exception as commit_err:
                logger.warning("Database commit failed (standalone mode): %s", str(commit_err))
                with suppress(Exception):
                    await session.rollback()
        except Exception:
            with suppress(Exception):
                await session.rollback()
            raise


@asynccontextmanager
async def get_db_context() -> AsyncGenerator[AsyncSession, None]:
    """
    Context manager for database sessions outside of FastAPI request scope.

    Useful for background tasks, cron jobs, and startup operations.

    Usage:
        async with get_db_context() as db:
            result = await db.execute(...)
    """
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
