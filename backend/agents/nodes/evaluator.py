"""
OmniEngine — Evaluator Node

Evaluates generated output quality, scores confidence (0.0-1.0), detects potential
hallucinations or safety issues, and determines if a disclaimer is required.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from langchain_core.messages import HumanMessage, SystemMessage

from backend.agents.model_router import ModelRouter
from backend.agents.prompts import EVALUATOR_PROMPT

if TYPE_CHECKING:
    from backend.agents.state import AgentState

logger = logging.getLogger(__name__)


async def evaluator_node(state: AgentState) -> dict[str, Any]:
    """
    Evaluator node implementation.

    Reads: `user_message`, `current_plan`, `retrieved_memories`
    Writes: `confidence_score`, `safety_flags`, `should_respond`, `next_node`, `scratchpad`
    """
    logger.info("Executing Evaluator node for session %s", state["session_id"])

    user_message = state["user_message"]
    plan = state.get("current_plan", [])

    # Collect plan step results
    step_results = [f"Step {s.get('step_id')}: {s.get('result')}" for s in plan if s.get("result")]
    combined_results = "\n".join(step_results) if step_results else "Direct LLM execution"

    router = ModelRouter()
    spec = router.select_model(tier="small", preference=state.get("model_preference"))
    llm = router.create_llm(spec, temperature=0.1, streaming=False)

    eval_input = f"User Request: {user_message}\nExecution Results:\n{combined_results}"

    prompt = [
        SystemMessage(content=EVALUATOR_PROMPT),
        HumanMessage(content=eval_input),
    ]

    try:
        response = await llm.ainvoke(prompt)
        content = response.content if isinstance(response.content, str) else str(response.content)

        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        eval_data = json.loads(content)

        confidence_score = float(eval_data.get("confidence_score", 0.85))
        is_acceptable = eval_data.get("is_acceptable", True)
        safety_flags = eval_data.get("safety_flags", [])

        logger.info(
            "Evaluation complete: confidence=%.2f, acceptable=%s, flags=%s",
            confidence_score,
            is_acceptable,
            safety_flags,
        )

        return {
            "confidence_score": confidence_score,
            "safety_flags": safety_flags,
            "should_respond": True,
            "next_node": "response_formatter",
            "scratchpad": [
                {
                    "node": "evaluator",
                    "confidence": confidence_score,
                    "is_acceptable": is_acceptable,
                }
            ],
        }

    except Exception as e:
        logger.warning("Evaluator failed, passing through with default confidence: %s", str(e))
        return {
            "confidence_score": 0.85,
            "safety_flags": [],
            "should_respond": True,
            "next_node": "response_formatter",
            "scratchpad": [
                {
                    "node": "evaluator",
                    "fallback": True,
                    "error": str(e),
                }
            ],
        }
