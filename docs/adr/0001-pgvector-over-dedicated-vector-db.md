# ADR 0001 — pgvector in the application database, not a dedicated vector DB

Status: accepted · 2026-09-19

## Context
The RAG corpus is hostel documents: rules, fee/leave/mess policies, notices,
FAQs. Realistically a few hundred pages, i.e. low thousands of chunks. Options
were pgvector, Chroma (used in an earlier project of ours), or Qdrant/Weaviate.

## Decision
Store embeddings in `chunk_embeddings` in the same PostgreSQL instance, using
pgvector with an HNSW cosine index.

## Consequences
- A document and its chunks/embeddings commit in ONE transaction; there is no
  second store to fall out of sync or back up separately.
- Metadata filtering (doc_type, status, effective_from) is plain SQL joined
  against the documents table, not a parallel filter language.
- Lexical retrieval comes free from the same database via `tsvector`.
- If the corpus ever outgrows this (≫100k chunks), the `EmbeddingProvider`
  abstraction and the model-keyed embeddings table make migration additive.

Chroma was rejected because it has no shared-server story alongside a
PostgreSQL source of truth; a dedicated vector service was rejected as
operational weight with no retrieval benefit at this scale.
