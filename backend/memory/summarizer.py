"""
OmniEngine — Conversation Summarizer & Entity Extractor

Summarizes old conversation turns and extracts entity memories
(user preferences, facts, key instructions) to be stored in Postgres and Qdrant.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from langchain_core.messages import SystemMessage, HumanMessage

from backend.agents.model_router import ModelRouter
from backend.core.config import get_settings

logger = logging.getLogger(__name__)

SUMMARIZER_PROMPT = """You are a Memory Summarizer. Summarize the following past conversation messages concisely.
Preserve key facts, user preferences, explicit instructions, decisions made, and technical context.

Output JSON:
{
  "summary": "Concise paragraph summarizing the main discussion and outcomes.",
  "entities": [
    {
      "entity_type": "preference|fact|instruction",
      "entity_key": "e.g., preferred_python_version",
      "content": "User prefers Python 3.12 for backend projects."
    }
  ]
}
"""


class Summarizer:
    """Async summarizer and entity extractor."""

    def __init__(self) -> None:
        self.settings = get_settings()

    async def summarize_messages(
        self, 
        messages: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Generate a summary and extract entity memories from old messages.
        """
        if not messages:
            return {"summary": "", "entities": []}

        conversation_text = "\n".join(
            f"{m.get('role', 'user')}: {m.get('content', '')}" for m in messages
        )

        router = ModelRouter()
        spec = router.select_model(tier="small")
        llm = router.create_llm(spec, temperature=0.1, streaming=False)

        prompt = [
            SystemMessage(content=SUMMARIZER_PROMPT),
            HumanMessage(content=f"Conversation to summarize:\n{conversation_text}"),
        ]

        try:
            response = await llm.ainvoke(prompt)
            content = response.content if isinstance(response.content, str) else str(response.content)

            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            data = json.loads(content)
            logger.info("Generated summary (%d chars) and %d entities", len(data.get("summary", "")), len(data.get("entities", [])))
            return data

        except Exception as e:
            logger.error("Summarizer failed: %s", str(e))
            return {
                "summary": f"Summary of {len(messages)} past messages.",
                "entities": [],
            }
