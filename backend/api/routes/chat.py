"""
OmniEngine — Chat SSE Streaming Route

The primary endpoint for conversational AI. Accepts a user message,
routes it through the LangGraph orchestrator, and streams tokens
back to the client via Server-Sent Events (SSE).

Flow:
  1. Validate input & authenticate
  2. Create/retrieve session
  3. Run input guardrails
  4. Invoke LangGraph orchestrator
  5. Stream tokens + tool status events
  6. Persist messages & telemetry
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select
from sse_starlette.sse import EventSourceResponse

from backend.api.dependencies import RequestCtx
from backend.api.schemas import ChatRequest, StreamEventType
from backend.core.exceptions import CostCapExceededError, SafetyViolationError
from backend.memory.models import Message, Session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["chat"])


@router.post(
    "/chat",
    summary="Send a message and receive a streamed response",
    description=(
        "Primary chat endpoint. Sends a user message through the AI pipeline "
        "and streams the response via Server-Sent Events."
    ),
    responses={
        200: {"description": "SSE stream of response tokens and events"},
        400: {"description": "Invalid request or safety violation"},
        402: {"description": "Session cost cap exceeded"},
        429: {"description": "Rate limit exceeded"},
    },
)
async def chat(
    body: ChatRequest,
    ctx: RequestCtx,
) -> EventSourceResponse:
    """
    Stream a chat response via SSE.

    The response is a stream of events with these types:
      - `token`: A text token to append to the response
      - `tool_start`: A tool invocation has begun (e.g., "Searching the web...")
      - `tool_result`: A tool has returned results
      - `thinking`: Internal processing status update
      - `cost_warning`: Session approaching cost cap
      - `metadata`: Final response metadata (model, tokens, cost)
      - `error`: An error occurred during generation
      - `done`: Stream is complete
    """
    return EventSourceResponse(
        _generate_response(body, ctx),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
            "X-Correlation-ID": ctx.correlation_id,
        },
    )


async def _generate_response(
    body: ChatRequest,
    ctx: RequestCtx,
) -> AsyncGenerator[dict, None]:
    """
    Core response generation pipeline.

    Yields SSE events as dicts with 'event' and 'data' keys.
    """
    request_start = time.perf_counter()
    user_id = uuid.uuid5(uuid.NAMESPACE_DNS, ctx.api_key)
    session_id: str | None = body.session_id
    total_tokens = 0
    model_used = "unknown"
    cost_usd = 0.0

    try:
        # =====================================================================
        # Step 1: Resolve or create session
        # =====================================================================
        if session_id:
            query = select(Session).where(
                Session.id == uuid.UUID(session_id),
                Session.user_id == user_id,
                Session.is_active.is_(True),
            )
            result = await ctx.db.execute(query)
            session = result.scalar_one_or_none()

            if session is None:
                yield _error_event("session_not_found", f"Session '{session_id}' not found.")
                return
        else:
            # Auto-create a new session
            session = Session(
                id=uuid.uuid4(),
                user_id=user_id,
                title=body.message[:80] + ("..." if len(body.message) > 80 else ""),
                model_preference=body.model_preference,
            )
            ctx.db.add(session)
            await ctx.db.flush()
            session_id = str(session.id)
            logger.info("Auto-created session", extra={"session_id": session_id})

        # =====================================================================
        # Step 2: Cost cap check
        # =====================================================================
        is_within_cap, current_cost, cap = await ctx.cost_tracker.check_cost_cap(session_id)
        if not is_within_cap:
            yield _error_event(
                "cost_cap_exceeded",
                f"Session cost cap exceeded (${current_cost:.2f}/${cap:.2f}). "
                "Please start a new session.",
            )
            return

        # Check alert threshold
        if await ctx.cost_tracker.is_alert_threshold(session_id):
            yield {
                "event": StreamEventType.COST_WARNING.value,
                "data": json.dumps({
                    "event": StreamEventType.COST_WARNING.value,
                    "data": f"Session cost at ${current_cost:.2f} of ${cap:.2f} cap.",
                    "metadata": {"current_cost": current_cost, "cap": cap},
                }),
            }

        # =====================================================================
        # Step 3: Persist user message
        # =====================================================================
        seq_result = await ctx.db.execute(
            select(func.coalesce(func.max(Message.sequence_number), 0))
            .where(Message.session_id == session.id)
        )
        next_seq = (seq_result.scalar() or 0) + 1

        user_message = Message(
            id=uuid.uuid4(),
            session_id=session.id,
            role="user",
            content=body.message,
            sequence_number=next_seq,
            attachments={"items": [a.model_dump() for a in body.attachments]}
            if body.attachments
            else None,
        )
        ctx.db.add(user_message)
        await ctx.db.flush()

        # =====================================================================
        # Step 4: Send "thinking" status
        # =====================================================================
        yield _status_event("Analyzing your request...")

        # =====================================================================
        # Step 5: Invoke the LangGraph orchestrator
        # =====================================================================
        # NOTE: The orchestrator (Phase 3) is imported dynamically to avoid
        # circular imports and to allow Phase 2 to function standalone.
        assistant_content = ""
        internal_monologue = ""
        tool_calls_log: list[dict] = []
        confidence_score: float | None = None

        try:
            from backend.agents.orchestrator import invoke_agent

            async for event in invoke_agent(
                session_id=session_id,
                user_message=body.message,
                attachments=[a.model_dump() for a in body.attachments],
                model_preference=body.model_preference,
                temperature=body.temperature,
                db_session=ctx.db,
                settings=ctx.settings,
            ):
                event_type = event.get("type", "token")

                if event_type == "token":
                    token = event.get("content", "")
                    assistant_content += token
                    yield {
                        "event": StreamEventType.TOKEN.value,
                        "data": json.dumps({
                            "event": StreamEventType.TOKEN.value,
                            "data": token,
                            "metadata": {},
                        }),
                    }

                elif event_type == "tool_start":
                    tool_name = event.get("tool_name", "unknown")
                    tool_calls_log.append({"name": tool_name, "status": "started"})
                    yield _tool_event(
                        StreamEventType.TOOL_START,
                        tool_name,
                        event.get("description", f"Using {tool_name}..."),
                    )

                elif event_type == "tool_result":
                    tool_name = event.get("tool_name", "unknown")
                    yield _tool_event(
                        StreamEventType.TOOL_RESULT,
                        tool_name,
                        "Completed",
                    )

                elif event_type == "thinking":
                    internal_monologue += event.get("content", "")
                    yield _status_event(event.get("status", "Processing..."))

                elif event_type == "metadata":
                    model_used = event.get("model", model_used)
                    total_tokens = event.get("total_tokens", 0)
                    cost_usd = event.get("cost_usd", 0.0)
                    confidence_score = event.get("confidence_score")

        except ImportError:
            # Phase 3 not yet built — generate a placeholder response
            logger.warning("LangGraph orchestrator not available — using fallback")
            yield _status_event("Generating response...")

            fallback_response = (
                "Thank you for your message. The AI orchestrator is being initialized. "
                "This is a placeholder response from the OmniEngine API layer. "
                "The full LangGraph pipeline will be available after Phase 3 deployment."
            )

            for i in range(0, len(fallback_response), 3):
                chunk = fallback_response[i : i + 3]
                assistant_content += chunk
                yield {
                    "event": StreamEventType.TOKEN.value,
                    "data": json.dumps({
                        "event": StreamEventType.TOKEN.value,
                        "data": chunk,
                        "metadata": {},
                    }),
                }

            model_used = "fallback"
            total_tokens = len(fallback_response.split())

        # =====================================================================
        # Step 6: Persist assistant message
        # =====================================================================
        assistant_message = Message(
            id=uuid.uuid4(),
            session_id=session.id,
            role="assistant",
            content=assistant_content,
            sequence_number=next_seq + 1,
            token_count=total_tokens,
            model_used=model_used,
            cost_usd=cost_usd,
            latency_ms=(time.perf_counter() - request_start) * 1000,
            tool_calls={"calls": tool_calls_log} if tool_calls_log else None,
            internal_monologue=internal_monologue or None,
            confidence_score=confidence_score,
        )
        ctx.db.add(assistant_message)

        # Update session totals
        session.total_tokens += total_tokens
        session.total_cost_usd += cost_usd

        await ctx.db.flush()

        # Update cost tracker in Redis
        if cost_usd > 0:
            await ctx.cost_tracker.add_cost(session_id, cost_usd)

        # =====================================================================
        # Step 7: Send final metadata & done
        # =====================================================================
        latency_ms = (time.perf_counter() - request_start) * 1000

        yield {
            "event": StreamEventType.METADATA.value,
            "data": json.dumps({
                "event": StreamEventType.METADATA.value,
                "data": "",
                "metadata": {
                    "session_id": session_id,
                    "message_id": str(assistant_message.id),
                    "model": model_used,
                    "total_tokens": total_tokens,
                    "cost_usd": round(cost_usd, 6),
                    "latency_ms": round(latency_ms, 2),
                    "confidence_score": confidence_score,
                },
            }),
        }

        yield {
            "event": StreamEventType.DONE.value,
            "data": json.dumps({
                "event": StreamEventType.DONE.value,
                "data": "[DONE]",
                "metadata": {"session_id": session_id},
            }),
        }

        logger.info(
            "Chat response completed",
            extra={
                "session_id": session_id,
                "model": model_used,
                "tokens": total_tokens,
                "cost_usd": cost_usd,
                "latency_ms": round(latency_ms, 2),
            },
        )

    except CostCapExceededError as e:
        yield _error_event("cost_cap_exceeded", e.message)
    except SafetyViolationError as e:
        yield _error_event("safety_violation", e.message)
    except Exception as e:
        logger.exception("Unexpected error in chat stream")
        yield _error_event(
            "internal_error",
            "An unexpected error occurred. Please try again.",
        )


# =============================================================================
# SSE Event Helpers
# =============================================================================

def _error_event(error_code: str, message: str) -> dict:
    """Create an SSE error event."""
    return {
        "event": StreamEventType.ERROR.value,
        "data": json.dumps({
            "event": StreamEventType.ERROR.value,
            "data": message,
            "metadata": {"error_code": error_code},
        }),
    }


def _status_event(status_message: str) -> dict:
    """Create an SSE thinking/status event."""
    return {
        "event": StreamEventType.THINKING.value,
        "data": json.dumps({
            "event": StreamEventType.THINKING.value,
            "data": status_message,
            "metadata": {},
        }),
    }


def _tool_event(event_type: StreamEventType, tool_name: str, description: str) -> dict:
    """Create an SSE tool event."""
    return {
        "event": event_type.value,
        "data": json.dumps({
            "event": event_type.value,
            "data": description,
            "metadata": {"tool_name": tool_name},
        }),
    }
