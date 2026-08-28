"""
Tests for `app.routes.documents` (Phase 06.1, plan 06.1-01, RAG-01).

Covers every `<behavior>` bullet in 06.1-01-PLAN.md Task 2. Exercises the
HTTP endpoint via `TestClient` against live, seeded Postgres and live
Qdrant -- never mocked, matching `test_routes_evidence_graph.py`'s own
convention -- except the embedding provider, which is respx-mocked
(`test_routes_actions.py`'s established pattern for the LLM/embedding
transport layer specifically).

Every negative case asserts row counts are unchanged (`documents`,
`document_chunks`) before and after the request, per the plan's own
"nothing written" requirement for every rejection path.
"""

import asyncio

import httpx
import respx

from app import db
from app.db import get_pool
from app.retrieval.embeddings import EMBEDDING_DIMENSIONS
from app.retrieval.qdrant_store import QDRANT_COLLECTION, QDRANT_URL, get_qdrant_client

DEMO_SYSTEM = "GXP-MFG-DEMO-01"
IDENTITY_HEADERS = {"X-User-Id": "test-uploader", "X-User-Role": "IT System Manager"}

EMBED_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-embedding-001:batchEmbedContents"
)


def _batch_embedding_body(count: int) -> dict:
    return {
        "embeddings": [
            {"values": [((i + j + 1) % 23) / 7.0 - 1.5 for i in range(EMBEDDING_DIMENSIONS)]}
            for j in range(count)
        ]
    }


def _mocked_embedding_route(count: int = 1):
    # Live Qdrant traffic (the route's own get_qdrant_client()/ensure_collection()/
    # index_document() calls) must pass through untouched -- only the
    # embedding endpoint is intercepted. See test_retrieval_ingest.py's own
    # comment for why `assert_all_mocked=False` is not used instead.
    respx.route(url__startswith=QDRANT_URL).pass_through()
    return respx.post(EMBED_URL).mock(
        return_value=httpx.Response(200, json=_batch_embedding_body(count))
    )


async def _counts():
    pool = await get_pool()
    doc_count = await pool.fetchval("SELECT COUNT(*) FROM documents")
    chunk_count = await pool.fetchval("SELECT COUNT(*) FROM document_chunks")
    return doc_count, chunk_count


async def _cleanup_document(document_id: str) -> None:
    pool = await get_pool()
    chunk_rows = await pool.fetch(
        "SELECT chunk_id FROM document_chunks WHERE document_id = $1", document_id
    )
    chunk_ids = [str(row["chunk_id"]) for row in chunk_rows]
    if chunk_ids:
        client = await get_qdrant_client()
        if client is not None:
            try:
                await client.delete(collection_name=QDRANT_COLLECTION, points_selector=chunk_ids)
            except Exception:  # noqa: BLE001 -- best-effort cleanup only
                pass
    await pool.execute("DELETE FROM document_chunks WHERE document_id = $1", document_id)
    await pool.execute("DELETE FROM documents WHERE id = $1", document_id)


def _upload(client, content: bytes, filename: str, headers=None, **form_overrides):
    data = {"system_id": DEMO_SYSTEM, "doc_type": "UPLOADED"}
    data.update(form_overrides)
    files = {"file": (filename, content, "text/markdown")}
    return client.post(
        "/api/documents/upload",
        files=files,
        data=data,
        headers=IDENTITY_HEADERS if headers is None else headers,
    )


MARKDOWN_CONTENT = (
    b"## Section A\n\nA short synthetic Markdown body used for the "
    b"upload route's own test suite, not real regulated content.\n"
)


