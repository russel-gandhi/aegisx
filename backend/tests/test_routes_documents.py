"""
Tests for `app.routes.documents` (Phase 06.1, plans 06.1-01/06.1-04,
RAG-01).

Covers every `<behavior>` bullet in 06.1-01-PLAN.md Task 2, every
`<behavior>` bullet in 06.1-04-PLAN.md Task 2 (format dispatch by magic
bytes, upload hardening), and every `<behavior>` bullet in
06.1-04-PLAN.md Task 3 (`GET /api/documents`, post-upload evidence-graph
rebuild). Exercises the HTTP endpoint via `TestClient` against live,
seeded Postgres and live Qdrant -- never mocked, matching
`test_routes_evidence_graph.py`'s own convention -- except the embedding
provider, which is respx-mocked (`test_routes_actions.py`'s established
pattern for the LLM/embedding transport layer specifically).

Every negative case asserts row counts are unchanged (`documents`,
`document_chunks`) before and after the request, per the plan's own
"nothing written" requirement for every rejection path.
"""

import asyncio
import os

import httpx
import respx

from app import db
from app.db import get_pool
from app.graph.evidence_graph import make_node_id
from app.retrieval.embeddings import EMBEDDING_DIMENSIONS
from app.retrieval.qdrant_store import QDRANT_COLLECTION, QDRANT_URL, get_qdrant_client

DEMO_SYSTEM = "GXP-MFG-DEMO-01"
IDENTITY_HEADERS = {"X-User-Id": "test-uploader", "X-User-Role": "IT System Manager"}

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "documents")
SOP_PDF_PATH = os.path.join(FIXTURES_DIR, "sop_extract.pdf")
VALIDATION_DOCX_PATH = os.path.join(FIXTURES_DIR, "validation_protocol.docx")
TRACEABILITY_CSV_PATH = os.path.join(FIXTURES_DIR, "traceability_matrix.csv")

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


# ---------------------------------------------------------------------------
# 06.1-04-PLAN.md Task 2 -- format dispatch by magic bytes, upload hardening
# ---------------------------------------------------------------------------


def _upload_file(client, path: str, filename: str, headers=None, **form_overrides):
    with open(path, "rb") as f:
        content = f.read()
    return _upload(client, content, filename, headers=headers, **form_overrides)


def test_pdf_bytes_behind_text_extension_returns_415_and_writes_nothing(client):
    # Plain text bytes, but the extension claims .pdf -- magic-byte sniff
    # must reject this even though "pdf" is a supported extension.
    before = asyncio.run(_counts())
    resp = _upload(client, b"this is not really a PDF file at all", "fake.pdf")
    assert resp.status_code == 415
    assert asyncio.run(_counts()) == before


def test_pdf_bytes_behind_docx_extension_returns_415_and_writes_nothing(client):
    # A genuine PDF's bytes, but the extension claims .docx -- magic-byte
    # sniff must reject this (T-06.1-21 file-type confusion).
    before = asyncio.run(_counts())
    with open(SOP_PDF_PATH, "rb") as f:
        pdf_bytes = f.read()
    resp = _upload(client, pdf_bytes, "fake.docx")
    assert resp.status_code == 415
    assert asyncio.run(_counts()) == before


