"""
Retrieval quality evaluation harness (Phase 06.1, plan 06.1-07, HARD-04,
RAG-03, RAG-04).

Ticket: n/a (roadmap phase 06.1) | Requirements: HARD-04, RAG-03, RAG-04
Source: 06.1-07-PLAN.md Tasks 1-2 <action>; 06.1-RESEARCH.md's "Validation
Architecture" HARD-04 row and Assumption A4 (RRF_K unvalidated against
this project's own corpus).

This module is evaluation-only: it is imported by
`backend/tests/test_retrieval_eval.py` and by nothing in the request path
(`app/routes`, `app/agents`, `app/graph` are all untouched by this plan --
verified by an acceptance-criteria grep). It measures the retrieval
pipeline `app.retrieval.hybrid_search`/`lexical`/`qdrant_store` already
implement; it never retunes any of their constants (`RRF_K`,
`RERANK_RELEVANCE_THRESHOLD` stay exactly as plan 06.1-03 set them -- see
this plan's own scope boundary).

`run_evaluation` issues Postgres/Qdrant/embedding READS only: it drives
`hybrid_retrieve`/`bm25_search`/`dense_search` directly, hydrates a single
whole-corpus content scan to determine each case's true relevant-chunk set,
and writes nothing to any store. Corpus setup/teardown (uploading and
deleting the eval fixture documents) is the caller's -- specifically
`backend/tests/test_retrieval_eval.py`'s own pytest fixture's --
responsibility, never this module's.

Relevance model: a chunk counts as relevant to a case when any of that
case's `relevant_markers` appears as a substring of the chunk's own
`content`, after both sides are lowercased and whitespace-normalised
(`" ".join(text.split())`). This is deliberately substring-based, not
chunk-id-based, so ground truth survives a change to chunk boundaries
without needing to be relabelled (06.1-07-PLAN.md Task 1 <behavior>).
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from app.retrieval.embeddings import call_embedding
from app.retrieval.hybrid_search import hybrid_retrieve
from app.retrieval.lexical import bm25_search
from app.retrieval.qdrant_store import dense_search, get_qdrant_client

logger = logging.getLogger(__name__)

# The evaluation's own top-k cutoff for precision@k/recall@k. A named
# constant, not a literal, so a caller building an EvalReport for a
# different k does not have to hunt for the number (06.1-07-PLAN.md's own
# `EVAL_K: int = 5` artifact spec).
EVAL_K: int = 5

# `dense_search`/`bm25_search` are asked for more than EVAL_K candidates so
# recall@k and MRR can see past the top-k cutoff -- a candidate ranked 6th
# still contributes to MRR even though it does not contribute to
# precision@5/recall@5.
_CANDIDATE_DEPTH: int = 20


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


def _normalize(text: Optional[str]) -> str:
    """Lowercase and collapse all whitespace runs to a single space --
    the same normalisation both sides of the substring relevance check
    apply, so a chunk boundary landing mid-sentence or a stray double
    space never silently zeroes a score (06.1-07-PLAN.md Task 2
    <behavior>)."""
    return " ".join((text or "").lower().split())


async def _global_relevant_ids(pool: Any, system_id: str, cases: List[EvalCase]) -> Dict[str, Set[str]]:
    """One whole-corpus content scan (a single Postgres query, not one
    per case) resolving each case's TRUE relevant-chunk-id set --
    independent of what any particular retrieval configuration actually
    returns, so `recall_at_k`'s denominator reflects the corpus's real
    relevant set rather than only whatever a specific run happened to
    surface."""
    rows = await pool.fetch(
        "SELECT c.chunk_id, c.content FROM document_chunks c JOIN documents d ON d.id = "
        "c.document_id WHERE d.system_id = $1",
        system_id,
    )
    normalized_corpus = [(str(row["chunk_id"]), _normalize(row["content"])) for row in rows]

    relevant_by_case: Dict[str, Set[str]] = {}
    for case in cases:
        normalized_markers = [_normalize(marker) for marker in case.relevant_markers]
        relevant_by_case[case.query_id] = {
            chunk_id
            for chunk_id, normalized_content in normalized_corpus
            if any(marker in normalized_content for marker in normalized_markers)
        }
    return relevant_by_case


async def _dense_only_ids(case: EvalCase, k: int) -> List[str]:
    """The `dense_only` configuration: embed the query and search Qdrant
    directly, with no fusion and no reranking. Returns `[]` (never
    raises) if the embedding degrades or Qdrant is unreachable -- the
    same degrade-don't-raise contract every other module in this
    subsystem follows."""
    embedding = await call_embedding(case.query, task_type="RETRIEVAL_QUERY")
    if embedding.degraded:
        return []
    client = await get_qdrant_client()
    if client is None:
        return []
    hits = await dense_search(client, embedding.vector, case.system_id, limit=max(k, _CANDIDATE_DEPTH))
    ordered = sorted(hits, key=lambda hit: hit.score, reverse=True)
    return [hit.chunk_id for hit in ordered]


async def _lexical_only_ids(pool: Any, case: EvalCase, k: int) -> List[str]:
    """The `lexical_only` configuration: BM25 search directly, with no
    fusion and no reranking. `bm25_search` already returns its hits
    sorted descending and never raises."""
    hits = await bm25_search(pool, case.query, case.system_id, limit=max(k, _CANDIDATE_DEPTH))
    return [chunk_id for chunk_id, _score in hits]


async def _hybrid_reranked_ids(pool: Any, case: EvalCase) -> List[str]:
    """The `hybrid_reranked` configuration: the real, unmodified
    `hybrid_retrieve` end-to-end (fusion + reranking + the deterministic
    relevance gate), reading `chunk_id` off each surviving evidence item
    in its own returned order.

    Excludes `evidence_type == "graph_relationship"` items:
    `expand_graph_evidence` appends those unconditionally, after -- not
    subject to -- the fusion/reranking gate this evaluation measures, and
    their `chunk_id` is a graph node id rather than a real
    `document_chunks` row, so no `relevant_markers` substring check can
    ever apply to one. Counting them as "retrieved" candidates would
    penalise `hybrid_reranked` against `dense_only`/`lexical_only` (which
    never see graph evidence at all) for a category of evidence this
    evaluation was never measuring in the first place -- this plan
    measures document-chunk retrieval quality, not graph-relationship
    enrichment (a separate, already-tested Bible Section 15.5 concern,
    see 06.1-03-SUMMARY.md)."""
    outcome = await hybrid_retrieve(pool, case.query, case.system_id)
    return [item["chunk_id"] for item in outcome.evidence if item.get("evidence_type") != "graph_relationship"]


async def run_evaluation(pool: Any, cases: List[EvalCase], k: int = EVAL_K) -> EvalReport:
    """Run every `cases` entry against three retrieval configurations --
    `dense_only`, `lexical_only`, `hybrid_reranked` -- and return an
    `EvalReport` carrying one `ConfigReport` per configuration plus a
    `per_case` breakdown so a regression can be attributed to a specific
    query rather than only to an aggregate drop.

    Read-only: every candidate list comes from `dense_search`/
    `bm25_search`/`hybrid_retrieve` directly; this function issues no
    Postgres write and no Qdrant write of its own -- see module
    docstring.
    """
    if not cases:
        return EvalReport(k=k, configs=[], per_case=[])

    system_id = cases[0].system_id
    relevant_by_case = await _global_relevant_ids(pool, system_id, cases)

    rows_by_config: Dict[str, List[Tuple[List[str], Set[str]]]] = {
        "dense_only": [],
        "lexical_only": [],
        "hybrid_reranked": [],
    }
    per_case: List[Dict[str, Any]] = []

    for case in cases:
        relevant_ids = relevant_by_case.get(case.query_id, set())

        dense_ids = await _dense_only_ids(case, k)
        lexical_ids = await _lexical_only_ids(pool, case, k)
        hybrid_ids = await _hybrid_reranked_ids(pool, case)

        rows_by_config["dense_only"].append((dense_ids, relevant_ids))
        rows_by_config["lexical_only"].append((lexical_ids, relevant_ids))
        rows_by_config["hybrid_reranked"].append((hybrid_ids, relevant_ids))

        per_case.append(
            {
                "query_id": case.query_id,
                "query": case.query,
                "relevant_ids": sorted(relevant_ids),
                "dense_only": {
                    "retrieved": dense_ids[:k],
                    "precision_at_k": precision_at_k(dense_ids, relevant_ids, k),
                    "recall_at_k": recall_at_k(dense_ids, relevant_ids, k),
                    "reciprocal_rank": reciprocal_rank(dense_ids, relevant_ids),
                },
                "lexical_only": {
                    "retrieved": lexical_ids[:k],
                    "precision_at_k": precision_at_k(lexical_ids, relevant_ids, k),
                    "recall_at_k": recall_at_k(lexical_ids, relevant_ids, k),
                    "reciprocal_rank": reciprocal_rank(lexical_ids, relevant_ids),
                },
                "hybrid_reranked": {
                    "retrieved": hybrid_ids[:k],
                    "precision_at_k": precision_at_k(hybrid_ids, relevant_ids, k),
                    "recall_at_k": recall_at_k(hybrid_ids, relevant_ids, k),
                    "reciprocal_rank": reciprocal_rank(hybrid_ids, relevant_ids),
                },
            }
        )

    configs: List[ConfigReport] = []
    for config_name in ("dense_only", "lexical_only", "hybrid_reranked"):
        rows = rows_by_config[config_name]
        precision = sum(precision_at_k(retrieved, relevant, k) for retrieved, relevant in rows) / len(rows)
        recall = sum(recall_at_k(retrieved, relevant, k) for retrieved, relevant in rows) / len(rows)
        mrr = mean_reciprocal_rank(rows)
        configs.append(
            ConfigReport(config=config_name, precision_at_k=precision, recall_at_k=recall, mrr=mrr, cases=len(rows))
        )

    return EvalReport(k=k, configs=configs, per_case=per_case)
