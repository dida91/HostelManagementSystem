"""Embedding generation and persistence.

All embedding API calls funnel through here -- nothing else in the application
calls the embedding provider directly. Embeddings are stored with their model
and dimension so a future model change is an additive backfill.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.providers.base import EmbeddingProvider
from app.ai.telemetry.tracing import ai_span
from app.core.logging import get_logger
from app.models.document import ChunkEmbedding, DocumentChunk

log = get_logger("ai.embeddings")

OPERATION_DOCS = "embeddings.documents"
OPERATION_QUERY = "embeddings.query"


class EmbeddingService:
    def __init__(self, provider: EmbeddingProvider) -> None:
        self._provider = provider

    @property
    def model_name(self) -> str:
        return self._provider.model_name

    @property
    def dimensions(self) -> int:
        return self._provider.dimensions

    async def embed_chunks(
        self,
        *,
        session: AsyncSession,
        chunk_ids: list[uuid.UUID],
        user_id: uuid.UUID | None = None,
    ) -> int:
        """Embed chunks that do not yet have a vector for the current model.

        Idempotent: re-running skips chunks already embedded with this model,
        so a partially failed ingestion can simply be retried.
        """
        if not chunk_ids:
            return 0

        existing = set(
            (
                await session.execute(
                    select(ChunkEmbedding.chunk_id).where(
                        ChunkEmbedding.chunk_id.in_(chunk_ids),
                        ChunkEmbedding.model == self.model_name,
                    )
                )
            ).scalars()
        )
        todo = [cid for cid in chunk_ids if cid not in existing]
        if not todo:
            return 0

        rows = (
            (await session.execute(select(DocumentChunk).where(DocumentChunk.id.in_(todo))))
            .scalars()
            .all()
        )
        if not rows:
            return 0

        async with ai_span(
            operation=OPERATION_DOCS, model=self.model_name, session=session, user_id=user_id
        ) as span:
            vectors = await self._provider.embed_documents([r.text for r in rows])
            # Embedding APIs bill on input only; record an approximation so cost
            # reporting stays meaningful across operation types.
            span.record_usage(sum(r.token_count or 0 for r in rows), 0)

        for chunk, vec in zip(rows, vectors, strict=True):
            session.add(
                ChunkEmbedding(
                    chunk_id=chunk.id,
                    provider="gemini",
                    model=self.model_name,
                    dim=vec.dim,
                    embedding=vec.values,
                )
            )
        await session.flush()
        log.info("chunks_embedded", count=len(rows), model=self.model_name)
        return len(rows)

    async def embed_query(
        self, *, session: AsyncSession | None, text: str, user_id: uuid.UUID | None = None
    ) -> list[float]:
        async with ai_span(
            operation=OPERATION_QUERY, model=self.model_name, session=session, user_id=user_id
        ) as span:
            vec = await self._provider.embed_query(text)
            span.record_usage(max(1, len(text) // 4), 0)
        return vec.values
