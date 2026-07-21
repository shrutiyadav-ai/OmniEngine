"""
OmniEngine — Pydantic Request/Response Schemas

Defines all API data models with strict validation. These schemas serve
as the contract between the frontend and backend.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


# =============================================================================
# Enums
# =============================================================================

class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"


class StreamEventType(str, Enum):
    """SSE event types sent to the client."""
    TOKEN = "token"                    # Streamed text token
    TOOL_START = "tool_start"          # Tool invocation started
    TOOL_RESULT = "tool_result"        # Tool result received
    THINKING = "thinking"              # Internal processing status
    ERROR = "error"                    # Error during generation
    DONE = "done"                      # Generation complete
    METADATA = "metadata"              # Response metadata (cost, model, etc.)
    COST_WARNING = "cost_warning"      # Session approaching cost cap


class ModelTier(str, Enum):
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"
    REASONING = "reasoning"


# =============================================================================
# Request Models
# =============================================================================

class Attachment(BaseModel):
    """File or image attachment in a chat message."""

    model_config = ConfigDict(str_strip_whitespace=True)

    type: Literal["image", "file", "url"] = Field(
        ..., description="Type of attachment"
    )
    url: str | None = Field(
        None, description="URL or base64 data URI of the attachment"
    )
    content: str | None = Field(
        None, description="Raw text content (for files)"
    )
    filename: str | None = Field(
        None, description="Original filename", max_length=255
    )
    mime_type: str | None = Field(
        None, description="MIME type of the attachment"
    )


class ChatRequest(BaseModel):
    """Request body for the chat endpoint."""

    model_config = ConfigDict(str_strip_whitespace=True)

    session_id: str | None = Field(
        None,
        description="Existing session ID. If None, a new session is created.",
    )
    message: str = Field(
        ...,
        min_length=1,
        max_length=100_000,
        description="User's message text",
    )
    attachments: list[Attachment] = Field(
        default_factory=list,
        max_length=10,
        description="Optional file/image attachments",
    )
    model_preference: str | None = Field(
        None,
        description="Preferred model (e.g., 'gpt-4o', 'claude-sonnet-4-20250514'). Overrides auto-routing.",
    )
    stream: bool = Field(
        True,
        description="Whether to stream the response via SSE",
    )
    temperature: float | None = Field(
        None,
        ge=0.0,
        le=2.0,
        description="Sampling temperature override",
    )
    system_prompt_override: str | None = Field(
        None,
        max_length=10_000,
        description="Custom system prompt (advanced usage)",
    )


class SessionCreateRequest(BaseModel):
    """Request to create a new chat session."""

    title: str = Field(
        "New Chat",
        max_length=500,
        description="Session title",
    )
    model_preference: str | None = Field(
        None,
        description="Default model preference for this session",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional session metadata",
    )


# =============================================================================
# Response Models
# =============================================================================

class MessageResponse(BaseModel):
    """A single message in a conversation."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role: MessageRole
    content: str
    sequence_number: int
    token_count: int = 0
    model_used: str | None = None
    cost_usd: float = 0.0
    latency_ms: float | None = None
    tool_calls: dict[str, Any] | None = None
    tool_results: dict[str, Any] | None = None
    attachments: dict[str, Any] | None = None
    confidence_score: float | None = None
    created_at: datetime


class SessionResponse(BaseModel):
    """Session summary for listing."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    is_active: bool = True
    model_preference: str | None = None
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    message_count: int = 0
    created_at: datetime
    updated_at: datetime


class SessionDetailResponse(SessionResponse):
    """Session with full message history."""

    messages: list[MessageResponse] = Field(default_factory=list)


class ChatResponse(BaseModel):
    """Non-streaming chat response."""

    session_id: str
    message: MessageResponse
    metadata: dict[str, Any] = Field(default_factory=dict)


class StreamEvent(BaseModel):
    """A single SSE event sent during streaming."""

    event: StreamEventType
    data: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)

    def to_sse(self) -> str:
        """Format as an SSE string."""
        import json

        payload = json.dumps({
            "event": self.event.value,
            "data": self.data,
            "metadata": self.metadata,
        })
        return f"event: {self.event.value}\ndata: {payload}\n\n"


class ErrorResponse(BaseModel):
    """Standard error response format."""

    error: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable error message")
    details: dict[str, Any] = Field(default_factory=dict)


class HealthResponse(BaseModel):
    """Health check response."""

    status: Literal["healthy", "degraded", "unhealthy"]
    version: str
    environment: str
    checks: dict[str, bool] = Field(default_factory=dict)


class SessionListResponse(BaseModel):
    """Paginated list of sessions."""

    sessions: list[SessionResponse]
    total: int
    page: int = 1
    per_page: int = 20
