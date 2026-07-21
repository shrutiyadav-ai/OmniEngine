"""
OmniEngine — Context Manager

Calculates token usage of conversation history using tiktoken.
Triggers background summarization when context window exceeds 70% threshold.
Manages rolling message buffers.
"""

from __future__ import annotations

import logging
from typing import Any

import tiktoken

from backend.core.config import Settings, get_settings

logger = logging.getLogger(__name__)


class ContextManager:
    """Manages context window size, token counting, and summarization triggers."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        try:
            self._encoding = tiktoken.get_encoding("cl100k_base")
        except Exception:
            self._encoding = None

    def count_tokens(self, text: str) -> int:
        """Count tokens in a string using tiktoken."""
        if not text:
            return 0
        if self._encoding:
            return len(self._encoding.encode(text))
        # Fallback estimation (approx 4 chars per token)
        return len(text) // 4

    def count_message_tokens(self, messages: list[dict[str, Any]]) -> int:
        """Count total tokens across a list of message dicts or BaseMessages."""
        total = 0
        for msg in messages:
            if isinstance(msg, dict):
                content = msg.get("content", "")
            else:
                content = getattr(msg, "content", "")
            total += self.count_tokens(str(content)) + 4  # Overhead per message
        return total

    def should_summarize(self, total_tokens: int, max_window_tokens: int = 128_000) -> bool:
        """
        Check if total tokens exceed the summarization threshold (default: 70%).
        """
        threshold = self.settings.context_summarization_threshold
        return total_tokens >= (max_window_tokens * threshold)

    def truncate_buffer(
        self,
        messages: list[dict[str, Any]],
        max_keep: int | None = None,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """
        Split messages into (to_summarize, to_keep) based on rolling buffer size.
        """
        max_keep = max_keep or self.settings.memory_rolling_buffer_size
        if len(messages) <= max_keep:
            return [], messages

        split_idx = len(messages) - max_keep
        to_summarize = messages[:split_idx]
        to_keep = messages[split_idx:]
        return to_summarize, to_keep
