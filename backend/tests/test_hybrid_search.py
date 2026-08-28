"""
Tests for `app.retrieval.hybrid_search` (Phase 06.1, plan 06.1-02,
RAG-05/RAG-06, AGT-01).

Covers every Task 1 `<behavior>` bullet for `hybrid_retrieve`: the UNIT
section uses respx-stubbed embeddings plus a monkeypatched
`dense_search`/`get_qdrant_client` (this module's own two Qdrant seams),
and one INTEGRATION test runs against the real local Postgres + Qdrant
stack, guarded the same way `test_evidence_graph.py`/`test_retrieval_ingest.py`
guard their own live-state tests -- no skip marker; this whole suite
assumes the docker-compose stack is up.
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
    STAGE_LABELS,
    hybrid_retrieve,
)
from app.retrieval.qdrant_store import DenseHit, QDRANT_URL, ensure_collection, get_qdrant_client, upsert_chunks

DEMO_SYSTEM = "GXP-MFG-DEMO-01"
DEMO_DOCUMENT_ID = "DOC-2026-OM-99"  # seeded row, infra/postgres/seed/001_seed.sql
DEMO_DOCUMENT_TITLE = "NovaSynth Operations Manual"
GEMINI_EMBED_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent"
)


class FakePool:
    """Minimal asyncpg-Pool stand-in for the UNIT section: `.fetch()`
    returns whichever of `rows` match the requested chunk_ids, ignoring
    the SQL text itself -- the real hydration query is proven by the
    INTEGRATION test below."""

    def __init__(self, rows: List[Dict[str, Any]]):
        self._rows = rows

    async def fetch(self, _query: str, chunk_ids: List[str]):
        wanted = {str(c) for c in chunk_ids}
        return [row for row in self._rows if str(row["chunk_id"]) in wanted]


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


def test_trace_marks_combining_and_reranking_skipped_never_complete(monkeypatch):
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
    for stage_id in ("combining", "reranking"):
        stage = next(s for s in outcome.trace if s["stage_id"] == stage_id)
        assert stage["status"] == "skipped"
        assert stage["status"] != "complete"


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
