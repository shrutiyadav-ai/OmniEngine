"""
OmniEngine — Custom Exception Hierarchy

Defines domain-specific exceptions and global FastAPI exception handlers.
All exceptions carry structured error codes for API responses.
"""

from __future__ import annotations

import logging
import traceback
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


# =============================================================================
# Base Exception
# =============================================================================

class OmniEngineError(Exception):
    """Base exception for all OmniEngine errors."""

    def __init__(
        self,
        message: str,
        error_code: str = "internal_error",
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details or {}


# =============================================================================
# Domain-Specific Exceptions
# =============================================================================

class ModelRoutingError(OmniEngineError):
    """Raised when model selection or fallback chain exhaustion occurs."""

    def __init__(
        self,
        message: str = "Unable to route to a suitable model",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            error_code="model_routing_error",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            details=details,
        )


class ToolExecutionError(OmniEngineError):
    """Raised when a tool invocation fails after retries."""

    def __init__(
        self,
        tool_name: str,
        message: str = "Tool execution failed",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=f"Tool '{tool_name}' failed: {message}",
            error_code="tool_execution_error",
            status_code=status.HTTP_502_BAD_GATEWAY,
            details={**(details or {}), "tool_name": tool_name},
        )


class SafetyViolationError(OmniEngineError):
    """Raised when input or output fails safety checks."""

    def __init__(
        self,
        violation_type: str = "content_policy",
        message: str = "Content violates safety policies",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            message=message,
            error_code="safety_violation",
            status_code=status.HTTP_400_BAD_REQUEST,
            details={**(details or {}), "violation_type": violation_type},
        )


class CostCapExceededError(OmniEngineError):
    """Raised when a session exceeds its cost budget."""

    def __init__(
        self,
        session_id: str,
        current_cost: float,
        cap: float,
    ) -> None:
        super().__init__(
            message=(
                f"Session cost cap exceeded. Current: ${current_cost:.4f}, "
                f"Cap: ${cap:.2f}. Workflow terminated."
            ),
            error_code="cost_cap_exceeded",
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            details={
                "session_id": session_id,
                "current_cost_usd": current_cost,
                "cap_usd": cap,
            },
        )


class SessionNotFoundError(OmniEngineError):
    """Raised when a session ID does not exist."""

    def __init__(self, session_id: str) -> None:
        super().__init__(
            message=f"Session '{session_id}' not found",
            error_code="session_not_found",
            status_code=status.HTTP_404_NOT_FOUND,
            details={"session_id": session_id},
        )


class ContextWindowExceededError(OmniEngineError):
    """Raised when context exceeds model limits even after summarization."""

    def __init__(
        self,
        model: str,
        token_count: int,
        max_tokens: int,
    ) -> None:
        super().__init__(
            message=f"Context window exceeded for {model}: {token_count}/{max_tokens} tokens",
            error_code="context_window_exceeded",
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            details={
                "model": model,
                "token_count": token_count,
                "max_tokens": max_tokens,
            },
        )


class AgentRecursionError(OmniEngineError):
    """Raised when LangGraph agent loop hits recursion limit."""

    def __init__(self, limit: int, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            message=f"Agent workflow exceeded recursion limit of {limit}",
            error_code="agent_recursion_limit",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details={**(details or {}), "recursion_limit": limit},
        )


# =============================================================================
# Global Exception Handlers
# =============================================================================

def register_exception_handlers(app: FastAPI) -> None:
    """Register global exception handlers with the FastAPI application."""

    @app.exception_handler(OmniEngineError)
    async def omni_engine_error_handler(
        request: Request,
        exc: OmniEngineError,
    ) -> JSONResponse:
        """Handle all OmniEngine domain exceptions."""
        logger.error(
            "OmniEngine error: %s",
            exc.message,
            extra={
                "error_code": exc.error_code,
                "status_code": exc.status_code,
                "details": exc.details,
                "path": str(request.url),
            },
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.error_code,
                "message": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(ValueError)
    async def value_error_handler(
        request: Request,
        exc: ValueError,
    ) -> JSONResponse:
        """Handle validation errors."""
        logger.warning("Validation error: %s", str(exc), extra={"path": str(request.url)})
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": "validation_error",
                "message": str(exc),
                "details": {},
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        """Catch-all for unexpected errors. Never expose internals to clients."""
        logger.critical(
            "Unhandled exception: %s",
            str(exc),
            extra={
                "path": str(request.url),
                "traceback": traceback.format_exc(),
            },
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "internal_error",
                "message": "An unexpected error occurred. Please try again.",
                "details": {},
            },
        )
