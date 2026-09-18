from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel

from app.models.enums import DocumentStatus, DocumentType
from app.schemas.common import ORMModel


class DocumentOut(ORMModel):
    id: uuid.UUID
    title: str
    filename: str
    mime_type: str
    size_bytes: int
    doc_type: DocumentType
    language: str
    status: DocumentStatus
    page_count: int | None = None
    effective_from: date | None = None
    created_at: datetime
    chunk_count: int = 0


class ReindexResult(BaseModel):
    document_id: uuid.UUID
    queued: bool
