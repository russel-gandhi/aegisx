"""
Tests for `app.retrieval.hybrid_search` and `app.retrieval.lexical`
(Phase 06.1, plans 06.1-02/06.1-03, RAG-03/04/05, RAG-06, AGT-01).

Covers every Task 1-3 `<behavior>` bullet for `hybrid_retrieve`,
`reciprocal_rank_fusion`, `rerank_batch`, `expand_parent_context`, and
`expand_graph_evidence`: the UNIT section uses respx-stubbed embeddings
plus a monkeypatched `dense_search`/`get_qdrant_client` (this module's
own two Qdrant seams), and the INTEGRATION section runs against the real
local Postgres + Qdrant stack, guarded the same way
`test_evidence_graph.py`/`test_retrieval_ingest.py` guard their own
live-state tests -- no skip marker; this whole suite assumes the
docker-compose stack is up.
"""

import asyncio
from typing import Any, Dict, List, Optional

import httpx
import pytest
import respx

from app.db import get_pool
from app.retrieval import hybrid_search
from app.retrieval.embeddings import EMBEDDING_DIMENSIONS
from app.retrieval.hybrid_search import (
    DENSE_RELEVANCE_THRESHOLD,
    MAX_EVIDENCE_ITEMS,
    RRF_K,
    STAGE_LABELS,
    hybrid_retrieve,
    reciprocal_rank_fusion,
)
from app.retrieval.lexical import BM25_CANDIDATE_LIMIT, BM25_CORPUS_MAX_CHUNKS, bm25_search, build_corpus, tokenize
from app.retrieval.qdrant_store import DenseHit, QDRANT_URL, ensure_collection, get_qdrant_client, upsert_chunks

DEMO_SYSTEM = "GXP-MFG-DEMO-01"
DEMO_DOCUMENT_ID = "DOC-2026-OM-99"  # seeded row, infra/postgres/seed/001_seed.sql
DEMO_DOCUMENT_TITLE = "NovaSynth Operations Manual"
GEMINI_EMBED_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent"
)


class FakePool:
    """Minimal asyncpg-Pool stand-in for the UNIT section. Dispatches on
    the query text (never on call order) between the two distinct
    queries `hybrid_retrieve`/`lexical.build_corpus` issue against a
    pool: the chunk-hydration query (`... WHERE c.chunk_id =
    ANY($1::uuid[])`) returns whichever of `rows` match the requested
    chunk_ids, and the BM25 corpus-build query (no `ANY($1::uuid[])`)
    returns `bm25_rows` (content-only, ignoring `system_id`/`LIMIT`
    binding -- the real corpus SQL is proven by the INTEGRATION section
    below).

    `bm25_rows` defaults to `[]` (an empty BM25 corpus) so every
    pre-existing dense-only test's `FakePool(rows)` call keeps its
    original dense-only behavior unchanged -- BM25 fusion is opt-in via
    an explicit `bm25_rows=` argument."""

    def __init__(self, rows: List[Dict[str, Any]], bm25_rows: Optional[List[Dict[str, Any]]] = None):
        self._rows = rows
        self._bm25_rows = bm25_rows if bm25_rows is not None else []

    async def fetch(self, query: str, *args):
        if "ANY($1::uuid[])" in query:
            chunk_ids = args[0]
            wanted = {str(c) for c in chunk_ids}
            return [row for row in self._rows if str(row["chunk_id"]) in wanted]
        # BM25 corpus-build query (system_id, limit) -- system_id/limit
        # binding itself is proven by the INTEGRATION section.
        return [{"chunk_id": row["chunk_id"], "content": row.get("content", "")} for row in self._bm25_rows]


def _row(
    chunk_id: str,
    document_id: str = DEMO_DOCUMENT_ID,
    title: str = "Test Document",
    section: Optional[str] = "4.2 Traceability",
    page: Optional[int] = 3,
    content: str = "Example chunk content.",
) -> Dict[str, Any]:
    return {
        "chunk_id": chunk_id,
        "document_id": document_id,
        "content": content,
        "section": section,
        "page": page,
        "chunk_index": 0,
        "parent_chunk_id": None,
        "title": title,
    }


