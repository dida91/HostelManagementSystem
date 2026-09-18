"""Document upload: validation, content-addressed storage, dedup.

Files arrive from administrators, so they are treated as untrusted input:
sniffed rather than trusted by extension, size-capped, and stored under a
random name outside any served directory.
"""

from __future__ import annotations

import hashlib
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import ConflictError, ValidationFailedError
from app.core.logging import get_logger
from app.models.document import Document
from app.models.enums import DocumentStatus, DocumentType

log = get_logger("services.documents")

# Only formats the ingestion pipeline can actually parse.
ALLOWED_MIME = {
    "application/pdf": ".pdf",
    "text/plain": ".txt",
    "text/markdown": ".md",
}
# Magic-number prefixes, checked against the real bytes rather than the
# client-supplied content type.
_MAGIC = {b"%PDF-": "application/pdf"}


def sniff_mime(content: bytes, declared: str | None) -> str:
    """Determine the real content type from the bytes.

    A declared content type is a hint from the uploader and can be wrong or
    hostile; it is only used when the bytes are unambiguously text.
    """
    for magic, mime in _MAGIC.items():
        if content.startswith(magic):
            return mime
    try:
        content[:4096].decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValidationFailedError(
            "Unsupported file. Upload a PDF, plain text or Markdown document."
        ) from exc
    if declared in {"text/markdown", "text/plain"}:
        return declared
    return "text/plain"


class DocumentService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._settings = get_settings()

    @property
    def storage_root(self) -> Path:
        root = Path(self._settings.storage_dir) / "documents"
        root.mkdir(parents=True, exist_ok=True)
        return root

    async def create(
        self,
        *,
        filename: str,
        content: bytes,
        declared_mime: str | None,
        title: str,
        doc_type: DocumentType,
        language: str,
        uploaded_by_user_id: uuid.UUID | None,
    ) -> Document:
        if not content:
            raise ValidationFailedError("The uploaded file is empty.")
        if len(content) > self._settings.max_upload_bytes:
            limit_mb = self._settings.max_upload_bytes // (1024 * 1024)
            raise ValidationFailedError(f"File exceeds the {limit_mb} MB limit.")

        mime = sniff_mime(content, declared_mime)
        if mime not in ALLOWED_MIME:
            raise ValidationFailedError(
                "Unsupported file type. Upload a PDF, plain text or Markdown document."
            )

        digest = hashlib.sha256(content).hexdigest()
        existing = (
            await self._session.execute(select(Document).where(Document.sha256 == digest))
        ).scalar_one_or_none()
        if existing is not None:
            raise ConflictError(f"This file has already been uploaded as '{existing.title}'.")

        # Random stored name: the original filename never reaches the filesystem,
        # so a crafted name cannot traverse paths or collide.
        stored = f"{uuid.uuid4().hex}{ALLOWED_MIME[mime]}"
        path = self.storage_root / stored
        path.write_bytes(content)

        document = Document(
            title=title.strip(),
            filename=filename[:255],
            storage_uri=str(path),
            mime_type=mime,
            size_bytes=len(content),
            sha256=digest,
            doc_type=doc_type,
            language=language,
            status=DocumentStatus.UPLOADED,
            uploaded_by_user_id=uploaded_by_user_id,
        )
        self._session.add(document)
        await self._session.flush()
        log.info(
            "document_stored",
            document_id=str(document.id),
            mime=mime,
            size_bytes=len(content),
        )
        return document
