"""
Hybrid retrieval entry point (Phase 06.1, plans 06.1-02/06.1-03,
RAG-03/04/05, RAG-06, AGT-01, D-05/D-06/D-08/D-09).

Ticket: n/a (roadmap phase 06.1) | Requirements: RAG-03, RAG-04, RAG-05,
RAG-06, AGT-01
Source: 06.1-02-PLAN.md Task 1 <action> and 06.1-03-PLAN.md Tasks 1-3
<action>; AegisX-AI-Project-Bible-v6.md Section 15.2/15.3 (fusion +
rerank pipeline) and Section 15.7 (evidence provenance field set);
06.1-UI-SPEC.md's Investigation Trace stage mapping.

This module owns the ONE seam plan 06.1-01's `app/retrieval/embeddings.py`
and `app/retrieval/qdrant_store.py` were built for A1 to call
(06.1-01-SUMMARY.md "Next Phase Readiness"). `hybrid_retrieve()` runs
dense (Qdrant) and lexical (`app.retrieval.lexical.bm25_search`) search
concurrently, fuses the two ranked candidate lists with Reciprocal Rank
Fusion, hydrates the union from Postgres, applies the deterministic
relevance gate, and returns Section 15.7 evidence dicts plus a
six-`stage_id` trace table. Plan 06.1-02 shipped the dense-only slice of
this seam with `combining`/`reranking` always emitted as `skipped`; plan
06.1-03 fills both stages for real (RRF fusion + one batched reranking
call) behind this exact same function signature.

Deterministic-first boundary (D-08, CLAUDE.md): the fusion math
(`reciprocal_rank_fusion`) and the relevance gate are pure Python
arithmetic over numeric scores; no model ever decides whether a chunk is
relevant on its own. `rerank_batch` (Task 2) is the one place a model
scores candidate relevance -- always as exactly one batched call, its
output clamped/validated before use, never trusted to make the final
sufficiency decision itself. `why_selected` sentences are composed in
Python from the retrieval method and the real score(s), never generated
by a model (D-09's no-fabricated-evidence rule extended to this field).

Never raises to its caller (`app.agents.minimal_specialists.run_a1`):
every failure path -- degraded embedding, unreachable Qdrant, a Qdrant or
BM25 search error, zero candidates, or a Postgres hydration error -- is
caught here and returns an insufficient-evidence `RetrievalOutcome`
instead of propagating an exception. A degraded embedding or unreachable
Qdrant no longer forces an insufficient-evidence result on its own (Task
1's "degraded half-pipeline" behavior): the lexical leg can still surface
real evidence, and only a pipeline where BOTH legs come up empty degrades
all the way to insufficient. `trace` always includes an
`evaluating`/`complete` row even on these paths: the relevance check
genuinely ran (against zero or degraded candidates), so a negative result
is a real, reportable outcome, not a failure to report at all
(06.1-UI-SPEC.md Interaction Notes, stage 5's own note).
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from app.retrieval.embeddings import call_embedding
from app.retrieval.lexical import bm25_search
from app.retrieval.qdrant_store import dense_search, get_qdrant_client

logger = logging.getLogger(__name__)

# Bible Section 15.2/15.3 sizing ("Vector Search -> 20 candidates"); the
# BM25 leg (`app.retrieval.lexical.BM25_CANDIDATE_LIMIT`) reuses the same
# candidate depth before fusion.
DENSE_CANDIDATE_LIMIT: int = 20

# Cosine similarity floor a dense hit must clear to be treated as relevant
# evidence on its own (D-08's deterministic gate). A candidate found by
# BM25 (`bm25_score is not None`) is kept regardless of this threshold --
# `bm25_search` already drops non-positive/no-overlap scores, so a
# lexical match's own presence in that list is itself the signal, on a
# scale (unbounded, corpus-dependent) this cosine-calibrated constant was
# never meant to gate. Superseded as the *combined* gate's input by
# `RERANK_RELEVANCE_THRESHOLD` once plan 06.1-03 Task 2's reranker lands;
# this constant remains that gate's documented fallback when reranking
# degrades (Task 2 <action>).
DENSE_RELEVANCE_THRESHOLD: float = 0.55

# Standard IR technique (06.1-RESEARCH.md Pattern 2): a named module
# constant, not a magic number, so it can be tuned against this project's
# own corpus by the plan 06.1-07 eval harness. k=60 is the conventional
# default (widely used in hybrid-search implementations, including
# Qdrant's own hybrid-query documentation patterns) -- not a value
# derived from this corpus (06.1-RESEARCH.md Assumption A4, Low-Medium
# confidence).
RRF_K: int = 60

# Bible Section 15.4's evidence-list cap.
MAX_EVIDENCE_ITEMS: int = 8

# 06.1-UI-SPEC.md Interaction Notes, "Investigation Trace stage mapping"
# table -- the six ordered stage ids and their exact UI labels, transcribed
# verbatim. `understanding` and `preparing` are assembled by the HTTP route
# (plan 06.1-02 Task 2) from A0's intent and the synthesis step
# respectively; this module only ever emits `searching`/`combining`/
# `reranking`/`evaluating` rows, but the full six-entry table is declared
# here as the one place both the route and every test import it from.
STAGE_LABELS: Dict[str, str] = {
    "understanding": "Understanding question",
    "searching": "Searching knowledge",
    "combining": "Combining semantic and keyword evidence",
    "reranking": "Reranking candidates",
    "evaluating": "Evaluating evidence",
    "preparing": "Preparing assessment",
}


def _stage(stage_id: str, status: str, detail: Optional[str] = None) -> Dict[str, Any]:
    """One `InvestigationStage`-shaped dict. `label` is always read from
    `STAGE_LABELS`, never restated as a literal at a call site."""
    return {"stage_id": stage_id, "label": STAGE_LABELS[stage_id], "status": status, "detail": detail}


@dataclass
class RetrievalOutcome:
    evidence: List[Dict[str, Any]]
    trace: List[Dict[str, Any]]
    insufficient_evidence: bool
    model_attribution: str


def _insufficient(
    stages: List[Dict[str, Any]], evaluating_detail: str, model_attribution: str
) -> RetrievalOutcome:
    stages.append(_stage("evaluating", "complete", evaluating_detail))
    return RetrievalOutcome(
        evidence=[], trace=stages, insufficient_evidence=True, model_attribution=model_attribution
    )


def reciprocal_rank_fusion(
    dense_ranked_ids: List[str], bm25_ranked_ids: List[str], k: int = RRF_K
) -> Dict[str, float]:
    """Combine two independently-ranked candidate id lists into one fused
    score per id, without needing to normalize the two lists' incomparable
    score scales -- Qdrant's cosine similarity is bounded 0-1, BM25's own
    score is unbounded and corpus-dependent. RRF sidesteps that
    normalization problem entirely by scoring on RANK POSITION, not on
    the raw score value (06.1-RESEARCH.md Pattern 2, "Alternatives
    Considered": a weighted sum would need per-corpus normalisation and a
    tuned weight; RRF does not).

    Pure function -- no I/O, no async keyword anywhere in this body, no
    mutation of its inputs, same inputs always produce the same output
    (`reciprocal_rank_fusion([], []) == {}`). Callers are responsible for
    pre-sorting each input list
    by its own descending relevance score before calling this function --
    RRF fuses RANK, so an unsorted input silently produces a meaningless
    fusion.
    """
    scores: Dict[str, float] = {}
    for rank, chunk_id in enumerate(dense_ranked_ids):
        scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank + 1)
    for rank, chunk_id in enumerate(bm25_ranked_ids):
        scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank + 1)
    return scores


def _why_selected(
    dense_score: Optional[float], bm25_score: Optional[float], section: Optional[str], document_title: str
) -> str:
    """Composed in Python from the retrieval method and the real score(s)
    -- never generated by a model (D-09)."""
    section_label = section if section else "an unlabeled section"
    if dense_score is not None and bm25_score is not None:
        return (
            f"Semantic vector match (cosine {dense_score:.2f}) and keyword match "
            f'(BM25 {bm25_score:.2f}) against section "{section_label}" of {document_title}.'
        )
    if bm25_score is not None:
        return (
            f'Keyword match (BM25 {bm25_score:.2f}) against section "{section_label}" '
            f"of {document_title}."
        )
    return (
        f'Semantic vector match (cosine {dense_score:.2f}) against section '
        f'"{section_label}" of {document_title}.'
    )


def _build_evidence_item(
    chunk_id: str, dense_score: Optional[float], bm25_score: Optional[float], row: Any
) -> Dict[str, Any]:
    """One `RetrievalEvidenceItem`-shaped dict, read entirely from the
    Postgres row hydrated for `chunk_id` -- the vector store and the BM25
    index are indexes, not the source of truth (Task 1 <behavior>).
    `retrieval_method` reflects what actually happened for this candidate:
    `"hybrid"` when both scores are present, `"semantic"` when only
    dense, `"keyword"` when only BM25 (this is the value the Evidence
    View badge renders)."""
    document_title = row["title"] or ""
    section = row["section"]
    if dense_score is not None and bm25_score is not None:
        retrieval_method = "hybrid"
    elif dense_score is not None:
        retrieval_method = "semantic"
    else:
        retrieval_method = "keyword"
    return {
        "evidence_id": f"EV-{chunk_id[:8]}",
        "document_id": row["document_id"],
        "chunk_id": chunk_id,
        "document_title": document_title,
        "section": section,
        "page": row["page"],
        "content": row["content"],
        "retrieval_method": retrieval_method,
        "dense_score": round(dense_score, 4) if dense_score is not None else None,
        "bm25_score": round(bm25_score, 4) if bm25_score is not None else None,
        "evidence_type": "document",
        "why_selected": _why_selected(dense_score, bm25_score, section, document_title),
    }


async def _dense_leg(embedding: Any, client: Any, system_id: str) -> List[Any]:
    """The dense candidate leg run alongside `bm25_search` via
    `asyncio.gather`. Returns `[]` (not an exception) when the embedding
    already degraded or Qdrant is unreachable -- `hybrid_retrieve` already
    detects and reports both states in the `searching` stage before this
    coroutine ever runs; only a genuine `dense_search` failure should
    surface to `asyncio.gather`'s `return_exceptions=True` handling."""
    if embedding.degraded or client is None:
        return []
    return await dense_search(client, embedding.vector, system_id, limit=DENSE_CANDIDATE_LIMIT)


