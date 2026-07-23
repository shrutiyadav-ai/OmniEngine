"""
OmniEngine — Security Module

Implements API-key authentication with rate limiting.
Designed to be extended with JWT/OAuth2 in future versions.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
from typing import Annotated

from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import APIKeyHeader

from backend.core.config import Settings, get_settings
from backend.core.redis_client import RateLimiter, get_redis

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# API Key Security Scheme
# ---------------------------------------------------------------------------
api_key_header = APIKeyHeader(
    name="X-API-Key",
    scheme_name="API Key",
    description="API key for authentication. Pass via X-API-Key header.",
    auto_error=False,
)


def hash_api_key(api_key: str) -> str:
    """
    Hash an API key for secure storage.

    Uses SHA-256 with a consistent salt derived from the secret key.
    """
    settings = get_settings()
    return hashlib.sha256(f"{settings.api_secret_key}:{api_key}".encode()).hexdigest()


def generate_api_key(prefix: str = "omni") -> str:
    """Generate a new secure API key."""
    random_part = secrets.token_urlsafe(32)
    return f"{prefix}_{random_part}"


def verify_api_key(provided_key: str, stored_hash: str) -> bool:
    """Constant-time comparison of API key against stored hash."""
    computed_hash = hash_api_key(provided_key)
    return hmac.compare_digest(computed_hash, stored_hash)


# ---------------------------------------------------------------------------
# Authentication Dependencies
# ---------------------------------------------------------------------------


async def authenticate_api_key(
    request: Request,
    api_key: str | None = Security(api_key_header),
    settings: Settings = Depends(get_settings),
) -> str:
    """
    Validate the API key from the X-API-Key header.

    For v1, we check against a configured list of valid API keys.
    In a future version, this will look up keys in the database.

    Returns:
        The validated API key identifier.

    Raises:
        HTTPException(401): If no API key is provided.
        HTTPException(403): If the API key is invalid.
    """
    if api_key is None:
        # Also check query params for SSE connections (EventSource can't set headers)
        api_key = request.query_params.get("api_key")

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "authentication_required",
                "message": "API key is required. Provide it via the X-API-Key header.",
            },
        )

    # Validate against configured keys
    valid_keys = settings.api_key_list
    if api_key not in valid_keys:
        logger.warning(
            "Invalid API key attempt",
            extra={"key_prefix": api_key[:8] + "..." if len(api_key) > 8 else "***"},
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "invalid_api_key",
                "message": "The provided API key is invalid or revoked.",
            },
        )

    return api_key


async def enforce_rate_limit(
    request: Request,
    api_key: str = Depends(authenticate_api_key),
) -> str:
    """
    Enforce rate limiting after successful authentication.

    Injects rate limit headers into the response.

    Returns:
        The authenticated API key.

    Raises:
        HTTPException(429): If rate limit is exceeded.
    """
    try:
        redis = get_redis()
        limiter = RateLimiter(redis)
        is_allowed, remaining, reset_seconds = await limiter.check_rate_limit(api_key)
    except RuntimeError:
        # Redis not available — fail open in development, fail closed in production
        settings = get_settings()
        if settings.is_production:
            logger.error("Redis unavailable for rate limiting in production")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "error": "service_unavailable",
                    "message": "Rate limiting service is temporarily unavailable.",
                },
            ) from None
        logger.warning("Redis unavailable — rate limiting disabled")
        return api_key

    # Inject rate limit headers into the response
    request.state.rate_limit_remaining = remaining
    request.state.rate_limit_reset = reset_seconds

    if not is_allowed:
        logger.warning(
            "Rate limit exceeded",
            extra={"api_key_prefix": api_key[:8] + "..."},
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "rate_limit_exceeded",
                "message": "Rate limit exceeded. Please slow down.",
                "retry_after_seconds": reset_seconds,
            },
            headers={
                "Retry-After": str(reset_seconds),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(reset_seconds),
            },
        )

    return api_key


# Type aliases for dependency injection
AuthenticatedKey = Annotated[str, Depends(authenticate_api_key)]
RateLimitedKey = Annotated[str, Depends(enforce_rate_limit)]
