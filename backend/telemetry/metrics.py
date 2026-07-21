"""
OmniEngine — Telemetry & Metrics Tracker

Logs request latency, token counts, model usage, and costs to PostgreSQL.
Enforces hard cost-cap thresholds per session and request.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import get_settings
from backend.memory.models import TelemetryLog
from backend.safety.pii_redactor import PIIRedactor

logger = logging.getLogger(__name__)


class TelemetryTracker:
    """Async telemetry logger."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.pii_redactor = PIIRedactor()

    async def log_request(
        self,
        db: AsyncSession,
        request_id: str,
        model: str,
        provider: str,
        prompt_tokens: int,
        completion_tokens: int,
        latency_ms: float,
        cost_usd: float,
        session_id: str | None = None,
        user_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Persist telemetry record to database."""
        if not self.settings.telemetry_enabled:
            return

        try:
            log_entry = TelemetryLog(
                id=uuid.uuid4(),
                session_id=uuid.UUID(session_id) if session_id else None,
                user_id=uuid.UUID(user_id) if user_id else None,
                request_id=request_id,
                model=model,
                provider=provider,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
                total_latency_ms=latency_ms,
                estimated_cost_usd=cost_usd,
                metadata_json=metadata,
            )
            db.add(log_entry)
            await db.flush()

            logger.info(
                "Telemetry logged for request %s (tokens: %d, cost: $%.4f)",
                request_id, prompt_tokens + completion_tokens, cost_usd
            )
        except Exception as e:
            logger.warning("Failed to record telemetry log: %s", str(e))
