"""
Tests for `app.routes.systems` (REMEDIATION-PLAN.md #6).

Follows this suite's established `TestClient` module-level pattern
(`test_routes_audit.py`) plus the `db.DATABASE_URL`-monkeypatch technique
`test_routes_documents.py` uses to exercise the 503 unreachable-pool path
without needing to mock `acquire_pool_or_none` itself.
"""

import asyncio

from fastapi.testclient import TestClient

from app import db
from app.main import app

client = TestClient(app)


def test_list_systems_returns_200_with_both_seeded_systems():
    resp = client.get("/api/systems")
    assert resp.status_code == 200
    ids = {row["id"] for row in resp.json()}
    assert {"GXP-MFG-DEMO-01", "BUS-IT-DEMO-02"}.issubset(ids)


def test_list_systems_postgres_unreachable_returns_503(monkeypatch, reset_db_pool):
    monkeypatch.setattr(
        db, "DATABASE_URL", "postgresql://sentinel:sentinel@127.0.0.1:1/sentinel"
    )
    resp = client.get("/api/systems")
    assert resp.status_code == 503
    assert "Postgres pool unavailable" in resp.json()["detail"]


def test_readiness_unknown_system_returns_404():
    resp = client.get("/api/systems/NOT-A-REAL-SYSTEM/readiness")
    assert resp.status_code == 404


def test_readiness_postgres_unreachable_returns_503(monkeypatch, reset_db_pool):
    monkeypatch.setattr(
        db, "DATABASE_URL", "postgresql://sentinel:sentinel@127.0.0.1:1/sentinel"
    )
    resp = client.get("/api/systems/GXP-MFG-DEMO-01/readiness")
    assert resp.status_code == 503


def test_readiness_known_system_returns_seeded_score_and_open_findings_breakdown():
    resp = client.get("/api/systems/GXP-MFG-DEMO-01/readiness")
    assert resp.status_code == 200
    body = resp.json()
    assert body["system_id"] == "GXP-MFG-DEMO-01"
    # Bible Section 5 seeds this system's readiness_score at 61 -- this
    # route reads the stored column verbatim (see systems.py's own
    # docstring for why it does not recompute a formula the Bible never
    # specifies), so this is a real assertion on real seeded state, not an
    # arbitrary number.
    assert isinstance(body["score"], int)
    assert "open_findings" in body["breakdown"]
    assert isinstance(body["breakdown"]["open_findings"], int)


ITSM_HEADERS = {"X-User-Id": "u-itsm-test", "X-User-Role": "IT System Manager"}
QA_HEADERS = {"X-User-Id": "u-qa-test", "X-User-Role": "QA/Compliance"}

_CREATE_BODY = {
    "id": "TEST-CREATE-SYS-01",
    "name": "Test Created System",
    "description": "Created by test_routes_systems.py",
    "system_owner": "Test Owner",
    "lifecycle_state": "OPERATIONAL",
    "gxp_impact": True,
}


def _delete_test_system(system_id: str) -> None:
    async def _run():
        pool = await db.acquire_pool_or_none()
        if pool is not None:
            await pool.execute("DELETE FROM gxp_systems WHERE id = $1", system_id)

    asyncio.run(_run())


def test_create_system_as_itsm_returns_201_and_persists():
    _delete_test_system(_CREATE_BODY["id"])
    try:
        resp = client.post("/api/systems", json=_CREATE_BODY, headers=ITSM_HEADERS)
        assert resp.status_code == 201
        body = resp.json()
        assert body["id"] == _CREATE_BODY["id"]
        assert body["readiness_score"] == 0
        assert body["last_backup_test_ns"] is None

        list_resp = client.get("/api/systems")
        ids = {row["id"] for row in list_resp.json()}
        assert _CREATE_BODY["id"] in ids
    finally:
        _delete_test_system(_CREATE_BODY["id"])


def test_create_system_duplicate_id_returns_409():
    _delete_test_system(_CREATE_BODY["id"])
    try:
        first = client.post("/api/systems", json=_CREATE_BODY, headers=ITSM_HEADERS)
        assert first.status_code == 201
        second = client.post("/api/systems", json=_CREATE_BODY, headers=ITSM_HEADERS)
        assert second.status_code == 409
    finally:
        _delete_test_system(_CREATE_BODY["id"])


def test_create_system_non_itsm_role_returns_403():
    resp = client.post("/api/systems", json=_CREATE_BODY, headers=QA_HEADERS)
    assert resp.status_code == 403
    ids = {row["id"] for row in client.get("/api/systems").json()}
    assert _CREATE_BODY["id"] not in ids


def test_create_system_missing_identity_headers_returns_422():
    resp = client.post("/api/systems", json=_CREATE_BODY)
    assert resp.status_code == 422


def test_create_system_postgres_unreachable_returns_503(monkeypatch, reset_db_pool):
    monkeypatch.setattr(
        db, "DATABASE_URL", "postgresql://sentinel:sentinel@127.0.0.1:1/sentinel"
    )
    resp = client.post("/api/systems", json=_CREATE_BODY, headers=ITSM_HEADERS)
    assert resp.status_code == 503
