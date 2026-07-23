"""
OmniEngine — Web Search Tool (Tavily Integration)

Provides real-time web search capabilities with source citation formatting.
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field

from backend.core.config import get_settings
from backend.tools.registry import BaseTool

logger = logging.getLogger(__name__)


class WebSearchInput(BaseModel):
    """Input schema for web search tool."""

    query: str = Field(..., description="The search query string", min_length=2)
    max_results: int = Field(
        5, description="Maximum number of search results to return", ge=1, le=10
    )
    search_depth: str = Field("advanced", description="Search depth: 'basic' or 'advanced'")


class WebSearchTool(BaseTool):
    """Tavily web search tool implementation."""

    name = "web_search"
    description = (
        "Searches the live web for up-to-date information, news, dates, and real-time data."
    )
    args_schema = WebSearchInput

    async def execute(  # type: ignore[override]
        self, query: str, max_results: int = 5, search_depth: str = "advanced", **kwargs: Any
    ) -> str:
        """Execute Tavily search."""
        settings = get_settings()

        if not settings.tavily_api_key or settings.tavily_api_key.startswith("tvly-your"):
            logger.warning("Tavily API key not configured — using simulated search response")
            return f"Simulated Web Search Results for '{query}':\n1. [Example Source](https://example.com) — Latest updates regarding {query}."

        try:
            from tavily import AsyncTavilyClient

            client = AsyncTavilyClient(api_key=settings.tavily_api_key)

            response = await client.search(
                query=query,
                max_results=max_results,
                search_depth=search_depth,
            )

            results = response.get("results", [])
            formatted = []
            for idx, item in enumerate(results, 1):
                title = item.get("title", "No Title")
                url = item.get("url", "")
                snippet = item.get("content", "")
                formatted.append(f"{idx}. [{title}]({url})\n   {snippet}")

            return "\n\n".join(formatted) if formatted else "No relevant search results found."

        except Exception as e:
            logger.error("Tavily web search error: %s", str(e))
            return f"Error performing web search: {e!s}"