def test_valid_markdown_upload_returns_ready_with_matching_counts(client, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    with respx.mock:
        _mocked_embedding_route(count=1)
        resp = _upload(client, MARKDOWN_CONTENT, "fixture.md")

    assert resp.status_code == 200
    body = resp.json()
    try:
        assert body["status"] == "READY"
        assert body["chunk_count"] > 0
        assert body["chunk_count"] == body["indexed_vector_count"]
        assert body["system_id"] == DEMO_SYSTEM
        assert body["failed_stage"] is None
    finally:
        asyncio.run(_cleanup_document(body["document_id"]))


def test_upload_creates_exactly_one_documents_row_with_server_generated_id(client, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    before_docs, _ = asyncio.run(_counts())

    with respx.mock:
        _mocked_embedding_route(count=1)
        resp = _upload(client, MARKDOWN_CONTENT, "some-client-name.md")

    body = resp.json()
    try:
        after_docs, _ = asyncio.run(_counts())
        assert after_docs == before_docs + 1
        assert body["document_id"] != "some-client-name.md"
        assert body["document_id"].startswith("DOC-")

        async def _fetch_row():
            pool = await get_pool()
            return await pool.fetchrow(
                "SELECT id, system_id FROM documents WHERE id = $1", body["document_id"]
            )

        row = asyncio.run(_fetch_row())
        assert row is not None
        assert row["system_id"] == DEMO_SYSTEM
    finally:
        asyncio.run(_cleanup_document(body["document_id"]))


def test_missing_identity_headers_returns_422_and_writes_nothing(client):
    before = asyncio.run(_counts())
    resp = _upload(client, MARKDOWN_CONTENT, "fixture.md", headers={})
    assert resp.status_code == 422
    assert asyncio.run(_counts()) == before


def test_unrecognized_role_returns_403_and_writes_nothing(client):
    before = asyncio.run(_counts())
    resp = _upload(
        client,
        MARKDOWN_CONTENT,
        "fixture.md",
        headers={"X-User-Id": "someone", "X-User-Role": "Not A Real Role"},
    )
    assert resp.status_code == 403
    assert asyncio.run(_counts()) == before


def test_unknown_system_id_returns_404_and_writes_nothing(client):
    before = asyncio.run(_counts())
    resp = _upload(client, MARKDOWN_CONTENT, "fixture.md", system_id="NOPE-DOES-NOT-EXIST")
    assert resp.status_code == 404
    assert "Unknown system_id" in resp.json()["detail"]
    assert asyncio.run(_counts()) == before


def test_unsupported_extension_returns_415_and_writes_nothing(client):
    before = asyncio.run(_counts())
    resp = _upload(client, b"MZ\x90\x00fake exe bytes", "malware.exe")
    assert resp.status_code == 415
    assert asyncio.run(_counts()) == before


def test_binary_content_with_text_extension_returns_415_and_writes_nothing(client):
    before = asyncio.run(_counts())
    # Invalid UTF-8 byte sequence (a lone continuation byte) inside a
    # payload claiming a supported .md extension -- content sniff must
    # reject this even though the extension allowlist passes it.
    resp = _upload(client, b"\xff\xfe\x00\x01not really markdown", "sneaky.md")
    assert resp.status_code == 415
    assert asyncio.run(_counts()) == before


def test_oversized_upload_returns_413_before_any_parse(client, monkeypatch):
    from app.routes import documents as documents_route

    monkeypatch.setattr(documents_route, "MAX_UPLOAD_BYTES", 10)
    before = asyncio.run(_counts())

    resp = _upload(client, b"this payload is longer than ten bytes", "fixture.md")

    assert resp.status_code == 413
    assert asyncio.run(_counts()) == before


def test_postgres_unreachable_returns_503_no_partial_state(client, monkeypatch, reset_db_pool):
    monkeypatch.setattr(
        db, "DATABASE_URL", "postgresql://sentinel:sentinel@127.0.0.1:1/sentinel"
    )
    resp = _upload(client, MARKDOWN_CONTENT, "fixture.md")
    assert resp.status_code == 503
    assert "Postgres pool unavailable" in resp.json()["detail"]


def test_degraded_embedding_provider_returns_honest_failed_envelope(client, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    resp = _upload(client, MARKDOWN_CONTENT, "fixture.md")

    assert resp.status_code == 200
    body = resp.json()
    try:
        assert body["status"] == "FAILED"
        assert body["failed_stage"] == "indexing"
        assert body["chunk_count"] == 0
        assert body["indexed_vector_count"] == 0

        async def _chunk_rows():
            pool = await get_pool()
            return await pool.fetch(
                "SELECT chunk_id FROM document_chunks WHERE document_id = $1",
                body["document_id"],
            )

        rows = asyncio.run(_chunk_rows())
        assert rows == []  # no document_chunks rows despite the documents row existing
    finally:
        asyncio.run(_cleanup_document(body["document_id"]))