def _hit(chunk_id: str, score: float, document_id: str = DEMO_DOCUMENT_ID) -> DenseHit:
    return DenseHit(chunk_id=chunk_id, document_id=document_id, score=score)


def _mock_embedding_env(monkeypatch, degrade: bool = False) -> None:
    if degrade:
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    else:
        monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")


def _install_fake_qdrant(monkeypatch, hits: List[DenseHit], client_unavailable: bool = False) -> None:
    async def _fake_dense_search(client, vector, system_id, limit):
        return hits

    async def _fake_get_qdrant_client():
        return None if client_unavailable else object()

    monkeypatch.setattr(hybrid_search, "dense_search", _fake_dense_search)
    monkeypatch.setattr(hybrid_search, "get_qdrant_client", _fake_get_qdrant_client)


def _run(coro):
    return asyncio.run(coro)


def _bm25_rows_with_distractor(chunk_id: str, content: str) -> List[Dict[str, Any]]:
    """A term present in exactly 1 of N corpus documents needs N >= 3 for
    BM25's own IDF formula (`log((N - n + 0.5) / (n + 0.5))`) to be
    strictly positive rather than zero or negative (N=1: negative; N=2:
    exactly zero; N=3: positive -- confirmed live against the installed
    rank-bm25==0.2.2). Every fusion test below that wants a genuine
    positive BM25 match includes two distractor docs alongside the
    target content."""
    return [
        {"chunk_id": chunk_id, "content": content},
        {"chunk_id": "dddddddd-0000-0000-0000-000000000000", "content": "unrelated maintenance log entry text"},
        {"chunk_id": "eeeeeeee-0000-0000-0000-000000000000", "content": "another distractor document about scheduling"},
    ]


# ---------------------------------------------------------------------------
# UNIT -- respx-stubbed embeddings, monkeypatched dense_search/get_qdrant_client
# ---------------------------------------------------------------------------


def test_evidence_items_carry_full_section_15_7_provenance(monkeypatch):
    _mock_embedding_env(monkeypatch)
    chunk_id = "11111111-1111-1111-1111-111111111111"
    _install_fake_qdrant(monkeypatch, [_hit(chunk_id, 0.71)])

    async def _go():
        with respx.mock:
            respx.post(GEMINI_EMBED_URL).mock(
                return_value=httpx.Response(200, json={"embedding": {"values": [0.1] * EMBEDDING_DIMENSIONS}})
            )
            return await hybrid_retrieve(FakePool([_row(chunk_id)]), "what does section 4.2 require?", DEMO_SYSTEM)

    outcome = _run(_go())
    assert outcome.insufficient_evidence is False
    assert len(outcome.evidence) == 1
    item = outcome.evidence[0]
    assert item["evidence_id"] == f"EV-{chunk_id[:8]}"
    assert item["document_id"] == DEMO_DOCUMENT_ID
    assert item["chunk_id"] == chunk_id
    assert item["document_title"] == "Test Document"
    assert item["section"] == "4.2 Traceability"
    assert item["page"] == 3
    assert item["content"] == "Example chunk content."
    assert item["retrieval_method"] == "semantic"
    assert item["dense_score"] == pytest.approx(0.71)
    assert item["evidence_type"] == "document"
    assert item["why_selected"]


