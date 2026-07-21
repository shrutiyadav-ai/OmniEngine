"""
Unit tests for API Pydantic schemas.
"""

import pytest
from pydantic import ValidationError

from backend.api.schemas import ChatRequest, SessionCreateRequest, MessageRole, StreamEvent, StreamEventType


def test_chat_request_validation():
    """Test valid and invalid ChatRequest payloads."""
    req = ChatRequest(message="Hello world", model_preference="gpt-4o")
    assert req.message == "Hello world"
    assert req.model_preference == "gpt-4o"
    assert req.stream is True

    with pytest.raises(ValidationError):
        ChatRequest(message="")  # Empty message disallowed


def test_session_create_validation():
    """Test SessionCreateRequest schema defaults."""
    req = SessionCreateRequest()
    assert req.title == "New Chat"
    assert req.model_preference is None


def test_stream_event_sse_formatting():
    """Test StreamEvent to SSE string serialization."""
    event = StreamEvent(
        event=StreamEventType.TOKEN,
        data="Hello",
        metadata={"step": 1},
    )
    sse = event.to_sse()
    assert "event: token" in sse
    assert '"data": "Hello"' in sse
