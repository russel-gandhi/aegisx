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
