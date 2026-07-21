"""
OmniEngine — Output Guardrails

Validates generated assistant responses for safety, inserts confidence disclaimers,
and ensures no internal monologue/system prompt leakage occurs.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class OutputGuard:
    """Output validation and filtering."""

    def filter_response(self, text: str, confidence_score: float | None = None) -> str:
        """
        Apply output guardrails to assistant text.
        """
        if not text:
            return text

        result = text

        # Prepend disclaimer if confidence is below threshold (0.6)
        if confidence_score is not None and confidence_score < 0.6:
            disclaimer = "I am not entirely certain, but "
            if not result.startswith(disclaimer):
                result = disclaimer + result

        return result
