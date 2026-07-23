"""
OmniEngine — Vision Analyzer Tool

Parses images, charts, and diagrams using GPT-4o or Gemini 1.5 Pro.
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field

from backend.agents.model_router import ModelRouter
from backend.tools.registry import BaseTool

logger = logging.getLogger(__name__)


class VisionInput(BaseModel):
    """Input schema for vision analysis."""

    image_url: str = Field(..., description="URL or base64 data URI of the image")
    prompt: str = Field(
        "Describe and analyze this image in detail.",
        description="Prompt instructions for vision model",
    )


class VisionAnalyzerTool(BaseTool):
    """Multi-model vision analyzer tool."""

    name = "vision_analyzer"
    description = "Analyzes images, diagrams, charts, and OCR text from visual attachments."
    args_schema = VisionInput

    async def execute(  # type: ignore[override]
        self,
        image_url: str,
        prompt: str = "Describe and analyze this image in detail.",
        **kwargs: Any,
    ) -> str:
        """Execute vision analysis using vision-capable model."""
        try:
            router = ModelRouter()
            spec = router.select_model(tier="medium", needs_vision=True)
            llm = router.create_llm(spec, temperature=0.2, streaming=False)

            from langchain_core.messages import HumanMessage

            message = HumanMessage(
                content=[
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_url}},
                ]
            )

            response = await llm.ainvoke([message])
            return str(response.content)

        except Exception as e:
            logger.error("Vision analysis failed: %s", str(e))
            return f"Vision analysis unavailable: {e!s}"
