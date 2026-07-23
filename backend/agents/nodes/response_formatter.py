"""
OmniEngine — Response Formatter Node

Synthesizes plan results, retrieved memories, and user prompt into a polished,
markdown-formatted response. Generates streamed tokens.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from langchain_core.messages import HumanMessage, SystemMessage

from backend.agents.model_router import ModelRouter
from backend.agents.prompts import MEMORY_CONTEXT_TEMPLATE, RESPONSE_FORMATTER_PROMPT

if TYPE_CHECKING:
    from backend.agents.state import AgentState

logger = logging.getLogger(__name__)


async def response_formatter_node(state: AgentState) -> dict[str, Any]:
    """
    Response Formatter node implementation.

    Reads: `user_message`, `current_plan`, `retrieved_memories`, `confidence_score`
    Writes: `internal_monologue`, `is_done`, `scratchpad`
    """
    logger.info("Executing Response Formatter node for session %s", state["session_id"])

    user_message = state["user_message"]
    plan = state.get("current_plan", [])
    memories = state.get("retrieved_memories", [])
    confidence_score = state.get("confidence_score", 0.85)

    # Format memories context
    memory_text = ""
    if memories:
        formatted_m = [f"- [{m.get('memory_type')}] {m.get('content')}" for m in memories]
        memory_text = MEMORY_CONTEXT_TEMPLATE.format(memories="\n".join(formatted_m))

    # Format execution results
    results_text = ""
    if plan:
        completed = [
            f"Task: {s.get('description')}\nResult: {s.get('result')}"
            for s in plan
            if s.get("result")
        ]
        results_text = "\n\n".join(completed)

    disclaimer_prefix = ""
    if confidence_score is not None and confidence_score < 0.6:
        disclaimer_prefix = "I am not entirely certain, but "

    full_context = f"{memory_text}\nUser Query: {user_message}\n\nExecution Data:\n{results_text}"
    if disclaimer_prefix:
        full_context += f"\nNote: Low confidence score ({confidence_score}). Prepend disclaimer."

    router = ModelRouter()
    tier = state.get("model_tier", "medium")
    spec = router.select_model(tier=tier, preference=state.get("model_preference"))
    llm = router.create_llm(spec, temperature=state.get("temperature", 0.7), streaming=True)

    prompt = [
        SystemMessage(content=RESPONSE_FORMATTER_PROMPT),
        HumanMessage(content=full_context),
    ]

    try:
        # Note: In full streaming execution, tokens are yielded via callback/generator
        response = await llm.ainvoke(prompt)
        final_content = (
            response.content if isinstance(response.content, str) else str(response.content)
        )

        return {
            "internal_monologue": f"Formatted final output using model {spec.name} (tier: {tier}).",
            "model_used": spec.name,
            "is_done": True,
            "scratchpad": [
                {
                    "node": "response_formatter",
                    "model_used": spec.name,
                    "length": len(final_content),
                }
            ],
        }

    except Exception as e:
        logger.error("Response Formatter failed: %s", str(e))
        return {
            "internal_monologue": f"Formatting error: {e!s}",
            "is_done": True,
            "scratchpad": [
                {
                    "node": "response_formatter",
                    "error": str(e),
                }
            ],
        }
