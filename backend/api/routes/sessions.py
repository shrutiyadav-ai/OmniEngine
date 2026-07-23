"""
OmniEngine — Session Management Routes

CRUD endpoints for conversation sessions. Sessions group messages
into threads and track per-session cost and token usage.
"""

from __future__ import annotations

import logging
import uuid
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from backend.api.schemas import (
    MessageResponse,
    MessageRole,
    SessionCreateRequest,
    SessionDetailResponse,
    SessionListResponse,
    SessionResponse,
)
from backend.memory.models import Session

if TYPE_CHECKING:
    from backend.api.dependencies import RequestCtx

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])


@router.post(
    "",
    response_model=SessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new chat session",
)
async def create_session(
    body: SessionCreateRequest,
    ctx: RequestCtx,
) -> Any:
    """Create a new conversation session for the authenticated user."""
    # For v1, we use the API key as the user identifier
    # In a future version, this will resolve to a User record
    user_id = uuid.uuid5(uuid.NAMESPACE_DNS, ctx.api_key)

    session = Session(
        id=uuid.uuid4(),
        user_id=user_id,
        title=body.title,
        model_preference=body.model_preference,
        metadata_json=body.metadata if body.metadata else None,
    )

    ctx.db.add(session)
    await ctx.db.flush()  # Get the ID without committing

    logger.info(
        "Session created",
        extra={"session_id": str(session.id), "title": session.title},
    )

    return SessionResponse(
        id=session.id,
        title=session.title,
        is_active=session.is_active,
        model_preference=session.model_preference,
        total_tokens=0,
        total_cost_usd=0.0,
        message_count=0,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


@router.get(
    "",
    response_model=SessionListResponse,
    summary="List user's sessions",
)
async def list_sessions(
    ctx: RequestCtx,
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Results per page"),
    active_only: bool = Query(True, description="Filter to active sessions"),
) -> Any:
    """List all sessions for the authenticated user, newest first."""
    user_id = uuid.uuid5(uuid.NAMESPACE_DNS, ctx.api_key)

    # Build query
    query = select(Session).where(Session.user_id == user_id)
    count_query = select(func.count()).select_from(Session).where(Session.user_id == user_id)

    if active_only:
        query = query.where(Session.is_active.is_(True))
        count_query = count_query.where(Session.is_active.is_(True))

    # Get total count
    total_result = await ctx.db.execute(count_query)
    total = total_result.scalar() or 0

    # Paginate and fetch
    query = (
        query.options(selectinload(Session.messages))
        .order_by(Session.updated_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )

    result = await ctx.db.execute(query)
    sessions = result.scalars().all()

    return SessionListResponse(
        sessions=[
            SessionResponse(
                id=s.id,
                title=s.title,
                is_active=s.is_active,
                model_preference=s.model_preference,
                total_tokens=s.total_tokens,
                total_cost_usd=s.total_cost_usd,
                message_count=len(s.messages),
                created_at=s.created_at,
                updated_at=s.updated_at,
            )
            for s in sessions
        ],
        total=total,
        page=page,
        per_page=per_page,
    )


@router.get(
    "/{session_id}",
    response_model=SessionDetailResponse,
    summary="Get session with message history",
)
async def get_session(
    session_id: uuid.UUID,
    ctx: RequestCtx,
) -> Any:
    """Retrieve a session with its full message history."""
    user_id = uuid.uuid5(uuid.NAMESPACE_DNS, ctx.api_key)

    query = (
        select(Session)
        .where(Session.id == session_id, Session.user_id == user_id)
        .options(selectinload(Session.messages))
    )

    result = await ctx.db.execute(query)
    session = result.scalar_one_or_none()

    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "session_not_found",
                "message": f"Session '{session_id}' not found.",
            },
        )

    return SessionDetailResponse(
        id=session.id,
        title=session.title,
        is_active=session.is_active,
        model_preference=session.model_preference,
        total_tokens=session.total_tokens,
        total_cost_usd=session.total_cost_usd,
        message_count=len(session.messages),
        created_at=session.created_at,
        updated_at=session.updated_at,
        messages=[
            MessageResponse(
                id=m.id,
                role=MessageRole(m.role),
                content=m.content,
                sequence_number=m.sequence_number,
                token_count=m.token_count,
                model_used=m.model_used,
                cost_usd=m.cost_usd,
                latency_ms=m.latency_ms,
                tool_calls=m.tool_calls,
                tool_results=m.tool_results,
                attachments=m.attachments,
                confidence_score=m.confidence_score,
                created_at=m.created_at,
            )
            for m in sorted(session.messages, key=lambda x: x.sequence_number)
        ],
    )


@router.delete(
    "/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete a session",
)
async def delete_session(
    session_id: uuid.UUID,
    ctx: RequestCtx,
) -> None:
    """
    Soft-delete a session by setting is_active=False.

    The session data is preserved for analytics but hidden from the user.
    """
    user_id = uuid.uuid5(uuid.NAMESPACE_DNS, ctx.api_key)

    query = select(Session).where(
        Session.id == session_id,
        Session.user_id == user_id,
    )

    result = await ctx.db.execute(query)
    session = result.scalar_one_or_none()

    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "session_not_found",
                "message": f"Session '{session_id}' not found.",
            },
        )

    session.is_active = False
    await ctx.db.flush()

    # Clean up Redis cache
    try:
        await ctx.session_cache.delete(str(session_id))
        await ctx.cost_tracker.reset(str(session_id))
    except Exception:
        logger.warning("Failed to clean Redis state for session %s", session_id)

    logger.info("Session soft-deleted", extra={"session_id": str(session_id)})


@router.patch(
    "/{session_id}/title",
    response_model=SessionResponse,
    summary="Update session title",
)
async def update_session_title(
    session_id: uuid.UUID,
    ctx: RequestCtx,
    title: str = Query(..., min_length=1, max_length=500),
) -> Any:
    """Update the title of an existing session."""
    user_id = uuid.uuid5(uuid.NAMESPACE_DNS, ctx.api_key)

    query = select(Session).where(
        Session.id == session_id,
        Session.user_id == user_id,
    )

    result = await ctx.db.execute(query)
    session = result.scalar_one_or_none()

    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "session_not_found",
                "message": f"Session '{session_id}' not found.",
            },
        )

    session.title = title
    await ctx.db.flush()

    return SessionResponse(
        id=session.id,
        title=session.title,
        is_active=session.is_active,
        model_preference=session.model_preference,
        total_tokens=session.total_tokens,
        total_cost_usd=session.total_cost_usd,
        message_count=len(session.messages) if session.messages else 0,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )
