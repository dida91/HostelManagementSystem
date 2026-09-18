"""Hybrid retrieval: dense (pgvector) + lexical (PostgreSQL FTS), fused with RRF.

Why hybrid rather than embeddings alone: hostel questions carry exact tokens --
room numbers, fine amounts, rule numbers, dates -- where lexical matching beats
embeddings, while paraphrased questions ("can I stay out late?") need dense
retrieval. Reciprocal Rank Fusion combines both without a tuned weight, which
matters because we have no labelled data to tune one against at the start.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import Float, func, select
from sqlalchemy import text as sql_text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.document import ChunkEmbedding, Document, DocumentChunk
from app.models.enums import DocumentStatus, DocumentType

log = get_logger("ai.retrieval")

# Standard RRF damping constant. Keeps any single ranker from dominating.
RRF_K = 60


@dataclass(slots=True)
class RetrievedChunk:
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    document_title: str
    text: str
    page_number: int | None
    section_path: str | None
    dense_rank: int | None = None
    lexical_rank: int | None = None
    score: float = 0.0

    @property
    def source_label(self) -> str:
        parts = [self.document_title]
        if self.page_number is not None:
            parts.append(f"p.{self.page_number}")
        if self.section_path:
            parts.append(self.section_path)
        return " — ".join(parts)


class RetrievalService:
    def __init__(self, *, embedding_model: str) -> None:
        self._embedding_model = embedding_model

    async def _dense(
        self,
        session: AsyncSession,
        query_vector: list[float],
        *,
        limit: int,
        doc_types: list[DocumentType] | None,
    ) -> list[tuple[uuid.UUID, float]]:
        stmt = (
            select(
                DocumentChunk.id,
                ChunkEmbedding.embedding.cosine_distance(query_vector).label("distance"),
            )
            .join(ChunkEmbedding, ChunkEmbedding.chunk_id == DocumentChunk.id)
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(
                ChunkEmbedding.model == self._embedding_model,
                Document.status == DocumentStatus.INDEXED,
            )
            .order_by(sql_text("distance"))
            .limit(limit)
        )
        if doc_types:
            stmt = stmt.where(Document.doc_type.in_(doc_types))
        rows = (await session.execute(stmt)).all()
        return [(r[0], float(r[1])) for r in rows]

    async def _lexical(
        self,
        session: AsyncSession,
        query: str,
        *,
        limit: int,
        doc_types: list[DocumentType] | None,
    ) -> list[tuple[uuid.UUID, float]]:
        # 'simple' config matches the generated tsv column: the corpus mixes
        # English and Nepali, and English stemming would mangle Devanagari.
        tsquery = func.websearch_to_tsquery("simple", query)
        rank = func.ts_rank_cd(DocumentChunk.tsv, tsquery).cast(Float)
        stmt = (
            select(DocumentChunk.id, rank.label("rank"))
            .join(Document, Document.id == DocumentChunk.document_id)
            .where(
                DocumentChunk.tsv.op("@@")(tsquery),
                Document.status == DocumentStatus.INDEXED,
            )
            .order_by(sql_text("rank DESC"))
            .limit(limit)
        )
        if doc_types:
            stmt = stmt.where(Document.doc_type.in_(doc_types))
        rows = (await session.execute(stmt)).all()
        return [(r[0], float(r[1])) for r in rows]

    async def retrieve(
        self,
        *,
        session: AsyncSession,
        query: str,
        query_vector: list[float],
        top_k: int = 5,
        candidate_k: int = 20,
        doc_types: list[DocumentType] | None = None,
    ) -> list[RetrievedChunk]:
        """Run both rankers and fuse with RRF."""
        dense = await self._dense(session, query_vector, limit=candidate_k, doc_types=doc_types)
        lexical = await self._lexical(session, query, limit=candidate_k, doc_types=doc_types)

        scores: dict[uuid.UUID, float] = {}
        dense_rank: dict[uuid.UUID, int] = {}
        lexical_rank: dict[uuid.UUID, int] = {}

        for rank, (cid, _) in enumerate(dense, start=1):
            dense_rank[cid] = rank
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (RRF_K + rank)
        for rank, (cid, _) in enumerate(lexical, start=1):
            lexical_rank[cid] = rank
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (RRF_K + rank)

        if not scores:
            return []

        ordered = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:top_k]
        ids = [cid for cid, _ in ordered]

        rows = (
            await session.execute(
                select(DocumentChunk, Document.title)
                .join(Document, Document.id == DocumentChunk.document_id)
                .where(DocumentChunk.id.in_(ids))
            )
        ).all()
        by_id = {c.id: (c, title) for c, title in rows}

        results: list[RetrievedChunk] = []
        for cid, score in ordered:
            if cid not in by_id:
                continue
            chunk, title = by_id[cid]
            results.append(
                RetrievedChunk(
                    chunk_id=chunk.id,
                    document_id=chunk.document_id,
                    document_title=title,
                    text=chunk.text,
                    page_number=chunk.page_number,
                    section_path=chunk.section_path,
                    dense_rank=dense_rank.get(cid),
                    lexical_rank=lexical_rank.get(cid),
                    score=score,
                )
            )

        log.info(
            "retrieval_complete",
            dense_hits=len(dense),
            lexical_hits=len(lexical),
            returned=len(results),
        )
        return results


def build_context(chunks: list[RetrievedChunk]) -> str:
    """Assemble numbered passages the model must cite by tag."""
    blocks = []
    for i, c in enumerate(chunks, start=1):
        blocks.append(f"[S{i}] (source: {c.source_label})\n{c.text}")
    return "\n\n---\n\n".join(blocks)
