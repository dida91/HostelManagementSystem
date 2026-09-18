"""Document ingestion worker."""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path

from app.ai.providers.registry import ai_is_available, get_embedding_provider, get_llm_provider
from app.ai.services.embeddings import EmbeddingService
from app.ai.services.ingestion import IngestionService
from app.core.db import AsyncSessionLocal
from app.core.logging import get_logger
from app.models.document import Document
from app.workers.celery_app import celery_app

log = get_logger("workers.documents")


async def _ingest(document_id: uuid.UUID) -> str:
    async with AsyncSessionLocal() as session:
        document = await session.get(Document, document_id)
        if document is None:
            return "not_found"

        path = Path(document.storage_uri)
        # File IO is blocking; keep it off the event loop.
        if not await asyncio.to_thread(path.exists):
            log.error("stored_file_missing", document_id=str(document_id))
            return "file_missing"

        service = IngestionService(
            embeddings=EmbeddingService(get_embedding_provider()),
            document_reader=get_llm_provider(),  # type: ignore[arg-type]
        )
        content = await asyncio.to_thread(path.read_bytes)
        chunks = await service.ingest(session=session, document=document, content=content)
        await session.commit()
        return f"indexed:{chunks}"


@celery_app.task(
    name="ai.ingest_document",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
)
def ingest_document_task(self, document_id: str) -> str:  # type: ignore[no-untyped-def]
    if not ai_is_available():
        # Embeddings require the provider; the file stays stored and can be
        # reindexed once a key is configured.
        log.warning("ai_unavailable_skipping_ingestion", document_id=document_id)
        return "skipped_ai_unavailable"

    log.info("ingesting_document", document_id=document_id)
    return asyncio.run(_ingest(uuid.UUID(document_id)))
