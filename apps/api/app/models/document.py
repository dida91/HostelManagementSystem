"""Document intelligence and vector storage.

`chunk_embeddings` is a separate table keyed by (chunk_id, model) rather than an
embedding column on the chunk itself. Changing the embedding model then becomes
an additive backfill plus an index swap -- no destructive migration, and two
models can coexist during a re-index.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Computed,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.config import get_settings
from app.core.db import Base
from app.models.base import Timestamps, UUIDPrimaryKey
from app.models.enums import DocumentStatus, DocumentType

EMBEDDING_DIM = get_settings().ai.gemini_embedding_dim


class Document(UUIDPrimaryKey, Timestamps, Base):
    __tablename__ = "documents"

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_uri: Mapped[str] = mapped_column(String(500), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    # Content hash: deduplicates re-uploads of an identical file.
    sha256: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    doc_type: Mapped[DocumentType] = mapped_column(
        Enum(DocumentType, name="document_type"), nullable=False
    )
    language: Mapped[str] = mapped_column(String(10), default="en", nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    effective_from: Mapped[date | None] = mapped_column(Date)
    page_count: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[DocumentStatus] = mapped_column(
        Enum(DocumentStatus, name="document_status"),
        default=DocumentStatus.UPLOADED,
        nullable=False,
    )
    processing_error: Mapped[str | None] = mapped_column(Text)
    uploaded_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )

    chunks: Mapped[list[DocumentChunk]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_documents_type_status", "doc_type", "status"),)


class DocumentChunk(UUIDPrimaryKey, Base):
    __tablename__ = "document_chunks"

    document_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    page_number: Mapped[int | None] = mapped_column(Integer)
    section_path: Mapped[str | None] = mapped_column(String(300))
    text: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int | None] = mapped_column(Integer)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    chunk_metadata: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Generated column powering the lexical half of hybrid retrieval.
    # 'simple' (not 'english') because the corpus mixes English and Nepali;
    # English stemming would degrade Devanagari tokens.
    tsv: Mapped[str | None] = mapped_column(
        TSVECTOR, Computed("to_tsvector('simple', text)", persisted=True)
    )

    document: Mapped[Document] = relationship(back_populates="chunks")
    embeddings: Mapped[list[ChunkEmbedding]] = relationship(
        back_populates="chunk", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_chunk_index_per_document"),
        Index("ix_chunks_tsv", "tsv", postgresql_using="gin"),
    )


class ChunkEmbedding(UUIDPrimaryKey, Base):
    __tablename__ = "chunk_embeddings"

    chunk_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("document_chunks.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(32), default="gemini", nullable=False)
    model: Mapped[str] = mapped_column(String(80), nullable=False)
    dim: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    chunk: Mapped[DocumentChunk] = relationship(back_populates="embeddings")

    __table_args__ = (UniqueConstraint("chunk_id", "model", name="uq_embedding_per_chunk_model"),)
