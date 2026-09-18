"""Complaint classification evaluation.

Runs the REAL Gemini pipeline against a labelled dataset and reports per-class
precision/recall/F1 plus latency, token usage and cost. Requires GEMINI_API_KEY.

    python ai/evaluation/runners/eval_complaints.py

Metrics are written to ai/evaluation/reports/ so prompt changes can be compared
across versions. Nothing here claims accuracy without evidence: if the run does
not execute, no numbers are produced.
"""
from __future__ import annotations

import asyncio
import json
import sys
import time
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.ai.prompts import complaint as prompts  # noqa: E402
from app.ai.providers.registry import ai_is_available, get_llm_provider  # noqa: E402
from app.ai.schemas.complaint import ComplaintAnalysis  # noqa: E402
from app.core.config import get_settings  # noqa: E402

DATASET = ROOT / "ai" / "evaluation" / "datasets" / "complaints.jsonl"
REPORTS = ROOT / "ai" / "evaluation" / "reports"
FIELDS = ["category", "priority", "sentiment", "suggested_department"]


def prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return precision, recall, f1


async def main() -> int:
    if not ai_is_available():
        print("GEMINI_API_KEY is not configured -- cannot evaluate.", file=sys.stderr)
        print("Set it in apps/api/.env, then re-run.", file=sys.stderr)
        return 2

    rows = [json.loads(line) for line in DATASET.read_text().splitlines() if line.strip()]
    provider = get_llm_provider()
    model = get_settings().ai.gemini_fast_model

    per_field_tp: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    per_field_fp: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    per_field_fn: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    exact = {f: 0 for f in FIELDS}
    latencies: list[float] = []
    tokens_in = tokens_out = 0
    failures = 0
    location_correct = 0

    for row in rows:
        started = time.perf_counter()
        try:
            result = await provider.generate_structured(
                prompt=prompts.build_user_prompt(row["text"]),
                schema=ComplaintAnalysis,
                system=prompts.SYSTEM,
                model=model,
                temperature=0.0,
            )
        except Exception as exc:  # noqa: BLE001
            failures += 1
            print(f"  [{row['id']}] FAILED: {type(exc).__name__}")
            continue

        latencies.append((time.perf_counter() - started) * 1000)
        tokens_in += result.usage.input_tokens or 0
        tokens_out += result.usage.output_tokens or 0
        got = result.data

        for field in FIELDS:
            want = row["expected"][field]
            have = getattr(got, field)
            have = have.value if hasattr(have, "value") else have
            if have == want:
                exact[field] += 1
                per_field_tp[field][want] += 1
            else:
                per_field_fp[field][have] += 1
                per_field_fn[field][want] += 1

        if (got.location is not None) == row["expected_location_present"]:
            location_correct += 1

        print(f"  [{row['id']}] {got.category.value}/{got.priority.value} ok")

    n = len(rows) - failures
    if n <= 0:
        print("All samples failed; no metrics produced.", file=sys.stderr)
        return 1

    latencies.sort()
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "model": model,
        "prompt_version": prompts.VERSION,
        "samples": len(rows),
        "failures": failures,
        "accuracy": {f: round(exact[f] / n, 3) for f in FIELDS},
        "location_abstention_accuracy": round(location_correct / n, 3),
        "per_class_f1": {
            f: {
                cls: round(
                    prf(per_field_tp[f][cls], per_field_fp[f][cls], per_field_fn[f][cls])[2], 3
                )
                for cls in set(per_field_tp[f]) | set(per_field_fn[f])
            }
            for f in FIELDS
        },
        "latency_ms": {
            "p50": round(latencies[len(latencies) // 2], 1),
            "p95": round(latencies[int(len(latencies) * 0.95) - 1], 1),
            "mean": round(sum(latencies) / len(latencies), 1),
        },
        "tokens": {"input": tokens_in, "output": tokens_out},
    }

    REPORTS.mkdir(parents=True, exist_ok=True)
    out = REPORTS / f"complaints_{prompts.VERSION}_{int(time.time())}.json"
    out.write_text(json.dumps(report, indent=2))

    print("\n=== Complaint classification ===")
    for f in FIELDS:
        print(f"  {f:24s} accuracy {report['accuracy'][f]:.3f}")
    print(f"  {'location abstention':24s} accuracy {report['location_abstention_accuracy']:.3f}")
    print(f"  latency p50/p95: {report['latency_ms']['p50']}/{report['latency_ms']['p95']} ms")
    print(f"  failures: {failures}/{len(rows)}")
    print(f"\n  report -> {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