def test_valid_pdf_upload_returns_ready_with_page_and_section(client, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    with respx.mock:
        _mocked_embedding_route(count=3)
        resp = _upload_file(client, SOP_PDF_PATH, "sop_extract.pdf")

    assert resp.status_code == 200
    body = resp.json()
    try:
        assert body["status"] == "READY"
        assert body["chunk_count"] > 0
        assert body["chunk_count"] == body["indexed_vector_count"]
        assert body["failed_stage"] is None

        async def _chunk_rows():
            pool = await get_pool()
            return await pool.fetch(
                "SELECT section, page FROM document_chunks WHERE document_id = $1",
                body["document_id"],
            )

        rows = asyncio.run(_chunk_rows())
        assert all(row["page"] is not None for row in rows)
        assert any(row["section"] is not None for row in rows)
    finally:
        asyncio.run(_cleanup_document(body["document_id"]))


def test_valid_docx_upload_returns_ready_with_section_no_page(client, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    with respx.mock:
        _mocked_embedding_route(count=3)
        resp = _upload_file(client, VALIDATION_DOCX_PATH, "validation_protocol.docx")

    assert resp.status_code == 200
    body = resp.json()
    try:
        assert body["status"] == "READY"
        assert body["chunk_count"] > 0
        assert body["chunk_count"] == body["indexed_vector_count"]

        async def _chunk_rows():
            pool = await get_pool()
            return await pool.fetch(
                "SELECT section, page FROM document_chunks WHERE document_id = $1",
                body["document_id"],
            )

        rows = asyncio.run(_chunk_rows())
        assert all(row["page"] is None for row in rows)
        assert any(row["section"] is not None for row in rows)
    finally:
        asyncio.run(_cleanup_document(body["document_id"]))


def test_valid_csv_upload_returns_ready_with_row_block_structure(client, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    with respx.mock:
        _mocked_embedding_route(count=5)
        resp = _upload_file(client, TRACEABILITY_CSV_PATH, "traceability_matrix.csv")

    assert resp.status_code == 200
    body = resp.json()
    try:
        assert body["status"] == "READY"
        assert body["chunk_count"] > 0
        assert body["chunk_count"] == body["indexed_vector_count"]

        async def _chunk_rows():
            pool = await get_pool()
            return await pool.fetch(
                "SELECT section, page, content FROM document_chunks WHERE document_id = $1 "
                "ORDER BY chunk_index",
                body["document_id"],
            )

        rows = asyncio.run(_chunk_rows())
        assert all(row["section"] == "traceability_matrix" for row in rows)
        assert all(row["page"] is not None for row in rows)
        assert "urs_id" in rows[0]["content"]
    finally:
        asyncio.run(_cleanup_document(body["document_id"]))


def test_upload_with_no_doc_type_form_field_defaults_to_uppercased_format(client, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    data = {"system_id": DEMO_SYSTEM}  # doc_type deliberately omitted
    files = {"file": ("fixture.md", MARKDOWN_CONTENT, "text/markdown")}
    with respx.mock:
        _mocked_embedding_route(count=1)
        resp = client.post(
            "/api/documents/upload", files=files, data=data, headers=IDENTITY_HEADERS
        )

    assert resp.status_code == 200
    body = resp.json()
    try:
        assert body["doc_type"] == "TEXT"
    finally:
        asyncio.run(_cleanup_document(body["document_id"]))


def test_corrupt_pdf_with_valid_magic_bytes_returns_failed_parsing_envelope(client, monkeypatch):
    # Magic bytes agree (starts with %PDF-), so detect_format passes it
    # through -- but the body is not a real, parseable PDF, so pypdf
    # yields zero blocks. This must surface as an honest FAILED envelope,
    # not an unhandled exception, and must write zero document_chunks
    # rows despite the `documents` row existing.
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    corrupt_pdf = b"%PDF-1.4\nthis is not a real, well-formed PDF body at all"
    resp = _upload(client, corrupt_pdf, "corrupt.pdf")

    assert resp.status_code == 200
    body = resp.json()
    try:
        assert body["status"] == "FAILED"
        assert body["failed_stage"] == "parsing"
        assert body["chunk_count"] == 0
        assert body["indexed_vector_count"] == 0

        async def _chunk_rows():
            pool = await get_pool()
            return await pool.fetch(
                "SELECT chunk_id FROM document_chunks WHERE document_id = $1",
                body["document_id"],
            )

        rows = asyncio.run(_chunk_rows())
        assert rows == []
    finally:
        asyncio.run(_cleanup_document(body["document_id"]))


# ---------------------------------------------------------------------------
# 06.1-04-PLAN.md Task 3 -- GET /api/documents, post-upload graph rebuild
# ---------------------------------------------------------------------------


def _list(client, system_id=None, headers=None):
    params = {} if system_id is None else {"system_id": system_id}
    return client.get(
        "/api/documents", params=params, headers=IDENTITY_HEADERS if headers is None else headers
    )


def _upload_ready(client, monkeypatch, filename="fixture.md", content=None):
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    with respx.mock:
        _mocked_embedding_route(count=1)
        resp = _upload(client, content or MARKDOWN_CONTENT, filename)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "READY"
    return body


def test_parsing_failure_persists_failed_status_on_raw_documents_row(client, monkeypatch):
    # The `documents` row is inserted as "READY" before parsing runs. A
    # parsing failure must overwrite that raw column to "FAILED" instead
    # of leaving misleading persistent state -- `list_documents` already
    # recomputes an honest status from `chunk_count` at read time, but any
    # other/future direct reader of the raw column must see the truth too.
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    corrupt_pdf = b"%PDF-1.4\nthis is not a real, well-formed PDF body at all"
    resp = _upload(client, corrupt_pdf, "corrupt2.pdf")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "FAILED"
    try:

        async def _raw_status():
            pool = await get_pool()
            return await pool.fetchval(
                "SELECT status FROM documents WHERE id = $1", body["document_id"]
            )

        assert asyncio.run(_raw_status()) == "FAILED"
    finally:
        asyncio.run(_cleanup_document(body["document_id"]))


def test_indexing_failure_persists_failed_status_on_raw_documents_row(client, monkeypatch):
    # Same invariant as above, but for a failure at the indexing stage
    # (embeddings degraded) rather than the parsing stage.
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    resp = _upload(client, MARKDOWN_CONTENT, "degraded2.md")
    body = resp.json()
    assert body["status"] == "FAILED"
    try:

        async def _raw_status():
            pool = await get_pool()
            return await pool.fetchval(
                "SELECT status FROM documents WHERE id = $1", body["document_id"]
            )

        assert asyncio.run(_raw_status()) == "FAILED"
    finally:
        asyncio.run(_cleanup_document(body["document_id"]))


def test_list_documents_returns_newest_first_with_real_chunk_count(client, monkeypatch):
    body = _upload_ready(client, monkeypatch)
    try:
        resp = _list(client, system_id=DEMO_SYSTEM)
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["system_id"] == DEMO_SYSTEM
        match = next(d for d in payload["documents"] if d["document_id"] == body["document_id"])
        assert match["chunk_count"] == body["chunk_count"]
        assert match["ingestion_status"] == "READY"
        # newest-first: the just-uploaded document must be at index 0
        assert payload["documents"][0]["document_id"] == body["document_id"]
    finally:
        asyncio.run(_cleanup_document(body["document_id"]))


def test_list_documents_failed_ingest_reports_failed_status_with_zero_chunks(client, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    resp = _upload(client, MARKDOWN_CONTENT, "degraded.md")
    body = resp.json()
    assert body["status"] == "FAILED"
    try:
        payload = _list(client, system_id=DEMO_SYSTEM).json()
        match = next(d for d in payload["documents"] if d["document_id"] == body["document_id"])
        assert match["chunk_count"] == 0
        assert match["ingestion_status"] == "FAILED"
    finally:
        asyncio.run(_cleanup_document(body["document_id"]))


def test_list_documents_no_system_id_filter_returns_across_systems(client, monkeypatch):
    body = _upload_ready(client, monkeypatch)
    try:
        payload = _list(client).json()
        assert payload["system_id"] is None
        ids = {d["document_id"] for d in payload["documents"]}
        assert body["document_id"] in ids
    finally:
        asyncio.run(_cleanup_document(body["document_id"]))


def test_list_documents_system_with_no_documents_returns_empty_list_200(client):
    # BUS-IT-DEMO-02 (infra/postgres/seed/001_seed.sql) is a seeded system
    # with zero seeded `documents` rows -- a real "system exists, has
    # nothing uploaded yet" state, not a synthetic id.
    resp = _list(client, system_id="BUS-IT-DEMO-02")
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["documents"] == []


def test_list_documents_unknown_system_id_returns_404(client):
    resp = _list(client, system_id="NOPE-DOES-NOT-EXIST")
    assert resp.status_code == 404
    assert "Unknown system_id" in resp.json()["detail"]


def test_list_documents_missing_identity_returns_422(client):
    resp = _list(client, system_id=DEMO_SYSTEM, headers={})
    assert resp.status_code == 422


def test_upload_creates_document_graph_node_without_explicit_rebuild(client, monkeypatch):
    body = _upload_ready(client, monkeypatch, filename="graph_visibility.md")
    try:
        expected_node_id = make_node_id("DOCUMENT", body["document_id"])

        async def _fetch_node():
            pool = await get_pool()
            return await pool.fetchrow(
                "SELECT node_id FROM graph_nodes WHERE node_id = $1", expected_node_id
            )

        row = asyncio.run(_fetch_node())
        assert row is not None, (
            f"expected a DOCUMENT graph node {expected_node_id!r} after upload "
            "with no explicit rebuild call"
        )
    finally:
        asyncio.run(_cleanup_document(body["document_id"]))


def test_rebuild_failure_after_successful_ingest_still_returns_ready(client, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")

    async def _raising_persist_graph(pool, system_id, graph):
        raise RuntimeError("simulated graph rebuild failure")

    import app.routes.documents as documents_route

    monkeypatch.setattr(documents_route, "persist_graph", _raising_persist_graph)

    with respx.mock:
        _mocked_embedding_route(count=1)
        resp = _upload(client, MARKDOWN_CONTENT, "rebuild_failure.md")

    assert resp.status_code == 200
    body = resp.json()
    try:
        assert body["status"] == "READY"  # rebuild failure never fails the upload response
        assert body["chunk_count"] > 0
    finally:
        asyncio.run(_cleanup_document(body["document_id"]))