async def hybrid_retrieve(pool: Any, query: str, system_id: str) -> RetrievalOutcome:
    """Dense + lexical hybrid retrieval: embed the query, then run Qdrant
    dense search and BM25 lexical search CONCURRENTLY, fuse the two
    ranked candidate id lists with Reciprocal Rank Fusion, hydrate the
    union from Postgres, and apply the deterministic relevance gate. See
    module docstring for the never-raises contract and the
    degraded-half-pipeline behavior (a degraded embedding or unreachable
    Qdrant no longer forces insufficient evidence on its own -- only both
    legs coming up empty does).
    """
    stages: List[Dict[str, Any]] = []

    embedding = await call_embedding(query, task_type="RETRIEVAL_QUERY")
    client = None if embedding.degraded else await get_qdrant_client()

    dense_result, bm25_result = await asyncio.gather(
        _dense_leg(embedding, client, system_id),
        bm25_search(pool, query, system_id),
        return_exceptions=True,
    )

    dense_search_failed = isinstance(dense_result, Exception)
    if dense_search_failed:
        logger.warning(
            "A1 dense_search failed (system_id=%s): %s",
            system_id,
            type(dense_result).__name__,
            exc_info=dense_result,
        )
        dense_hits: List[Any] = []
    else:
        # `dense_search` (qdrant_store) already returns hits ranked
        # descending by Qdrant's own scoring, but this function guarantees
        # the "ordered by descending score" property itself (Task 1
        # <behavior>) rather than merely trusting the caller's ordering --
        # RRF fuses on rank position, so an unsorted list would silently
        # fuse on the wrong ranking.
        dense_hits = sorted(dense_result, key=lambda hit: hit.score, reverse=True)

    if isinstance(bm25_result, Exception):
        logger.warning(
            "A1 bm25_search failed (system_id=%s): %s",
            system_id,
            type(bm25_result).__name__,
            exc_info=bm25_result,
        )
        bm25_hits: List[Tuple[str, float]] = []
    else:
        bm25_hits = bm25_result

    if embedding.degraded:
        stages.append(_stage("searching", "skipped", f"{embedding.failure_reason}; lexical-only"))
        model_attribution = f"embedding-degraded:{embedding.failure_reason}"
    elif client is None:
        stages.append(_stage("searching", "skipped", "qdrant unavailable; lexical-only"))
        model_attribution = "qdrant-unavailable"
    elif dense_search_failed:
        stages.append(_stage("searching", "skipped", "qdrant search failed; lexical-only"))
        model_attribution = "retrieval-error"
    else:
        stages.append(_stage("searching", "complete", f"{len(dense_hits)} candidate chunks"))
        model_attribution = embedding.model_id

    stages.append(
        _stage(
            "combining",
            "complete",
            f"{len(dense_hits)} semantic + {len(bm25_hits)} keyword candidates fused",
        )
    )
    stages.append(_stage("reranking", "skipped", "reranking not yet enabled"))

    dense_ids = [hit.chunk_id for hit in dense_hits]
    bm25_ids = [chunk_id for chunk_id, _score in bm25_hits]
    fused_scores = reciprocal_rank_fusion(dense_ids, bm25_ids)

    if not fused_scores:
        return _insufficient(
            stages, "0 of 0 candidates cleared the relevance threshold", model_attribution
        )

    dense_score_by_id = {hit.chunk_id: hit.score for hit in dense_hits}
    bm25_score_by_id = dict(bm25_hits)

    try:
        rows = await pool.fetch(
            "SELECT c.chunk_id, c.document_id, c.content, c.section, c.page, c.chunk_index, "
            "c.parent_chunk_id, d.title FROM document_chunks c JOIN documents d ON d.id = "
            "c.document_id WHERE c.chunk_id = ANY($1::uuid[])",
            list(fused_scores.keys()),
        )
    except Exception as exc:  # noqa: BLE001 - see module docstring's never-raises contract
        logger.warning("A1 Postgres hydration failed (system_id=%s): %s", system_id, type(exc).__name__, exc_info=True)
        return _insufficient(
            stages, "0 of 0 candidates cleared the relevance threshold", "hydration-error"
        )

    row_by_chunk_id = {str(row["chunk_id"]): row for row in rows}

    # Every fused id with no matching row is dropped. Ordered by
    # descending fused (RRF) score -- the one score comparable across a
    # dense-only, a lexical-only, and a hybrid candidate alike.
    candidates: List[Tuple[str, float, Optional[float], Optional[float], Any]] = [
        (
            chunk_id,
            fused_score,
            dense_score_by_id.get(chunk_id),
            bm25_score_by_id.get(chunk_id),
            row_by_chunk_id[chunk_id],
        )
        for chunk_id, fused_score in fused_scores.items()
        if chunk_id in row_by_chunk_id
    ]
    candidates.sort(key=lambda c: c[1], reverse=True)

    total = len(candidates)
    # The relevance gate (D-08): a candidate carrying a dense_score must
    # clear DENSE_RELEVANCE_THRESHOLD; a candidate found ONLY by BM25 is
    # kept on the strength of that lexical match alone -- bm25_search
    # already dropped non-positive/no-overlap scores, so a lexical
    # match's own presence in that list is itself the signal, on a scale
    # (unbounded, corpus-dependent) this cosine-calibrated constant was
    # never meant to gate. Plan 06.1-03 Task 2's batched reranker
    # supersedes this as the gate for ALL fused candidates, dense or
    # lexical alike.
    kept = [
        c
        for c in candidates
        if (c[2] is not None and c[2] >= DENSE_RELEVANCE_THRESHOLD) or c[3] is not None
    ][:MAX_EVIDENCE_ITEMS]

    stages.append(
        _stage("evaluating", "complete", f"{len(kept)} of {total} candidates cleared the relevance threshold")
    )

    if not kept:
        return RetrievalOutcome(
            evidence=[], trace=stages, insufficient_evidence=True, model_attribution=model_attribution
        )

    evidence = [
        _build_evidence_item(chunk_id, dense_score, bm25_score, row)
        for chunk_id, _fused_score, dense_score, bm25_score, row in kept
    ]
    return RetrievalOutcome(
        evidence=evidence, trace=stages, insufficient_evidence=False, model_attribution=model_attribution
    )