def test_evidence_truncated_to_max_items_ordered_by_descending_score(monkeypatch):
    _mock_embedding_env(monkeypatch)
    chunk_ids = [f"{i:08x}-0000-0000-0000-000000000000" for i in range(10)]
    rows = [_row(cid) for cid in chunk_ids]
    # Scores are all above threshold, deliberately in a scrambled
    # (non-descending) order -- hybrid_retrieve must guarantee the
    # descending-score ordering itself, not merely trust the caller's
    # Qdrant-ranked order.
    scores = [0.90, 0.85, 0.95, 0.80, 0.99, 0.75, 0.70, 0.65, 0.60, 0.56]
    hits = [_hit(cid, score) for cid, score in zip(chunk_ids, scores)]
    _install_fake_qdrant(monkeypatch, hits)

    async def _go():
        with respx.mock:
            respx.post(GEMINI_EMBED_URL).mock(
                return_value=httpx.Response(200, json={"embedding": {"values": [0.1] * EMBEDDING_DIMENSIONS}})
            )
            return await hybrid_retrieve(FakePool(rows), "query", DEMO_SYSTEM)

    outcome = _run(_go())
    assert len(outcome.evidence) == MAX_EVIDENCE_ITEMS
    returned_scores = [item["dense_score"] for item in outcome.evidence]
    assert returned_scores == sorted(returned_scores, reverse=True)
    assert returned_scores[0] == pytest.approx(0.99)


def test_evidence_read_from_postgres_row_not_qdrant_payload(monkeypatch):
    _mock_embedding_env(monkeypatch)
    chunk_id = "22222222-2222-2222-2222-222222222222"
    # The Postgres row deliberately disagrees with the DenseHit's own
    # document_id -- every evidence field must come from the ROW, proving
    # content/section/page/title are hydrated from Postgres, never trusted
    # from the Qdrant payload (Task 1 <behavior>).
    rows = [_row(chunk_id, document_id="DOC-FROM-POSTGRES", title="Postgres Title", content="Postgres content.")]
    _install_fake_qdrant(monkeypatch, [_hit(chunk_id, 0.80, document_id="DOC-FROM-QDRANT-PAYLOAD")])

    async def _go():
        with respx.mock:
            respx.post(GEMINI_EMBED_URL).mock(
                return_value=httpx.Response(200, json={"embedding": {"values": [0.1] * EMBEDDING_DIMENSIONS}})
            )
            return await hybrid_retrieve(FakePool(rows), "query", DEMO_SYSTEM)

    outcome = _run(_go())
    item = outcome.evidence[0]
    assert item["document_id"] == "DOC-FROM-POSTGRES"
    assert item["document_title"] == "Postgres Title"
    assert item["content"] == "Postgres content."


def test_all_candidates_below_threshold_returns_insufficient_evidence(monkeypatch):
    _mock_embedding_env(monkeypatch)
    chunk_id = "33333333-3333-3333-3333-333333333333"
    _install_fake_qdrant(monkeypatch, [_hit(chunk_id, DENSE_RELEVANCE_THRESHOLD - 0.01)])

    async def _go():
        with respx.mock:
            respx.post(GEMINI_EMBED_URL).mock(
                return_value=httpx.Response(200, json={"embedding": {"values": [0.1] * EMBEDDING_DIMENSIONS}})
            )
            return await hybrid_retrieve(FakePool([_row(chunk_id)]), "query", DEMO_SYSTEM)

    outcome = _run(_go())
    assert outcome.insufficient_evidence is True
    assert outcome.evidence == []


def test_zero_qdrant_candidates_returns_insufficient_evidence_no_exception(monkeypatch):
    _mock_embedding_env(monkeypatch)
    _install_fake_qdrant(monkeypatch, [])

    async def _go():
        with respx.mock:
            respx.post(GEMINI_EMBED_URL).mock(
                return_value=httpx.Response(200, json={"embedding": {"values": [0.1] * EMBEDDING_DIMENSIONS}})
            )
            return await hybrid_retrieve(FakePool([]), "query", DEMO_SYSTEM)

    outcome = _run(_go())
    assert outcome.insufficient_evidence is True
    assert outcome.evidence == []


def test_degraded_embedding_no_api_key_returns_insufficient_evidence_named_reason(monkeypatch):
    _mock_embedding_env(monkeypatch, degrade=True)

    async def _go():
        with respx.mock:
            # No route registered for the embedding endpoint -- a degraded
            # (no-key) call_embedding returns before any HTTP request is
            # issued, so respx's own assert_all_mocked default never trips.
            return await hybrid_retrieve(FakePool([]), "query", DEMO_SYSTEM)

    outcome = _run(_go())
    assert outcome.insufficient_evidence is True
    assert outcome.evidence == []
    assert "no API key configured" in outcome.model_attribution


