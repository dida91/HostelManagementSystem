"""Document ingestion: parse -> chunk -> embed -> index.

Native text extraction is tried first. Gemini multimodal is used only for pages
where that yields too little text (scans, image-based PDFs), because sending
every page to the model is slow and costly for no gain on text-native files.
"""

from __future__ import annotations

import io
import uuid

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.providers.base import DocumentUnderstandingProvider
from app.ai.services.chunking import chunk_text
from app.ai.services.embeddings import EmbeddingService
from app.core.logging import get_logger
from app.models.document import ChunkEmbedding, Document, DocumentChunk
from app.models.enums import DocumentStatus

log = get_logger("ai.ingestion")

# Below this many characters, a PDF page is treated as un-extractable (a scan)
# and handed to the multimodal model.
MIN_CHARS_PER_PAGE = 120


class IngestionService:
    def __init__(
        self,
        *,
        embeddings: EmbeddingService,
        document_reader: DocumentUnderstandingProvider | None = None,
    ) -> None:
        self._embeddings = embeddings
        self._reader = document_reader

    async def _extract_pages(self, document: Document, content: bytes) -> list[tuple[int, str]]:
        """Return [(page_number, text)]. Non-PDF formats are a single page."""
        if document.mime_type in {"text/plain", "text/markdown"}:
            return [(1, content.decode("utf-8", errors="replace"))]

        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(content))
        pages: list[tuple[int, str]] = []
        scanned: list[int] = []

        for index, page in enumerate(reader.pages, start=1):
            try:
                text = page.extract_text() or ""
            except Exception:  # noqa: BLE001 - a broken page must not fail the document
                text = ""
            if len(text.strip()) < MIN_CHARS_PER_PAGE:
                scanned.append(index)
            pages.append((index, text))

        if scanned and self._reader is not None:
            log.info(
                "pages_need_multimodal_extraction",
                document_id=str(document.id),
                pages=scanned[:20],
                count=len(scanned),
            )
            result = await self._reader.extract_document_text(
                content=content,
                mime_type=document.mime_type,
                hint=f"Hostel document: {document.title}",
            )
            if result.text.strip():
                # The model reads the whole file rather than page-by-page, so page
                # attribution is lost here; chunks from this path carry page=None
                # and cite the document and section only.
                return [(0, result.text)]

        return pages

    async def ingest(
        self,
        *,
        session: AsyncSession,
        document: Document,
        content: bytes,
        user_id: uuid.UUID | None = None,
    ) -> int:
        """Parse, chunk, embed and index. Idempotent: re-ingesting replaces the
        document's existing chunks rather than duplicating them."""
        document.status = DocumentStatus.PROCESSING
        document.processing_error = None
        await session.flush()

        try:
            pages = await self._extract_pages(document, content)
            document.page_count = max((p for p, _ in pages), default=0) or None

            # Clear any previous index for this document.
            old = (
                (
                    await session.execute(
                        select(DocumentChunk.id).where(DocumentChunk.document_id == document.id)
                    )
                )
                .scalars()
                .all()
            )
            if old:
                await session.execute(
                    delete(ChunkEmbedding).where(ChunkEmbedding.chunk_id.in_(old))
                )
                await session.execute(delete(DocumentChunk).where(DocumentChunk.id.in_(old)))
                await session.flush()

            chunk_index = 0
            chunk_ids: list[uuid.UUID] = []
            for page_number, text in pages:
                for chunk in chunk_text(
                    text,
                    page_number=page_number if page_number > 0 else None,
                    start_index=chunk_index,
                ):
                    row = DocumentChunk(
                        document_id=document.id,
                        chunk_index=chunk.index,
                        page_number=chunk.page_number,
                        section_path=chunk.section_path,
                        text=chunk.text,
                        token_count=chunk.token_count,
                        content_hash=chunk.content_hash,
                        chunk_metadata={
                            "doc_type": document.doc_type.value,
                            "language": document.language,
                        },
                    )
                    session.add(row)
                    chunk_ids.append(row.id)
                    chunk_index = chunk.index + 1
            await session.flush()

            if not chunk_ids:
                raise ValueError("No readable text was extracted from this document.")

            await self._embeddings.embed_chunks(
                session=session, chunk_ids=chunk_ids, user_id=user_id
            )

            document.status = DocumentStatus.INDEXED
            await session.flush()
            log.info(
                "document_indexed",
                document_id=str(document.id),
                chunks=len(chunk_ids),
                pages=document.page_count,
            )
            return len(chunk_ids)

        except Exception as exc:
            document.status = DocumentStatus.FAILED
            # Operator-facing only; the API returns a generic message.
            document.processing_error = f"{type(exc).__name__}: {exc}"[:1000]
            await session.flush()
            log.error(
                "document_ingestion_failed",
                document_id=str(document.id),
                error=str(exc)[:500],
            )
            raise
