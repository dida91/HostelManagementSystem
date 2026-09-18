"""RAG evaluation: retrieval quality, grounding and citation correctness.

Runs the REAL pipeline against the labelled question set. Requires
GEMINI_API_KEY and an indexed corpus.

    python ai/evaluation/runners/eval_rag.py

Measures:
  * retrieval recall@k   -- did the gold section appear in the retrieved chunks
  * MRR                  -- how highly was it ranked
  * grounding accuracy   -- did the model correctly claim/disclaim support,
                            including ABSTENTION on questions with no answer
  * citation validity    -- does every citation resolve to a retrieved chunk
"""

from __future__ import annotations

import asyncio
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.ai.providers.registry import (  # noqa: E402
    ai_is_available, get_embedding_provider, get_llm_provider,
)
from app.ai.services.embeddings import EmbeddingService  # noqa: E402
from app.ai.services.rag import RagService  # noqa: E402
from app.ai.services.retrieval import RetrievalService  # noqa: E402
from app.core.db import AsyncSessionLocal  # noqa: E402
from app.models.document import DocumentChunk  # noqa: E402

DATASET = ROOT / "ai" / "evaluation" / "datasets" / "rag_questions.jsonl"
REPORTS = ROOT / "ai" / "evaluation" / "reports"
TOP_K = 5


async def main() -> int:
    if not ai_is_available():
        print("GEMINI_API_KEY is not configured -- cannot evaluate.", file=sys.stderr)
        return 2

    from sqlalchemy import func, select

    rows = [json.loads(line) for line in DATASET.read_text().splitlines() if line.strip()]

    embeddings = EmbeddingService(get_embedding_provider())
    rag = RagService(
        provider=get_llm_provider(),
        embeddings=embeddings,
        retrieval=RetrievalService(embedding_model=embeddings.model_name),
    )

    recall_hits = 0
    recall_applicable = 0
    reciprocal_ranks: list[float] = []
    grounding_correct = 0
    abstention_correct = 0
    abstention_total = 0
    citation_valid = 0
    citation_total = 0
    latencies: list[float] = []

    async with AsyncSessionLocal() as session:
        indexed = (await session.execute(select(func.count(DocumentChunk.id)))).scalar_one()
        if not indexed:
            print(
                "No indexed document chunks. Upload hostel documents via "
                "POST /api/v1/documents and let ingestion finish, then re-run.",
                file=sys.stderr,
            )
            return 3
        print(f"Corpus: {indexed} indexed chunks\n")

        for row in rows:
            started = time.perf_counter()
            try:
                result = await rag.answer(
                    session=session, question=row["question"], top_k=TOP_K
                )
            except Exception as exc:  # noqa: BLE001
                print(f"  [{row['id']}] FAILED: {type(exc).__name__}")
                continue
            latencies.append((time.perf_counter() - started) * 1000)

            gold = row.get("gold_section")
            if gold:
                recall_applicable += 1
                ranks = [
                    i
                    for i, c in enumerate(result.chunks, start=1)
                    if gold.lower() in ((c.section_path or "") + " " + c.document_title).lower()
                ]
                if ranks:
                    recall_hits += 1
                    reciprocal_ranks.append(1.0 / ranks[0])
                else:
                    reciprocal_ranks.append(0.0)

            if result.grounded == row["must_be_grounded"]:
                grounding_correct += 1

            # Abstention: the model must decline when no document covers the question.
            if not row["must_be_grounded"]:
                abstention_total += 1
                if not result.grounded:
                    abstention_correct += 1

            retrieved = {str(c.chunk_id) for c in result.chunks}
            for citation in result.citations:
                citation_total += 1
                if citation["chunk_id"] in retrieved:
                    citation_valid += 1

            status = "grounded" if result.grounded else "abstained"
            print(f"  [{row['id']}] {status}, {len(result.citations)} citation(s)")

        await session.rollback()

    if not latencies:
        print("All questions failed; no metrics produced.", file=sys.stderr)
        return 1

    latencies.sort()
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "questions": len(rows),
        "top_k": TOP_K,
        "retrieval_recall_at_k": (
            round(recall_hits / recall_applicable, 3) if recall_applicable else None
        ),
        "mrr": (
            round(sum(reciprocal_ranks) / len(reciprocal_ranks), 3)
            if reciprocal_ranks else None
        ),
        "grounding_accuracy": round(grounding_correct / len(latencies), 3),
        "abstention_accuracy": (
            round(abstention_correct / abstention_total, 3) if abstention_total else None
        ),
        "citation_validity": (
            round(citation_valid / citation_total, 3) if citation_total else None
        ),
        "latency_ms": {
            "p50": round(latencies[len(latencies) // 2], 1),
            "p95": round(latencies[int(len(latencies) * 0.95) - 1], 1),
        },
    }

    REPORTS.mkdir(parents=True, exist_ok=True)
    out = REPORTS / f"rag_{int(time.time())}.json"
    out.write_text(json.dumps(report, indent=2))

    print("\n=== RAG evaluation ===")
    for key in (
        "retrieval_recall_at_k", "mrr", "grounding_accuracy",
        "abstention_accuracy", "citation_validity",
    ):
        print(f"  {key:24s} {report[key]}")
    print(f"  {'latency p50/p95 ms':24s} {report['latency_ms']['p50']}/{report['latency_ms']['p95']}")
    print(f"\n  report -> {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