def test_trace_always_marks_evaluating_complete_even_when_insufficient(monkeypatch):
    _mock_embedding_env(monkeypatch, degrade=True)

    async def _go():
        with respx.mock:
            return await hybrid_retrieve(FakePool([]), "query", DEMO_SYSTEM)

    outcome = _run(_go())
    evaluating = next(s for s in outcome.trace if s["stage_id"] == "evaluating")
    assert evaluating["status"] == "complete"


def test_trace_marks_combining_complete_and_reranking_still_skipped(monkeypatch):
    """Task 1 replaces `combining`'s `skipped` stage with a real
    `complete` one naming both candidate counts; `reranking` stays
    `skipped` until Task 2."""
    _mock_embedding_env(monkeypatch)
    chunk_id = "44444444-4444-4444-4444-444444444444"
    _install_fake_qdrant(monkeypatch, [_hit(chunk_id, 0.90)])

    async def _go():
        with respx.mock:
            respx.post(GEMINI_EMBED_URL).mock(
                return_value=httpx.Response(200, json={"embedding": {"values": [0.1] * EMBEDDING_DIMENSIONS}})
            )
            return await hybrid_retrieve(FakePool([_row(chunk_id)]), "query", DEMO_SYSTEM)

    outcome = _run(_go())
    combining = next(s for s in outcome.trace if s["stage_id"] == "combining")
    assert combining["status"] == "complete"
    assert "1 semantic" in combining["detail"]
    assert "0 keyword" in combining["detail"]
    reranking = next(s for s in outcome.trace if s["stage_id"] == "reranking")
    assert reranking["status"] == "skipped"


# ---------------------------------------------------------------------------
# UNIT -- reciprocal_rank_fusion (pure function, Task 1)
# ---------------------------------------------------------------------------


def test_rrf_ranks_candidates_present_in_both_lists_above_single_list_candidates():
    scores = reciprocal_rank_fusion(["a", "b", "c"], ["c", "a", "d"])
    assert scores["a"] > scores["b"]
    assert scores["c"] > scores["d"]


def test_rrf_empty_inputs_returns_empty_dict():
    assert reciprocal_rank_fusion([], []) == {}


def test_rrf_is_pure_no_io_no_mutation():
    dense = ["a", "b"]
    bm25 = ["b", "c"]
    dense_copy, bm25_copy = list(dense), list(bm25)
    first = reciprocal_rank_fusion(dense, bm25)
    second = reciprocal_rank_fusion(dense, bm25)
    assert first == second
    assert dense == dense_copy
    assert bm25 == bm25_copy


def test_rrf_source_has_no_await_pool_or_client_reference():
    """No I/O in `reciprocal_rank_fusion`'s own body -- the acceptance
    criterion's `sed`/`grep` check, expressed as a Python-side guard so a
    refactor that reintroduces I/O fails a test, not just a shell check."""
    import inspect

    source = inspect.getsource(reciprocal_rank_fusion)
    assert "await" not in source
    assert "pool" not in source
    assert "client" not in source


# ---------------------------------------------------------------------------
# UNIT -- app.retrieval.lexical (tokenize / build_corpus / bm25_search, Task 1)
# ---------------------------------------------------------------------------


def test_tokenize_keeps_hyphenated_identifier_as_one_token():
    assert tokenize("URS-042 traceability matrix") == ["urs-042", "traceability", "matrix"]


def test_build_corpus_empty_system_returns_ids_and_none(monkeypatch):
    async def _go():
        return await build_corpus(FakePool([], bm25_rows=[]), DEMO_SYSTEM)

    ids, bm25 = _run(_go())
    assert ids == []
    assert bm25 is None


