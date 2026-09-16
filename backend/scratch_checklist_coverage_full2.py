"""One-off script: run all 350 real checklist questions through the real,
live hybrid_retrieve against GXP-MFG-DEMO-01 (real Postgres, real Qdrant,
real Ollama embeddings; reranker attempted but expected to degrade). Not
part of the app or test suite; run and discard.

Purpose: measure how many of the checklist questions the RAG pipeline can
currently surface topically-plausible evidence for, grouped by phase, as
a coverage signal -- not a precision/recall benchmark (no ground truth
labels exist for all 350)."""

import asyncio
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))

from app.db import acquire_pool_or_none  # noqa: E402
from app.llm_router import LLMResponse  # noqa: E402
from app.retrieval import hybrid_search  # noqa: E402
from app.retrieval.hybrid_search import hybrid_retrieve  # noqa: E402

SYSTEM_ID = "GXP-MFG-DEMO-01"
OUT_PATH = os.path.join(os.path.dirname(__file__), "scratch_checklist_coverage_full2_results.json")


async def _skip_rerank_call_llm(*, task: str, prompt: str, **_kwargs) -> LLMResponse:
    # Reranking has been observed to fail on every single call in this
    # environment (local Ollama too slow for the full candidate batch,
    # Groq quota exhausted, OpenRouter billing/malformed) -- this script
    # measures fusion+gate retrieval coverage across 350 real questions,
    # so skip straight to the same degraded response the real cascade
    # would eventually reach anyway, rather than burning ~30-60s per
    # question retrying a cascade already known to fail here.
    return LLMResponse(text="", model_id="", provider="", degraded=True, failure_reason="skipped-for-coverage-run")


def _write_results(results: list) -> None:
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=1)


async def main() -> None:
    # Full run: real reranker cascade, no shortcuts -- Ollama is confirmed
    # up and warm now, so this measures actual production behavior instead
    # of the fallback-gate-only path the rerank-skipped sibling script
    # measures.
    pool = await acquire_pool_or_none()
    if pool is None:
        print("Postgres unreachable.", flush=True)
        return

    with open(os.path.join(os.path.dirname(__file__), "scratch_checklist_350.json"), encoding="utf-8") as f:
        questions = json.load(f)

    results = []
    start_all = time.monotonic()
    for i, q in enumerate(questions):
        start = time.monotonic()
        try:
            outcome = await hybrid_retrieve(pool, q["question"], SYSTEM_ID)
            evidence = outcome.evidence
        except Exception as exc:  # noqa: BLE001
            evidence = []
            print(f"ERR {q['q_id']}: {type(exc).__name__}: {exc}", flush=True)
        elapsed = time.monotonic() - start
        top_titles = [e.get("document_title") for e in evidence[:3]]
        reranked = any(e.get("reranker_score") is not None for e in evidence)
        top_scores = [
            {"dense": e.get("dense_score"), "bm25": e.get("bm25_score"), "rerank": e.get("reranker_score")}
            for e in evidence[:3]
        ]
        results.append(
            {
                "q_id": q["q_id"],
                "phase_no": q["phase_no"],
                "phase": q["phase"],
                "evidence_count": len(evidence),
                "top_titles": top_titles,
                "top_scores": top_scores,
                "reranked": reranked,
                "elapsed_s": round(elapsed, 1),
            }
        )
        if (i + 1) % 10 == 0:
            elapsed_all = time.monotonic() - start_all
            print(f"...{i + 1}/{len(questions)} done ({elapsed_all:.0f}s elapsed, last={elapsed:.1f}s)", flush=True)
            _write_results(results)  # incremental checkpoint -- survives an interrupted run

    _write_results(results)

    # Summary by phase
    by_phase: dict = {}
    for r in results:
        key = (r["phase_no"], r["phase"])
        by_phase.setdefault(key, {"total": 0, "with_evidence": 0, "reranked": 0})
        by_phase[key]["total"] += 1
        if r["evidence_count"] > 0:
            by_phase[key]["with_evidence"] += 1
        if r["reranked"]:
            by_phase[key]["reranked"] += 1

    total = len(results)
    total_with_evidence = sum(1 for r in results if r["evidence_count"] > 0)
    total_reranked = sum(1 for r in results if r["reranked"])
    print(f"\n{total_with_evidence}/{total} questions returned at least 1 evidence item")
    print(f"{total_reranked}/{total} questions had a REAL reranker score (not degraded fallback)\n")
    print(f"{'phase':<45}{'with_evidence':>15}{'reranked':>10}{'total':>8}")
    for (phase_no, phase), stats in sorted(by_phase.items()):
        print(f"{phase_no} {phase:<42}{stats['with_evidence']:>15}{stats['reranked']:>10}{stats['total']:>8}")


if __name__ == "__main__":
    asyncio.run(main())
