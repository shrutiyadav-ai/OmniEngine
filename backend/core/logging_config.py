"""
OmniEngine — Structured Logging Configuration

Configures structured JSON logging using structlog for production
and human-readable colored output for development.
Includes correlation ID propagation for request tracing.
"""

from __future__ import annotations

import logging
import sys
import uuid
from contextvars import ContextVar
from typing import Any

import structlog

from backend.core.config import get_settings

# Context variable for request correlation ID
correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="")


def add_correlation_id(
    logger: Any,  # noqa: ARG001
    method_name: str,  # noqa: ARG001
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """Inject correlation ID into every log entry."""
    cid = correlation_id_var.get("")
    if cid:
        event_dict["correlation_id"] = cid
    return event_dict


def add_app_info(
    logger: Any,  # noqa: ARG001
    method_name: str,  # noqa: ARG001
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """Add application metadata to log entries."""
    settings = get_settings()
    event_dict["service"] = "omniengine"
    event_dict["environment"] = settings.environment
    return event_dict


def generate_correlation_id() -> str:
    """Generate a new correlation ID for request tracing."""
    return str(uuid.uuid4())


def configure_logging() -> None:
    """
    Configure structured logging for the application.

    - Development: Colored, human-readable console output
    - Production: JSON-formatted output for log aggregation (ELK, Datadog, etc.)
    """
    settings = get_settings()
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    # Shared processors for both structlog and stdlib
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        add_correlation_id,
    ]

    if settings.is_production:
        # Production: JSON output
        shared_processors.extend(
            [
                add_app_info,
                structlog.processors.format_exc_info,
                structlog.processors.UnicodeDecoder(),
            ]
        )

        structlog.configure(
            processors=[
                *shared_processors,
                structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
            ],
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )

        formatter = structlog.stdlib.ProcessorFormatter(
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                structlog.processors.JSONRenderer(),
            ],
        )
    else:
        # Development: Colored console output
        structlog.configure(
            processors=[
                *shared_processors,
                structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
            ],
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )

        formatter = structlog.stdlib.ProcessorFormatter(
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                structlog.dev.ConsoleRenderer(colors=True),
            ],
        )

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove existing handlers to avoid duplicates
    root_logger.handlers.clear()

    # Add structured handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)

    # Quiet noisy third-party loggers
    for noisy_logger in [
        "uvicorn.access",
        "httpx",
        "httpcore",
        "hpack",
        "sqlalchemy.engine",
        "sqlalchemy.pool",
        "asyncio",
        "urllib3",
    ]:
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)

    # Uvicorn loggers — integrate with structlog
    for uvicorn_logger_name in ["uvicorn", "uvicorn.error"]:
        uv_logger = logging.getLogger(uvicorn_logger_name)
        uv_logger.handlers.clear()
        uv_logger.addHandler(handler)
        uv_logger.setLevel(log_level)

    logging.getLogger(__name__).info(
        "Logging configured",
        extra={
            "level": settings.log_level,
            "format": "json" if settings.is_production else "console",
        },
    )
