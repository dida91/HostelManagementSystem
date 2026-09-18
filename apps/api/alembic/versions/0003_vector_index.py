"""hnsw index for chunk embeddings

Revision ID: 0003_vector_index
Revises: 0002_initial_schema
"""
from __future__ import annotations

from alembic import op

revision = "0003_vector_index"
down_revision = "0002_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Cosine distance matches the normalised embeddings produced by the
    # Gemini embedding provider. m/ef_construction are conservative defaults
    # appropriate for a corpus in the low thousands of chunks.
    op.execute(
        "CREATE INDEX ix_chunk_embeddings_hnsw ON chunk_embeddings "
        "USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)"
    )
    op.execute("CREATE INDEX ix_chunks_text_trgm ON document_chunks USING gin (text gin_trgm_ops)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_chunks_text_trgm")
    op.execute("DROP INDEX IF EXISTS ix_chunk_embeddings_hnsw")