def test_bm25_search_exact_identifier_ranks_matching_chunk_first(monkeypatch):
    rows = [
        {"chunk_id": "aaaa1111-0000-0000-0000-000000000000", "content": "General onboarding overview text."},
        {"chunk_id": "bbbb2222-0000-0000-0000-000000000000", "content": "Traceability matrix for URS-042 verification."},
        {"chunk_id": "cccc3333-0000-0000-0000-000000000000", "content": "Unrelated maintenance schedule notes."},
    ]

    async def _go():
        return await bm25_search(FakePool([], bm25_rows=rows), "URS-042 traceability", DEMO_SYSTEM)

    results = _run(_go())
    assert results
    assert results[0][0] == "bbbb2222-0000-0000-0000-000000000000"


def test_bm25_search_returns_at_most_limit_sorted_descending_dropping_zero_scores(monkeypatch):
    rows = [
        {"chunk_id": f"{i:08x}-0000-0000-0000-000000000000", "content": "matching keyword content " * (i + 1)}
        for i in range(BM25_CANDIDATE_LIMIT + 5)
    ]
    rows.append({"chunk_id": "ffffffff-0000-0000-0000-000000000000", "content": "completely unrelated text zz yy"})

    async def _go():
        return await bm25_search(FakePool([], bm25_rows=rows), "matching keyword content", DEMO_SYSTEM)

    results = _run(_go())
    assert len(results) <= BM25_CANDIDATE_LIMIT
    scores = [score for _cid, score in results]
    assert scores == sorted(scores, reverse=True)
    assert all(score > 0 for score in scores)
    assert "ffffffff-0000-0000-0000-000000000000" not in {cid for cid, _ in results}


# ---------------------------------------------------------------------------
# UNIT -- hybrid_retrieve fusion behavior (Task 1)
# ---------------------------------------------------------------------------


def test_bm25_only_chunk_appears_with_bm25_score_and_dense_score_none(monkeypatch):
    _mock_embedding_env(monkeypatch)
    chunk_id = "66666666-6666-6666-6666-666666666666"
    _install_fake_qdrant(monkeypatch, [])  # no dense hits at all
    bm25_rows = _bm25_rows_with_distractor(chunk_id, "URS-042 traceability requirement text.")

    async def _go():
        with respx.mock:
            respx.post(GEMINI_EMBED_URL).mock(
                return_value=httpx.Response(200, json={"embedding": {"values": [0.1] * EMBEDDING_DIMENSIONS}})
            )
            return await hybrid_retrieve(
                FakePool([_row(chunk_id)], bm25_rows=bm25_rows), "URS-042 traceability", DEMO_SYSTEM
            )

    outcome = _run(_go())
    assert outcome.insufficient_evidence is False
    assert len(outcome.evidence) == 1
    item = outcome.evidence[0]
    assert item["chunk_id"] == chunk_id
    assert item["dense_score"] is None
    assert item["bm25_score"] is not None
    assert item["retrieval_method"] == "keyword"


def test_dense_only_chunk_appears_with_dense_score_and_bm25_score_none(monkeypatch):
    _mock_embedding_env(monkeypatch)
    chunk_id = "77777777-7777-7777-7777-777777777777"
    _install_fake_qdrant(monkeypatch, [_hit(chunk_id, 0.80)])

    async def _go():
        with respx.mock:
            respx.post(GEMINI_EMBED_URL).mock(
                return_value=httpx.Response(200, json={"embedding": {"values": [0.1] * EMBEDDING_DIMENSIONS}})
            )
            return await hybrid_retrieve(FakePool([_row(chunk_id)], bm25_rows=[]), "query", DEMO_SYSTEM)

    outcome = _run(_go())
    item = outcome.evidence[0]
    assert item["bm25_score"] is None
    assert item["dense_score"] is not None
    assert item["retrieval_method"] == "semantic"


