"""One-off script: run the real evaluation.run_evaluation harness against
the just-ingested GXP-MFG-DEMO-01 Dummy_data corpus, with REAL (unmocked)
Ollama embeddings and the real LLM reranker cascade. Not part of the app
or test suite; run and discard.

Markers below were chosen by scanning the live corpus for identifier
tokens that appear in exactly ONE chunk (verified via a one-off DB scan),
so relevant_ids has size 1 for every ID- case and recall@k means
something (previous run used broad substrings like "privileged" that
matched 200+ chunks, making recall@5 mathematically near-zero regardless
of retrieval quality)."""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from app.db import acquire_pool_or_none  # noqa: E402
from app.retrieval.evaluation import EvalCase, format_report, run_evaluation  # noqa: E402

SYSTEM_ID = "GXP-MFG-DEMO-01"

CASES = [
    EvalCase("ID-01", "What does workflow WF-AG-006 cover in the Administrator Guide?", SYSTEM_ID, ["WF-AG-006"]),
    EvalCase("ID-02", "What is access-review criterion CRIT-AMR-003 about?", SYSTEM_ID, ["CRIT-AMR-003"]),
    EvalCase("ID-03", "What does change-control decision DEC-CHG-005 record?", SYSTEM_ID, ["DEC-CHG-005"]),
    EvalCase("ID-04", "What assumption is documented under ASM-CS-002?", SYSTEM_ID, ["ASM-CS-002"]),
    EvalCase("ID-05", "What does defect log quality gate DEFL-QG-11 check?", SYSTEM_ID, ["DEFL-QG-11"]),
    EvalCase("ID-06", "What does deviation log quality gate DEVL-QG-02 verify?", SYSTEM_ID, ["DEVL-QG-02"]),
    EvalCase("ID-07", "What open item does VER-DIA-009 track in the Data Integrity Assessment?", SYSTEM_ID, ["VER-DIA-009"]),
    EvalCase("ID-08", "What assumption does ASM-DRR-004 require handling for?", SYSTEM_ID, ["ASM-DRR-004"]),
    EvalCase("ID-09", "What business process is BPR-MES-007 in the IT Implementation Plan?", SYSTEM_ID, ["BPR-MES-007"]),
    EvalCase("ID-10", "What blocking decision does hold point HP-IQ-04 represent?", SYSTEM_ID, ["HP-IQ-04"]),
    EvalCase(
        "PARA-01",
        "Before someone starts doing privileged administrative work, what has to already be approved and ready, including a way to undo it?",
        SYSTEM_ID,
        ["Prepare privileged work"],
    ),
    EvalCase(
        "PARA-02",
        "What must be true about the twelve source documents for the design review to consider the baseline complete?",
        SYSTEM_ID,
        ["complete current v0.1 DUMMY design baseline"],
    ),
    EvalCase(
        "PARA-03",
        "During the incident review, how did the team decide this counted as a real IT incident in the first place?",
        SYSTEM_ID,
        ["Does the observation qualify as an IT incident"],
    ),
]


async def main() -> None:
    pool = await acquire_pool_or_none()
    if pool is None:
        print("Postgres unreachable.")
        return
    report = await run_evaluation(pool, CASES, k=5)
    print(format_report(report))
    print()
    for row in report.per_case:
        print(f"{row['query_id']}: relevant_ids={len(row['relevant_ids'])}")
        for config in ("dense_only", "lexical_only", "hybrid_reranked"):
            c = row[config]
            print(f"  {config:16s} p@5={c['precision_at_k']:.2f} r@5={c['recall_at_k']:.2f} rr={c['reciprocal_rank']:.2f}")


if __name__ == "__main__":
    asyncio.run(main())
