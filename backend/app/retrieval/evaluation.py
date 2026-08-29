"""
Retrieval quality evaluation harness (Phase 06.1, plan 06.1-07, HARD-04,
RAG-03, RAG-04).

Ticket: n/a (roadmap phase 06.1) | Requirements: HARD-04, RAG-03, RAG-04
Source: 06.1-07-PLAN.md Task 1 <action>; 06.1-RESEARCH.md's "Validation
Architecture" HARD-04 row and Assumption A4 (RRF_K unvalidated against
this project's own corpus).

This module is evaluation-only: it is imported by
`backend/tests/test_retrieval_eval.py` and by nothing in the request path
(`app/routes`, `app/agents`, `app/graph` are all untouched by this plan --
verified by an acceptance-criteria grep). Task 1 (this file's current
shape) implements the four pure IR metric functions and the labelled-
fixture loader only -- no retrieval-pipeline import, no I/O beyond
`load_cases`' own file read. Task 2 adds `run_evaluation`, the live
runner driving the real hybrid-search entry point plus its two
underlying candidate-search functions end to end (see 06.1-07-SUMMARY.md
for the two task-level commits).

Relevance model: a chunk counts as relevant to a case when any of that
case's `relevant_markers` appears as a substring of the chunk's own
`content`, after both sides are lowercased and whitespace-normalised
(`" ".join(text.split())`). This is deliberately substring-based, not
chunk-id-based, so ground truth survives a change to chunk boundaries
without needing to be relabelled (06.1-07-PLAN.md Task 1 <behavior>).
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Set, Tuple

logger = logging.getLogger(__name__)

# The evaluation's own top-k cutoff for precision@k/recall@k. A named
# constant, not a literal, so a caller building an EvalReport for a
# different k does not have to hunt for the number (06.1-07-PLAN.md's own
# `EVAL_K: int = 5` artifact spec).
EVAL_K: int = 5


@dataclass
class EvalCase:
    query_id: str
    query: str
    system_id: str
    relevant_markers: List[str]


@dataclass
class ConfigReport:
    config: str
    precision_at_k: float
    recall_at_k: float
    mrr: float
    cases: int


@dataclass
class EvalReport:
    k: int
    configs: List[ConfigReport]
    per_case: List[Dict[str, Any]] = field(default_factory=list)


def precision_at_k(retrieved_ids: List[str], relevant_ids: Set[str], k: int) -> float:
    """Fraction of the top-`k` retrieved ids that are relevant.

    Divides by the number of ids actually present in the top-`k` slice
    (never by `k` itself), so an empty or shorter-than-`k` retrieved list
    returns `0.0` rather than raising a division-by-zero error.
    """
    if k <= 0:
        return 0.0
    top_k = retrieved_ids[:k]
    if not top_k:
        return 0.0
    hits = sum(1 for retrieved_id in top_k if retrieved_id in relevant_ids)
    return hits / len(top_k)


def recall_at_k(retrieved_ids: List[str], relevant_ids: Set[str], k: int) -> float:
    """Fraction of the true relevant set found within the top-`k`
    retrieved ids. Returns `0.0` (never raises) when `relevant_ids` is
    empty -- there is nothing to recall, not a perfect or undefined score.
    """
    if not relevant_ids:
        return 0.0
    top_k = retrieved_ids[:k]
    hits = sum(1 for retrieved_id in top_k if retrieved_id in relevant_ids)
    return hits / len(relevant_ids)


def reciprocal_rank(retrieved_ids: List[str], relevant_ids: Set[str]) -> float:
    """`1 / rank` of the first relevant id in `retrieved_ids` (1-indexed),
    or `0.0` if no relevant id appears anywhere in the list."""
    for index, retrieved_id in enumerate(retrieved_ids):
        if retrieved_id in relevant_ids:
            return 1.0 / (index + 1)
    return 0.0


def mean_reciprocal_rank(rows: List[Tuple[List[str], Set[str]]]) -> float:
    """Mean of `reciprocal_rank` over every `(retrieved_ids, relevant_ids)`
    row. Returns `0.0` for an empty `rows` list rather than dividing by
    zero."""
    if not rows:
        return 0.0
    return sum(reciprocal_rank(retrieved_ids, relevant_ids) for retrieved_ids, relevant_ids in rows) / len(rows)


def load_cases(path: str) -> List[EvalCase]:
    """Read `path` (the `labelled_queries.json` shape: `{"system_id",
    "k", "cases": [{"query_id", "query", "relevant_markers"}, ...]}`) and
    return one `EvalCase` per entry, each carrying the file's top-level
    `system_id`.

    Raises `ValueError` naming `path` on a missing file, malformed JSON, a
    missing required key, or a case entry with the wrong shape -- never a
    bare `KeyError`/`FileNotFoundError`, so a caller's error message
    always names which fixture file was the problem.
    """
    import json

    try:
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except FileNotFoundError as exc:
        raise ValueError(f"load_cases: file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"load_cases: malformed JSON in {path}: {exc}") from exc

    try:
        system_id = payload["system_id"]
        raw_cases = payload["cases"]
    except (KeyError, TypeError) as exc:
        raise ValueError(f"load_cases: missing required top-level key in {path}: {exc}") from exc

    cases: List[EvalCase] = []
    for index, raw_case in enumerate(raw_cases):
        try:
            cases.append(
                EvalCase(
                    query_id=raw_case["query_id"],
                    query=raw_case["query"],
                    system_id=system_id,
                    relevant_markers=list(raw_case["relevant_markers"]),
                )
            )
        except (KeyError, TypeError) as exc:
            raise ValueError(f"load_cases: malformed case at index {index} in {path}: {exc}") from exc

    return cases


def format_report(report: EvalReport) -> str:
    """A fixed-width table string summarising `report` -- suitable for
    pasting directly into a SUMMARY.md or backend/README.md baseline
    section."""
    header = f"{'config':<18}{'precision@k':>14}{'recall@k':>12}{'mrr':>10}{'cases':>8}"
    lines = [f"Retrieval Evaluation Report (k={report.k})", "", header, "-" * len(header)]
    for config_report in report.configs:
        lines.append(
            f"{config_report.config:<18}"
            f"{config_report.precision_at_k:>14.4f}"
            f"{config_report.recall_at_k:>12.4f}"
            f"{config_report.mrr:>10.4f}"
            f"{config_report.cases:>8d}"
        )
    return "\n".join(lines)