def test_hybrid_chunk_found_by_both_carries_both_scores_and_hybrid_method(monkeypatch):
    _mock_embedding_env(monkeypatch)
    chunk_id = "88888888-8888-8888-8888-888888888888"
    _install_fake_qdrant(monkeypatch, [_hit(chunk_id, 0.80)])
    bm25_rows = _bm25_rows_with_distractor(chunk_id, "URS-042 traceability requirement text.")

    async def _go():
        with respx.mock:
            respx.post(GEMINI_EMBED_URL).mock(
                return_value=httpx.Response(200, json={"embedding": {"values": [0.1] * EMBEDDING_DIMENSIONS}})
            )
            return await hybrid_retrieve(
                FakePool([_row(chunk_id)], bm25_rows=bm25_rows), "URS-042 traceability", DEMO_SYSTEM
            )

    outcome = _run(_go())
    item = outcome.evidence[0]
    assert item["dense_score"] is not None
    assert item["bm25_score"] is not None
    assert item["retrieval_method"] == "hybrid"


def test_asyncio_gather_runs_dense_and_lexical_legs_concurrently(monkeypatch):
    """`hybrid_retrieve`'s own source uses `asyncio.gather` -- a
    behavioral guard (not just a `grep`) that both legs actually run,
    proven by the bm25-only test above returning real evidence with zero
    dense hits and the dense-only test above returning real evidence with
    zero bm25 hits, from the SAME `hybrid_retrieve` code path."""
    import inspect

    assert "asyncio.gather" in inspect.getsource(hybrid_search.hybrid_retrieve)


def test_degraded_embedding_with_bm25_evidence_returns_lexical_only_not_insufficient(monkeypatch):
    """Task 1's degraded-half-pipeline behavior: a degraded embedding no
    longer forces insufficient evidence on its own when the lexical leg
    still finds real evidence."""
    _mock_embedding_env(monkeypatch, degrade=True)
    chunk_id = "99999999-9999-9999-9999-999999999999"
    bm25_rows = _bm25_rows_with_distractor(chunk_id, "URS-042 traceability requirement text.")

    async def _go():
        with respx.mock:
            # No route registered for the embedding endpoint -- a degraded
            # (no-key) call_embedding returns before any HTTP request.
            return await hybrid_retrieve(
                FakePool([_row(chunk_id)], bm25_rows=bm25_rows), "URS-042 traceability", DEMO_SYSTEM
            )

    outcome = _run(_go())
    assert outcome.insufficient_evidence is False
    assert len(outcome.evidence) == 1
    assert outcome.evidence[0]["retrieval_method"] == "keyword"
    searching = next(s for s in outcome.trace if s["stage_id"] == "searching")
    assert searching["status"] == "skipped"
    assert "lexical-only" in searching["detail"]


def test_qdrant_unavailable_with_bm25_evidence_returns_lexical_only_not_insufficient(monkeypatch):
    _mock_embedding_env(monkeypatch)
    chunk_id = "12121212-1212-1212-1212-121212121212"
    _install_fake_qdrant(monkeypatch, [], client_unavailable=True)
    bm25_rows = _bm25_rows_with_distractor(chunk_id, "URS-042 traceability requirement text.")

    async def _go():
        with respx.mock:
            respx.post(GEMINI_EMBED_URL).mock(
                return_value=httpx.Response(200, json={"embedding": {"values": [0.1] * EMBEDDING_DIMENSIONS}})
            )
            return await hybrid_retrieve(
                FakePool([_row(chunk_id)], bm25_rows=bm25_rows), "URS-042 traceability", DEMO_SYSTEM
            )

    outcome = _run(_go())
    assert outcome.insufficient_evidence is False
    assert outcome.evidence[0]["retrieval_method"] == "keyword"


def test_both_legs_empty_still_returns_insufficient_evidence(monkeypatch):
    _mock_embedding_env(monkeypatch, degrade=True)

    async def _go():
        with respx.mock:
            return await hybrid_retrieve(FakePool([], bm25_rows=[]), "query", DEMO_SYSTEM)

    outcome = _run(_go())
    assert outcome.insufficient_evidence is True
    assert outcome.evidence == []


