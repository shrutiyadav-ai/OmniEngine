"""
OmniEngine — RAG Retriever Node

Performs semantic memory retrieval (hybrid dense Qdrant + BM25 sparse search)
and injects relevant historical memories and context into the state.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from backend.agents.state import AgentState

logger = logging.getLogger(__name__)


async def rag_retriever_node(state: AgentState) -> dict[str, Any]:
    """
    RAG Retriever node implementation.

    Reads: `user_message`, `session_id`
    Writes: `retrieved_memories`, `context_summary`, `next_node`, `scratchpad`
    """
    logger.info("Executing RAG Retriever node for session %s", state["session_id"])

    user_message = state["user_message"]
    retrieved_memories: list[dict[str, Any]] = []
    context_summary: str | None = None

    try:
        from backend.memory.vector_store import get_vector_store

        vector_store = get_vector_store()

        results = await vector_store.search_memories(
            query=user_message,
            top_k=5,
            score_threshold=0.65,
        )

        for item in results:
            retrieved_memories.append(
                {
                    "content": item.get("content"),
                    "memory_type": item.get("memory_type", "general"),
                    "score": item.get("score", 0.0),
                }
            )

        logger.info("RAG search retrieved %d relevant memory chunks", len(retrieved_memories))

    except Exception as e:
        logger.warning("RAG retrieval skipped/failed: %s", str(e))

    # Next node: If there's a plan with tools pending, execute tools. Otherwise evaluate/respond.
    plan = state.get("current_plan", [])
    step_idx = state.get("current_step_index", 0)

    if plan and step_idx < len(plan) and plan[step_idx].get("tool"):
        next_node = "tool_executor"
    else:
        next_node = "evaluator"

    return {
        "retrieved_memories": retrieved_memories,
        "context_summary": context_summary,
        "next_node": next_node,
        "scratchpad": [
            {
                "node": "rag_retriever",
                "memories_found": len(retrieved_memories),
            }
        ],
    }
