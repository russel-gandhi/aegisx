"""
Tests for `POST /api/documents/{document_id}/approve` (`app.routes.documents`).

Closes the gap where an uploaded document (always inserted with
`status='READY'`) had no path to ever reach `status='APPROVED'`, the
value `app.agents.a2_compliance.verify_urs_approved` requires. Inserts
rows directly via SQL rather than going through the full upload/embedding
pipeline (`test_routes_documents.py`'s own respx-mocked convention) --
this route's own logic only ever reads/writes `documents.status`, so a
directly-inserted fixture row exercises the same code path.
"""

import asyncio

from app import db

QA_HEADERS = {"X-User-Id": "u-qa-test", "X-User-Role": "QA/Compliance"}
ITSM_HEADERS = {"X-User-Id": "u-itsm-test", "X-User-Role": "IT System Manager"}

DEMO_SYSTEM = "GXP-MFG-DEMO-01"


def _insert_document(document_id: str, status: str) -> None:
    async def _run():
        pool = await db.get_pool()
        await pool.execute(
            "INSERT INTO documents (id, system_id, doc_type, title, status, "
            "created_date, content_sha256) "
            "VALUES ($1, $2, 'URS', $3, $4, now(), $5) "
            "ON CONFLICT (id) DO UPDATE SET status = $4",
            document_id,
            DEMO_SYSTEM,
            f"Fixture {document_id}",
            status,
            f"sha-fixture-{document_id}",
        )

    asyncio.run(_run())


def _delete_document(document_id: str) -> None:
    async def _run():
        pool = await db.get_pool()
        await pool.execute("DELETE FROM documents WHERE id = $1", document_id)

    asyncio.run(_run())


def test_approve_ready_document_as_qa_returns_200_and_persists(client):
    doc_id = "TEST-APPROVE-DOC-01"
    _insert_document(doc_id, "READY")
    try:
        resp = client.post(f"/api/documents/{doc_id}/approve", headers=QA_HEADERS)
        assert resp.status_code == 200
        assert resp.json() == {"document_id": doc_id, "status": "APPROVED"}

        list_resp = client.get(
            f"/api/documents?system_id={DEMO_SYSTEM}", headers=QA_HEADERS
        )
        row = next(d for d in list_resp.json()["documents"] if d["document_id"] == doc_id)
        assert row["approval_status"] == "APPROVED"
    finally:
        _delete_document(doc_id)


def test_approve_already_approved_document_is_idempotent(client):
    doc_id = "TEST-APPROVE-DOC-02"
    _insert_document(doc_id, "APPROVED")
    try:
        resp = client.post(f"/api/documents/{doc_id}/approve", headers=QA_HEADERS)
        assert resp.status_code == 200
        assert resp.json()["status"] == "APPROVED"
    finally:
        _delete_document(doc_id)


def test_approve_quarantined_document_returns_409(client):
    doc_id = "TEST-APPROVE-DOC-03"
    _insert_document(doc_id, "QUARANTINED")
    try:
        resp = client.post(f"/api/documents/{doc_id}/approve", headers=QA_HEADERS)
        assert resp.status_code == 409
    finally:
        _delete_document(doc_id)


def test_approve_non_qa_role_returns_403(client):
    doc_id = "TEST-APPROVE-DOC-04"
    _insert_document(doc_id, "READY")
    try:
        resp = client.post(f"/api/documents/{doc_id}/approve", headers=ITSM_HEADERS)
        assert resp.status_code == 403

        list_resp = client.get(
            f"/api/documents?system_id={DEMO_SYSTEM}", headers=QA_HEADERS
        )
        row = next(d for d in list_resp.json()["documents"] if d["document_id"] == doc_id)
        assert row["approval_status"] == "READY"
    finally:
        _delete_document(doc_id)


def test_approve_unknown_document_returns_404(client):
    resp = client.post("/api/documents/NOT-A-REAL-DOC/approve", headers=QA_HEADERS)
    assert resp.status_code == 404


def test_approve_missing_identity_headers_returns_422(client):
    resp = client.post("/api/documents/whatever/approve")
    assert resp.status_code == 422


def test_approve_postgres_unreachable_returns_503(client, monkeypatch, reset_db_pool):
    monkeypatch.setattr(
        db, "DATABASE_URL", "postgresql://sentinel:sentinel@127.0.0.1:1/sentinel"
    )
    resp = client.post("/api/documents/whatever/approve", headers=QA_HEADERS)
    assert resp.status_code == 503