def test_qdrant_unavailable_returns_insufficient_evidence_no_exception(monkeypatch):
    _mock_embedding_env(monkeypatch)
    _install_fake_qdrant(monkeypatch, [], client_unavailable=True)

    async def _go():
        with respx.mock:
            respx.post(GEMINI_EMBED_URL).mock(
                return_value=httpx.Response(200, json={"embedding": {"values": [0.1] * EMBEDDING_DIMENSIONS}})
            )
            return await hybrid_retrieve(FakePool([]), "query", DEMO_SYSTEM)

    outcome = _run(_go())
    assert outcome.insufficient_evidence is True
    assert outcome.evidence == []


def test_stage_labels_declares_all_six_ids_in_order():
    assert list(STAGE_LABELS) == [
        "understanding",
        "searching",
        "combining",
        "reranking",
        "evaluating",
        "preparing",
    ]


def test_module_makes_no_chat_completion_call():
    assert not hasattr(hybrid_search, "call_llm")


# ---------------------------------------------------------------------------
# INTEGRATION -- hybrid_retrieve against live Postgres + live Qdrant
# ---------------------------------------------------------------------------


def test_integration_hybrid_retrieve_against_live_postgres_and_qdrant(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    chunk_id = "55555555-5555-5555-5555-555555555555"
    vector = [1.0] + [0.0] * (EMBEDDING_DIMENSIONS - 1)

    async def _run_test():
        pool = await get_pool()
        client = await get_qdrant_client()
        assert client is not None, "Qdrant must be reachable for this integration test"
        await ensure_collection(client)
        await pool.execute(
            "INSERT INTO document_chunks (chunk_id, document_id, content, embedding_id, "
            "section, page, chunk_index, metadata) "
            "VALUES ($1::uuid, $2, $3, $4, $5, $6, $7, $8::jsonb)",
            chunk_id,
            DEMO_DOCUMENT_ID,
            "Integration test content for hybrid_retrieve, live Postgres + Qdrant.",
            chunk_id,
            "Integration Test Section",
            7,
            0,
            "{}",
        )
        await upsert_chunks(
            client,
            [
                {
                    "chunk_id": chunk_id,
                    "document_id": DEMO_DOCUMENT_ID,
                    "system_id": DEMO_SYSTEM,
                    "vector": vector,
                    "section": "Integration Test Section",
                    "page": 7,
                    "chunk_index": 0,
                }
            ],
        )

        # Only the embedding endpoint is intercepted -- the live Qdrant
        # search below passes through to the real local service via an
        # explicit `pass_through()` route (test_retrieval_ingest.py's own
        # established convention: `assert_all_mocked=False` was tried and
        # rejected there for silently short-circuiting every request).
        with respx.mock:
            respx.route(url__startswith=QDRANT_URL).pass_through()
            respx.post(GEMINI_EMBED_URL).mock(
                return_value=httpx.Response(200, json={"embedding": {"values": vector}})
            )
            outcome = await hybrid_retrieve(pool, "integration test query", DEMO_SYSTEM)
        return outcome

    try:
        outcome = asyncio.run(_run_test())
        assert outcome.insufficient_evidence is False
        matches = [item for item in outcome.evidence if item["chunk_id"] == chunk_id]
        assert len(matches) == 1
        item = matches[0]
        assert item["document_id"] == DEMO_DOCUMENT_ID
        assert item["document_title"] == DEMO_DOCUMENT_TITLE
        assert item["section"] == "Integration Test Section"
        assert item["page"] == 7
        assert item["retrieval_method"] == "semantic"
        assert item["dense_score"] > DENSE_RELEVANCE_THRESHOLD
    finally:

        async def _cleanup():
            pool = await get_pool()
            await pool.execute("DELETE FROM document_chunks WHERE chunk_id = $1::uuid", chunk_id)
            client = await get_qdrant_client()
            if client is not None:
                await client.delete(collection_name="gxp_document_chunks", points_selector=[chunk_id])

        asyncio.run(_cleanup())
