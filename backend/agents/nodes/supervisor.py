"""
OmniEngine — Supervisor Node

Analyzes user intent, assesses task complexity, determines tool requirements,
and routes the workflow to either direct generation or plan decomposition.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.messages import SystemMessage, HumanMessage

from backend.agents.model_router import ModelRouter
from backend.agents.prompts import SUPERVISOR_PROMPT
from backend.agents.state import AgentState

logger = logging.getLogger(__name__)


async def supervisor_node(state: AgentState) -> dict[str, Any]:
    """
    Supervisor node implementation.

    Reads: `user_message`, `attachments`, `model_preference`
    Writes: `model_tier`, `active_tools`, `next_node`, `scratchpad`
    """
    logger.info("Executing Supervisor node for session %s", state["session_id"])

    user_message = state["user_message"]
    attachments = state.get("attachments", [])
    model_preference = state.get("model_preference")

    # Determine if vision capability is needed
    needs_vision = any(a.get("type") == "image" for a in attachments)

    router = ModelRouter()
    # Use small model for fast intent analysis
    spec = router.select_model(tier="small", preference=model_preference)
    llm = router.create_llm(spec, temperature=0.1, streaming=False)

    prompt = [
        SystemMessage(content=SUPERVISOR_PROMPT),
        HumanMessage(
            content=f"User Message: {user_message}\nAttachments Count: {len(attachments)}\nNeeds Vision: {needs_vision}"
        ),
    ]

    try:
        response = await llm.ainvoke(prompt)
        content = response.content if isinstance(response.content, str) else str(response.content)
        
        # Clean JSON markdown fences if present
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        analysis = json.loads(content)

        complexity = analysis.get("complexity", 5)
        requires_planning = analysis.get("requires_planning", False)
        required_tools = analysis.get("required_tools", [])
        suggested_tier = analysis.get("model_tier", "medium")

        # Determine next node
        if requires_planning or complexity >= 5 or len(required_tools) > 0:
            next_node = "planner"
        else:
            next_node = "rag_retriever"

        logger.info(
            "Supervisor analysis: intent=%s, complexity=%d, tools=%s, next_node=%s",
            analysis.get("intent"),
            complexity,
            required_tools,
            next_node,
        )

        return {
            "model_tier": suggested_tier,
            "active_tools": required_tools,
            "next_node": next_node,
            "scratchpad": [{
                "node": "supervisor",
                "analysis": analysis,
            }],
        }

    except Exception as e:
        logger.warning("Supervisor LLM parsing failed, using fallback: %s", str(e))
        # Fallback routing logic
        has_tools = len(attachments) > 0 or any(
            kw in user_message.lower() for kw in ["search", "google", "find", "code", "run", "calculate"]
        )
        return {
            "model_tier": "medium",
            "active_tools": ["web_search"] if "search" in user_message.lower() else [],
            "next_node": "planner" if has_tools else "rag_retriever",
            "scratchpad": [{
                "node": "supervisor",
                "fallback": True,
                "error": str(e),
            }],
        }
