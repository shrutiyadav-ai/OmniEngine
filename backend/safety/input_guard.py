"""
OmniEngine — Input Guardrails

Detects prompt injection attempts, jailbreak pattern signatures,
and content policy violations in user messages.
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

# Common prompt injection pattern signatures
INJECTION_PATTERNS = [
    r"ignore (all )?previous instructions",
    r"disregard (all )?prior directives",
    r"you are now (an )?unrestricted",
    r"DAN mode",
    r"bypass safety protocols",
    r"system prompt leakage",
    r"do anything now",
    r"jailbreak mode",
]


class InputGuard:
    """Input moderation and prompt injection detection."""

    def __init__(self) -> None:
        self._compiled_patterns = [re.compile(p, re.IGNORECASE) for p in INJECTION_PATTERNS]

    def check_prompt_injection(self, text: str) -> tuple[bool, str | None]:
        """
        Check if text contains known prompt injection signatures.

        Returns:
            Tuple of (is_injection, pattern_matched)
        """
        if not text:
            return False, None

        for pattern in self._compiled_patterns:
            match = pattern.search(text)
            if match:
                logger.warning("Prompt injection signature detected: %s", match.group(0))
                return True, match.group(0)

        return False, None
