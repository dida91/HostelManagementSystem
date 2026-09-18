"""Hostel document upload and indexing. Staff only."""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from sqlalchemy import func, select

from app.api.deps import CurrentUser, SessionDep, require_roles
from app.core.errors import NotFoundError
from app.models.document import Document, DocumentChunk
from app.models.enums import DocumentStatus, DocumentType, UserRole
from app.schemas.common import Page
from app.schemas.document import DocumentOut, ReindexResult
from app.services.documents import DocumentService

router = APIRouter(
    prefix="/documents",
    tags=["documents"],
    dependencies=[Depends(require_roles(UserRole.WARDEN, UserRole.SUPER_ADMIN))],
)


@router.post("", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def upload_document(
    user: CurrentUser,
    session: SessionDep,
    file: Annotated[UploadFile, File()],
    title: Annotated[str, Form(min_length=2, max_length=255)],
    doc_type: Annotated[DocumentType, Form()],
    language: Annotated[str, Form(max_length=10)] = "en",
) -> Document:
    """Upload a hostel document. Parsing and indexing run in the background."""
    content = await file.read()
    document = await DocumentService(session).create(
        filename=file.filename or "upload",
        content=content,
        declared_mime=file.content_type,
        title=title,
        doc_type=doc_type,
        language=language,
        uploaded_by_user_id=user.id,
    )

    from app.workers.tasks.document_tasks import ingest_document_task

    try:
        ingest_document_task.delay(str(document.id))
    except Exception:  # noqa: BLE001 - the file is stored; indexing can be retried
        from app.core.logging import get_logger

        get_logger("api.documents").error("ingestion_enqueue_failed", document_id=str(document.id))
    return document


@router.get("", response_model=Page[DocumentOut])
async def list_documents(
    session: SessionDep,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> Page[DocumentOut]:
    total = (await session.execute(select(func.count(Document.id)))).scalar_one()
    rows = (
        (
            await session.execute(
                select(Document).order_by(Document.created_at.desc()).limit(limit).offset(offset)
            )
        )
        .scalars()
        .all()
    )

    counts: dict[uuid.UUID, int] = {
        row[0]: row[1]
        for row in (
            await session.execute(
                select(DocumentChunk.document_id, func.count(DocumentChunk.id)).group_by(
                    DocumentChunk.document_id
                )
            )
        ).all()
    }
    items = []
    for r in rows:
        out = DocumentOut.model_validate(r)
        out.chunk_count = int(counts.get(r.id, 0))
        items.append(out)
    return Page(items=items, total=int(total), limit=limit, offset=offset)


@router.post("/{document_id}/reindex", response_model=ReindexResult)
async def reindex_document(document_id: uuid.UUID, session: SessionDep) -> ReindexResult:
    """Re-run parsing and embedding, e.g. after an ingestion failure or an
    embedding-model change."""
    document = await session.get(Document, document_id)
    if document is None:
        raise NotFoundError("Document not found.")

    from app.workers.tasks.document_tasks import ingest_document_task

    document.status = DocumentStatus.UPLOADED
    await session.flush()
    ingest_document_task.delay(str(document.id))
    return ReindexResult(document_id=document.id, queued=True)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(document_id: uuid.UUID, session: SessionDep) -> None:
    """Remove a document, its chunks and its embeddings, and the stored file."""
    document = await session.get(Document, document_id)
    if document is None:
        raise NotFoundError("Document not found.")
    stored = Path(document.storage_uri)
    await session.delete(document)  # chunks and embeddings cascade
    await session.flush()
    # Blocking file IO is kept off the event loop.
    await asyncio.to_thread(stored.unlink, True)
