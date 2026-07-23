"""
OmniEngine — Qdrant Vector Store Wrapper

Async wrapper around Qdrant AsyncQdrantClient for semantic search,
embedding generation, and memory payload management.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    PointStruct,
)

from backend.core.config import Settings, get_settings

logger = logging.getLogger(__name__)

_vector_store = None


class VectorStore:
    """Qdrant Vector Database manager."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.collection_name = self.settings.qdrant_collection_name
        self.client = AsyncQdrantClient(
            host=self.settings.qdrant_host,
            port=self.settings.qdrant_port,
        )

    async def generate_embedding(self, text: str) -> list[float]:
        """
        Generate embedding vector using OpenAI text-embedding-3-small or fallback.
        """
        try:
            from langchain_openai import OpenAIEmbeddings

            embeddings = OpenAIEmbeddings(
                model=self.settings.embedding_model,
                api_key=self.settings.openai_api_key,
            )
            from typing import cast

            return cast("list[float]", await embeddings.aembed_query(text))
        except Exception as e:
            logger.warning("Embedding generation failed, returning dummy vector: %s", str(e))
            # Dummy normalized vector for development fallback
            return [0.01] * self.settings.qdrant_embedding_dim

    async def upsert_memory(
        self,
        content: str,
        memory_type: str = "explicit_preference",
        entity_id: str | None = None,
        session_id: str | None = None,
        confidence_score: float = 0.95,
    ) -> str:
        """
        Upsert a memory payload to Qdrant.
        """
        point_id = str(uuid.uuid4())
        vector = await self.generate_embedding(content)

        payload = {
            "entity_id": entity_id or "usr_default",
            "memory_type": memory_type,
            "content": content,
            "confidence_score": confidence_score,
            "source_session": session_id or "",
        }

        await self.client.upsert(
            collection_name=self.collection_name,
            points=[
                PointStruct(
                    id=point_id,
                    vector=vector,
                    payload=payload,
                )
            ],
        )
        logger.info("Upserted vector memory point %s to Qdrant", point_id)
        return point_id

    async def search_memories(
        self,
        query: str,
        top_k: int = 5,
        score_threshold: float = 0.60,
    ) -> list[dict[str, Any]]:
        """
        Perform dense semantic vector search.
        """
        vector = await self.generate_embedding(query)

        try:
            results = await self.client.search(
                collection_name=self.collection_name,
                query_vector=vector,
                limit=top_k,
                score_threshold=score_threshold,
            )

            memories = []
            for hit in results:
                payload = hit.payload or {}
                memories.append(
                    {
                        "id": hit.id,
                        "score": hit.score,
                        "content": payload.get("content", ""),
                        "memory_type": payload.get("memory_type", ""),
                        "confidence_score": payload.get("confidence_score", 0.0),
                    }
                )
            return memories

        except Exception as e:
            logger.warning("Qdrant search error: %s", str(e))
            return []


def get_vector_store() -> VectorStore:
    """Return singleton VectorStore instance."""
    global _vector_store  # noqa: PLW0603
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store
