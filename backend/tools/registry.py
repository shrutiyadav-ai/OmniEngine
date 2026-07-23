"""
OmniEngine — MCP Tool Registry

Central registry for Model Context Protocol (MCP) compatible tools.
Manages tool discovery, Pydantic argument validation, and invocation.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pydantic import BaseModel

logger = logging.getLogger(__name__)


class BaseTool(ABC):
    """Abstract base class for all OmniEngine MCP tools."""

    name: str
    description: str
    args_schema: type[BaseModel]

    @abstractmethod
    async def execute(self, **kwargs: Any) -> Any:
        """Execute the tool with validated keyword arguments."""
        pass


class ToolRegistry:
    """Central registry of available tools."""

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """Register a tool instance."""
        self._tools[tool.name] = tool
        logger.info("Registered MCP tool: %s", tool.name)

    def get_tool(self, name: str) -> BaseTool | None:
        """Retrieve a tool by name."""
        return self._tools.get(name)

    def list_tools(self) -> list[dict[str, Any]]:
        """Return MCP-compatible manifests for all registered tools."""
        manifests = []
        for tool in self._tools.values():
            manifests.append(
                {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.args_schema.model_json_schema(),
                }
            )
        return manifests


_registry: ToolRegistry | None = None


def get_tool_registry() -> ToolRegistry:
    """Return the global tool registry singleton."""
    global _registry  # noqa: PLW0603
    if _registry is None:
        _registry = ToolRegistry()
        _register_default_tools(_registry)
    return _registry


def _register_default_tools(registry: ToolRegistry) -> None:
    """Register built-in tools."""
    try:
        from backend.tools.web_search import WebSearchTool

        registry.register(WebSearchTool())
    except Exception as e:
        logger.warning("Failed to register WebSearchTool: %s", str(e))

    try:
        from backend.tools.code_interpreter import CodeInterpreterTool

        registry.register(CodeInterpreterTool())
    except Exception as e:
        logger.warning("Failed to register CodeInterpreterTool: %s", str(e))

    try:
        from backend.tools.vision_analyzer import VisionAnalyzerTool

        registry.register(VisionAnalyzerTool())
    except Exception as e:
        logger.warning("Failed to register VisionAnalyzerTool: %s", str(e))

    try:
        from backend.tools.calendar_agent import CalendarAgentTool

        registry.register(CalendarAgentTool())
    except Exception as e:
        logger.warning("Failed to register CalendarAgentTool: %s", str(e))
