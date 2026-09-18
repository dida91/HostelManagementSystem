"""RAG answer generation with citations."""

from __future__ import annotations

import time
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.prompts import assistant as prompts
from app.ai.providers.base import LLMProvider
from app.ai.schemas.assistant import GroundedAnswer
from app.ai.services.embeddings import EmbeddingService
from app.ai.services.retrieval import RetrievalService, RetrievedChunk, build_context
from app.ai.telemetry.tracing import ai_span
from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.ai import RagQuery
from app.models.enums import DocumentType

log = get_logger("ai.rag")

OPERATION = "rag.answer"


class RagAnswer:
    def __init__(
        self, *, answer: str, grounded: bool, citations: list[dict], chunks: list[RetrievedChunk]
    ) -> None:
        self.answer = answer
        self.grounded = grounded
        self.citations = citations
        self.chunks = chunks


class RagService:
    def __init__(
        self,
        *,
        provider: LLMProvider,
        embeddings: EmbeddingService,
        retrieval: RetrievalService,
    ) -> None:
        self._provider = provider
        self._embeddings = embeddings
        self._retrieval = retrieval
        self._settings = get_settings().ai

    async def answer(
        self,
        *,
        session: AsyncSession,
        question: str,
        user_id: uuid.UUID | None = None,
        top_k: int = 5,
        doc_types: list[DocumentType] | None = None,
    ) -> RagAnswer:
        """Retrieve, then generate an answer constrained to what was retrieved.

        When retrieval returns nothing we do NOT call the model: an ungrounded
        model would happily invent a plausible hostel rule, which is worse than
        saying we do not know.
        """
        t0 = time.perf_counter()
        query_vector = await self._embeddings.embed_query(
            session=session, text=question, user_id=user_id
        )
        chunks = await self._retrieval.retrieve(
            session=session,
            query=question,
            query_vector=query_vector,
            top_k=top_k,
            doc_types=doc_types,
        )
        retrieval_ms = int((time.perf_counter() - t0) * 1000)

        if not chunks:
            log.info("rag_no_context", question_len=len(question))
            answer = RagAnswer(
                answer=(
                    "I could not find anything about that in the hostel documents. "
                    "Please check with the warden's office."
                ),
                grounded=False,
                citations=[],
                chunks=[],
            )
            session.add(
                RagQuery(
                    user_id=user_id,
                    query_text=question,
                    retrieved_chunk_ids=[],
                    dense_hits=0,
                    lexical_hits=0,
                    answer=answer.answer,
                    citations=[],
                    grounded=False,
                    retrieval_ms=retrieval_ms,
                    generation_ms=0,
                )
            )
            await session.flush()
            return answer

        context = build_context(chunks)
        model = self._settings.gemini_text_model
        t1 = time.perf_counter()

        async with ai_span(
            operation=OPERATION,
            model=model,
            session=session,
            user_id=user_id,
            prompt_version=prompts.RAG_VERSION,
        ) as span:
            result = await self._provider.generate_structured(
                prompt=prompts.build_rag_user_prompt(question=question, context=context),
                schema=GroundedAnswer,
                system=prompts.RAG_SYSTEM,
                model=model,
                temperature=0.1,
            )
            span.record_usage(result.usage.input_tokens, result.usage.output_tokens)
            span.retry_count = result.retry_count

        generation_ms = int((time.perf_counter() - t1) * 1000)
        data = result.data

        # Resolve [S#] tags back to real document coordinates. A tag the model
        # invented that does not map to a retrieved chunk is dropped rather than
        # shown as a citation.
        citations: list[dict] = []
        for cit in data.citations:
            idx = _parse_tag(cit.source_tag)
            if idx is None or not (1 <= idx <= len(chunks)):
                log.warning("rag_invalid_citation_tag", tag=cit.source_tag)
                continue
            c = chunks[idx - 1]
            citations.append(
                {
                    "tag": cit.source_tag,
                    "document_id": str(c.document_id),
                    "document_title": c.document_title,
                    "page_number": c.page_number,
                    "section_path": c.section_path,
                    "chunk_id": str(c.chunk_id),
                    "quote": cit.quote,
                }
            )

        session.add(
            RagQuery(
                user_id=user_id,
                query_text=question,
                retrieved_chunk_ids=[str(c.chunk_id) for c in chunks],
                dense_hits=sum(1 for c in chunks if c.dense_rank),
                lexical_hits=sum(1 for c in chunks if c.lexical_rank),
                answer=data.answer,
                citations=citations,
                grounded=data.grounded,
                retrieval_ms=retrieval_ms,
                generation_ms=generation_ms,
            )
        )
        await session.flush()

        return RagAnswer(
            answer=data.answer, grounded=data.grounded, citations=citations, chunks=chunks
        )


def _parse_tag(tag: str) -> int | None:
    cleaned = tag.strip().strip("[]").upper().lstrip("S")
    try:
        return int(cleaned)
    except ValueError:
        return None
