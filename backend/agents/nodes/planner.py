"""
OmniEngine — Planner Node

Decomposes complex requests into a JSON plan (array of sequential steps).
Handles re-planning if consecutive tool failures occur.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from backend.agents.model_router import ModelRouter
from backend.agents.prompts import PLANNER_PROMPT
from backend.agents.state import AgentState, TaskStep

logger = logging.getLogger(__name__)


async def planner_node(state: AgentState) -> dict[str, Any]:
    """
    Planner node implementation.

    Reads: `user_message`, `active_tools`, `plan_iteration`, `consecutive_tool_failures`
    Writes: `current_plan`, `current_step_index`, `plan_iteration`, `next_node`, `scratchpad`
    """
    plan_iteration = state.get("plan_iteration", 0) + 1
    logger.info(
        "Executing Planner node (iteration %d) for session %s", plan_iteration, state["session_id"]
    )

    user_message = state["user_message"]
    active_tools = state.get("active_tools", [])
    consecutive_failures = state.get("consecutive_tool_failures", 0)
    previous_plan = state.get("current_plan", [])

    router = ModelRouter()
    # Use medium/large model for plan generation
    spec = router.select_model(tier="medium", preference=state.get("model_preference"))
    llm = router.create_llm(spec, temperature=0.2, streaming=False)

    context = f"User Request: {user_message}\nAvailable Tools: {active_tools}"
    if consecutive_failures >= 3:
        context += f"\nRe-planning required! Previous plan failed after {consecutive_failures} tool failures. Previous plan: {previous_plan}"

    prompt = [
        SystemMessage(content=PLANNER_PROMPT),
        HumanMessage(content=context),
    ]

    try:
        response = await llm.ainvoke(prompt)
        content = response.content if isinstance(response.content, str) else str(response.content)

        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        raw_plan = json.loads(content)

        plan: list[TaskStep] = []
        for item in raw_plan:
            plan.append(
                TaskStep(
                    step_id=item.get("step_id", len(plan) + 1),
                    description=item.get("description", ""),
                    tool=item.get("tool"),
                    model_tier=item.get("model_tier", "medium"),
                    success_criteria=item.get("success_criteria", ""),
                    status="pending",
                    result=None,
                    retries=0,
                )
            )

        logger.info("Generated plan with %d steps", len(plan))

        return {
            "current_plan": plan,
            "current_step_index": 0,
            "plan_iteration": plan_iteration,
            "consecutive_tool_failures": 0,  # Reset counter on new plan
            "next_node": "rag_retriever",
            "scratchpad": [
                {
                    "node": "planner",
                    "plan_steps_count": len(plan),
                    "iteration": plan_iteration,
                }
            ],
        }

    except Exception as e:
        logger.warning("Planner failed to generate JSON plan: %s", str(e))
        # Default single-step fallback plan
        fallback_plan: list[TaskStep] = [
            TaskStep(
                step_id=1,
                description="Fulfill user request directly",
                tool=None,
                model_tier="medium",
                success_criteria="User query answered",
                status="pending",
                result=None,
                retries=0,
            )
        ]
        return {
            "current_plan": fallback_plan,
            "current_step_index": 0,
            "plan_iteration": plan_iteration,
            "next_node": "rag_retriever",
            "scratchpad": [
                {
                    "node": "planner",
                    "fallback": True,
                    "error": str(e),
                }
            ],
        }
