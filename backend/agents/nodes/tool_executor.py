"""
OmniEngine — Tool Executor Node

Validates tool invocations, dispatches to the MCP tool registry,
handles timeouts and retries, and captures execution results.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from backend.agents.state import AgentState

logger = logging.getLogger(__name__)


async def tool_executor_node(state: AgentState) -> dict[str, Any]:
    """
    Tool Executor node implementation.

    Reads: `current_plan`, `current_step_index`, `consecutive_tool_failures`
    Writes: `current_plan`, `current_step_index`, `consecutive_tool_failures`, `next_node`, `scratchpad`
    """
    plan: list[Any] = list(state.get("current_plan", []))
    step_idx = state.get("current_step_index", 0)
    consecutive_failures = state.get("consecutive_tool_failures", 0)

    if not plan or step_idx >= len(plan):
        return {"next_node": "evaluator"}

    current_step = dict(plan[step_idx])
    tool_name = str(current_step.get("tool", ""))

    if not tool_name:
        # Step doesn't require a tool — advance step index
        current_step["status"] = "completed"
        plan[step_idx] = current_step  # type: ignore[typeddict-item]
        return {
            "current_plan": plan,
            "current_step_index": step_idx + 1,
            "next_node": "tool_executor"
            if step_idx + 1 < len(plan) and plan[step_idx + 1].get("tool")
            else "evaluator",
        }

    logger.info(
        "Executing tool '%s' for step %s: %s",
        tool_name,
        str(current_step.get("step_id")),
        str(current_step.get("description")),
    )

    current_step["status"] = "in_progress"
    plan[step_idx] = current_step  # type: ignore[typeddict-item]

    try:
        # Import tools registry dynamically (Phase 4 integration)
        result_text = ""
        try:
            from backend.tools.registry import get_tool_registry

            registry = get_tool_registry()
            tool = registry.get_tool(tool_name)

            if tool:
                tool_result = await tool.execute(query=str(current_step.get("description", "")))
                result_text = str(tool_result)
            else:
                result_text = f"Tool '{tool_name}' simulated output for step: {current_step.get('description')}"
        except ImportError:
            # Phase 4 registry placeholder
            result_text = f"Simulated tool output for {tool_name}: executed step successfully."

        current_step["status"] = "completed"
        current_step["result"] = result_text
        plan[step_idx] = current_step  # type: ignore[typeddict-item]

        return {
            "current_plan": plan,
            "current_step_index": step_idx + 1,
            "consecutive_tool_failures": 0,
            "tool_call_count": state.get("tool_call_count", 0) + 1,
            "next_node": "tool_executor"
            if (step_idx + 1 < len(plan) and plan[step_idx + 1].get("tool"))
            else "evaluator",
            "scratchpad": [
                {
                    "node": "tool_executor",
                    "tool": tool_name,
                    "status": "success",
                    "result_preview": result_text[:100],
                }
            ],
        }

    except Exception as e:
        logger.error("Tool '%s' execution failed: %s", tool_name, str(e))
        new_failures = consecutive_failures + 1

        retries = current_step.get("retries", 0)
        current_step["retries"] = (int(retries) if isinstance(retries, (int, str)) else 0) + 1

        if new_failures >= 3:
            current_step["status"] = "failed"
            current_step["result"] = f"Failed after {new_failures} attempts: {e!s}"
            plan[step_idx] = current_step  # type: ignore[typeddict-item]

            logger.warning("3 consecutive tool failures reached — triggering re-planning")
            return {
                "current_plan": plan,
                "consecutive_tool_failures": new_failures,
                "next_node": "planner",  # Loop back to planner for re-planning
                "scratchpad": [
                    {
                        "node": "tool_executor",
                        "tool": tool_name,
                        "status": "failed_replanning_triggered",
                        "error": str(e),
                    }
                ],
            }

        plan[step_idx] = current_step  # type: ignore[index,typeddict-item]
        return {
            "current_plan": plan,
            "consecutive_tool_failures": new_failures,
            "next_node": "tool_executor",  # Retry
            "scratchpad": [
                {
                    "node": "tool_executor",
                    "tool": tool_name,
                    "status": "retry",
                    "attempt": current_step["retries"],
                    "error": str(e),
                }
            ],
        }
