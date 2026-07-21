"""
OmniEngine — SQLAlchemy ORM Models

Defines all database models for the application. The User model is designed
to be extended with OAuth2 fields in a future version.

This module is imported by Alembic's env.py for autogenerate support.
Full implementation will be completed in Phase 3.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all ORM models with common patterns."""

    type_annotation_map = {
        dict: JSONB,
    }


class User(Base):
    """
    User model — API-key auth for v1, designed for OAuth2 extension.

    Future OAuth2 fields (commented out for v1):
        - email: str
        - hashed_password: str
        - oauth_provider: str (google, github, etc.)
        - oauth_id: str
        - avatar_url: str
        - email_verified: bool
    """

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    api_key_hash: Mapped[str] = mapped_column(
        String(128), unique=True, nullable=False, index=True
    )
    display_name: Mapped[str] = mapped_column(String(255), nullable=False, default="User")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    tier: Mapped[str] = mapped_column(
        String(20), default="free", nullable=False
    )  # free, pro, enterprise
    total_tokens_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_cost_usd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # --- Future OAuth2 extension fields ---
    email: Mapped[Optional[str]] = mapped_column(
        String(255), unique=True, nullable=True, index=True
    )
    hashed_password: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    oauth_provider: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    oauth_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    sessions: Mapped[list[Session]] = relationship(
        "Session", back_populates="user", cascade="all, delete-orphan", lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, name={self.display_name}, tier={self.tier})>"


class Session(Base):
    """Conversation session — groups messages into a single thread."""

    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(500), default="New Chat", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    model_preference: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_cost_usd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    user: Mapped[User] = relationship("User", back_populates="sessions")
    messages: Mapped[list[Message]] = relationship(
        "Message", back_populates="session", cascade="all, delete-orphan", lazy="selectin",
        order_by="Message.sequence_number",
    )
    memory_summaries: Mapped[list[MemorySummary]] = relationship(
        "MemorySummary", back_populates="session", cascade="all, delete-orphan", lazy="noload"
    )

    __table_args__ = (
        Index("idx_sessions_user_active", "user_id", "is_active"),
        Index("idx_sessions_updated", "updated_at"),
    )

    def __repr__(self) -> str:
        return f"<Session(id={self.id}, title={self.title})>"


class Message(Base):
    """Individual message within a session."""

    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # user, assistant, system, tool
    content: Mapped[str] = mapped_column(Text, nullable=False)
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)

    # Token tracking
    token_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    model_used: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    latency_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Tool call tracking
    tool_calls: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    tool_results: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Internal monologue (hidden from user)
    internal_monologue: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Attachments (images, files)
    attachments: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Safety
    safety_flags: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    confidence_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    metadata_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Relationships
    session: Mapped[Session] = relationship("Session", back_populates="messages")

    __table_args__ = (
        Index("idx_messages_session_seq", "session_id", "sequence_number"),
        Index("idx_messages_created", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<Message(id={self.id}, role={self.role}, seq={self.sequence_number})>"


class MemorySummary(Base):
    """
    Summarized memory from older conversation turns.
    Created when context window exceeds threshold.
    """

    __tablename__ = "memory_summaries"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False
    )
    summary_text: Mapped[str] = mapped_column(Text, nullable=False)
    messages_summarized: Mapped[int] = mapped_column(
        Integer, nullable=False
    )  # Count of messages this summary covers
    token_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    embedding_id: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )  # Reference to Qdrant vector
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Relationships
    session: Mapped[Session] = relationship("Session", back_populates="memory_summaries")

    __table_args__ = (Index("idx_memory_session", "session_id", "created_at"),)

    def __repr__(self) -> str:
        return f"<MemorySummary(id={self.id}, msgs={self.messages_summarized})>"


class EntityMemory(Base):
    """
    Long-term entity memory extracted from conversations.
    Persists user preferences, facts, and contextual knowledge.
    Linked to Qdrant vectors for semantic retrieval.
    """

    __tablename__ = "entity_memories"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    entity_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # person, preference, fact, instruction
    entity_key: Mapped[str] = mapped_column(
        String(255), nullable=False
    )  # e.g., "preferred_language", "user_name"
    content: Mapped[str] = mapped_column(Text, nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.5, nullable=False)
    source_session_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    embedding_id: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )  # Qdrant vector ID
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        Index("idx_entity_user_type", "user_id", "entity_type"),
        Index("idx_entity_user_key", "user_id", "entity_key"),
    )

    def __repr__(self) -> str:
        return f"<EntityMemory(id={self.id}, type={self.entity_type}, key={self.entity_key})>"


class TelemetryLog(Base):
    """
    Per-request telemetry: tokens, latency, cost, model used.
    Used for analytics dashboards and cost-cap enforcement.
    """

    __tablename__ = "telemetry_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    session_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    request_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    provider: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # openai, anthropic, google

    # Token counts
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Performance
    ttft_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # Time to first token
    total_latency_ms: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Cost
    estimated_cost_usd: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)

    # Context
    tools_used: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    safety_flags: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    __table_args__ = (
        Index("idx_telemetry_session", "session_id", "created_at"),
        Index("idx_telemetry_user", "user_id", "created_at"),
        Index("idx_telemetry_model", "model", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<TelemetryLog(id={self.id}, model={self.model}, cost=${self.estimated_cost_usd:.4f})>"
