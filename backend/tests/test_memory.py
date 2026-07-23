"""
Unit tests for context window management and token counting.
"""

from backend.memory.context_manager import ContextManager


def test_token_counting() -> None:
    """Test token counting accuracy."""
    cm = ContextManager()
    count = cm.count_tokens("Hello world, this is a test prompt.")
    assert count > 0

    msg_count = cm.count_message_tokens(
        [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there!"},
        ]
    )
    assert msg_count > 10


def test_summarization_threshold_trigger() -> None:
    """Test context summarization 70% threshold calculation."""
    cm = ContextManager()
    assert cm.should_summarize(90_000, max_window_tokens=128_000) is True
    assert cm.should_summarize(10_000, max_window_tokens=128_000) is False


def test_rolling_buffer_truncation() -> None:
    """Test message buffer truncation for rolling memory."""
    cm = ContextManager()
    messages = [{"role": "user", "content": f"msg {i}"} for i in range(25)]

    to_summarize, to_keep = cm.truncate_buffer(messages, max_keep=20)
    assert len(to_summarize) == 5
    assert len(to_keep) == 20
