"""
OmniEngine — FastAPI Dependencies

Centralized dependency injection for database sessions, Redis clients,
authentication, and request context.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import Settings, get_settings
from backend.core.database import get_db_session
from backend.core.logging_config import correlation_id_var, generate_correlation_id
from backend.core.redis_client import CostTracker, RateLimiter, SessionCache, get_redis
from backend.core.security import RateLimitedKey

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

# =============================================================================
# Type Aliases for Clean Dependency Injection
# =============================================================================

# Database session — auto-committed on success, rolled back on error
DbSession = Annotated[AsyncSession, Depends(get_db_session)]

# Authenticated + rate-limited API key
ApiKey = RateLimitedKey

# Application settings
AppSettings = Annotated[Settings, Depends(get_settings)]


# =============================================================================
# Redis Service Dependencies
# =============================================================================


async def get_session_cache() -> SessionCache:
    """Provide a SessionCache instance backed by the global Redis pool."""
    return SessionCache(get_redis())


async def get_rate_limiter() -> RateLimiter:
    """Provide a RateLimiter instance backed by the global Redis pool."""
    return RateLimiter(get_redis())


async def get_cost_tracker() -> CostTracker:
    """Provide a CostTracker instance backed by the global Redis pool."""
    return CostTracker(get_redis())


SessionCacheDep = Annotated[SessionCache, Depends(get_session_cache)]
RateLimiterDep = Annotated[RateLimiter, Depends(get_rate_limiter)]
CostTrackerDep = Annotated[CostTracker, Depends(get_cost_tracker)]


# =============================================================================
# Request Context
# =============================================================================


class RequestContext:
    """
    Bundles request-scoped context for use in route handlers.

    Provides a single injectable object with all commonly needed services.
    """

    def __init__(
        self,
        db: AsyncSession,
        settings: Settings,
        api_key: str,
        correlation_id: str,
        session_cache: SessionCache,
        cost_tracker: CostTracker,
    ) -> None:
        self.db = db
        self.settings = settings
        self.api_key = api_key
        self.correlation_id = correlation_id
        self.session_cache = session_cache
        self.cost_tracker = cost_tracker


async def get_request_context(
    request: Request,
    db: DbSession,
    settings: AppSettings,
    api_key: ApiKey,
    session_cache: SessionCacheDep,
    cost_tracker: CostTrackerDep,
) -> AsyncGenerator[RequestContext, None]:
    """
    Build a RequestContext with correlation ID for the current request.

    Sets the correlation ID context variable for structured logging.
    """
    # Extract or generate correlation ID
    cid = request.headers.get("X-Correlation-ID", generate_correlation_id())
    correlation_id_var.set(cid)

    ctx = RequestContext(
        db=db,
        settings=settings,
        api_key=api_key,
        correlation_id=cid,
        session_cache=session_cache,
        cost_tracker=cost_tracker,
    )

    yield ctx


RequestCtx = Annotated[RequestContext, Depends(get_request_context)]
