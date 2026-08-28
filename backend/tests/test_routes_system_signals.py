"""
Tests for `app.routes.system_signals` (Phase 6, plan 06-02, Task 1).

Ticket: SENT-5-01 | Requirement: UI-03 | Decisions: D-06, D-07

Exercises the HTTP endpoint via `TestClient` against live, seeded Postgres
-- never mocked, mirroring `test_routes_evidence_graph.py`'s own
UNIT/NEGATIVE/EDGE structure. The seeded overdue records this suite
depends on (`SUP-2026-01` "DataSync Solutions", `AR-2026-05`) are asserted
present, not assumed -- if seed data has drifted, these tests fail loudly
rather than silently passing on a zero-signal response.
"""

import asyncio

from app import db
from app.db import get_pool


def test_gxp_demo_returns_overdue_supplier_and_access_review(client):
    resp = client.get("/api/systems/GXP-MFG-DEMO-01/access-supplier-signals")
    assert resp.status_code == 200
    body = resp.json()
    assert body["system_id"] == "GXP-MFG-DEMO-01"
    assert body["overdue_suppliers"] >= 1
    assert "DataSync Solutions" in body["overdue_supplier_names"]
    assert body["overdue_access_reviews"] >= 1


def test_bus_it_demo_has_no_seeded_overdue_signals(client):
    # BUS-IT-DEMO-02 is the "healthy" non-GxP seeded system (04-RESEARCH.md
    # / seed SQL) -- no suppliers/access_reviews rows are seeded for it, so
    # this asserts the endpoint returns real zeros, not an error, for a
    # system with genuinely no signal.
    resp = client.get("/api/systems/BUS-IT-DEMO-02/access-supplier-signals")
    assert resp.status_code == 200
    body = resp.json()
    assert body["system_id"] == "BUS-IT-DEMO-02"
    assert body["overdue_suppliers"] == 0
    assert body["overdue_supplier_names"] == []
    assert body["overdue_access_reviews"] == 0


def test_unknown_system_returns_404(client):
    resp = client.get("/api/systems/NO-SUCH-SYSTEM/access-supplier-signals")
    assert resp.status_code == 404


def test_postgres_unreachable_returns_503(client, monkeypatch, reset_db_pool):
    monkeypatch.setattr(
        db, "DATABASE_URL", "postgresql://sentinel:sentinel@127.0.0.1:1/sentinel"
    )
    resp = client.get("/api/systems/GXP-MFG-DEMO-01/access-supplier-signals")
    assert resp.status_code == 503


def test_query_binds_system_id_as_parameter_not_f_string(client):
    # ASVS V5 / T-06-07: a system_id containing a SQL-metacharacter-bearing
    # string must never be interpolated -- it should simply not match any
    # real system (404), never raise a 500 from a malformed query or alter
    # unrelated rows.
    resp = client.get(
        "/api/systems/GXP-MFG-DEMO-01' OR '1'='1/access-supplier-signals"
    )
    assert resp.status_code == 404


def test_response_matches_direct_query_against_live_postgres(client):
    resp = client.get("/api/systems/GXP-MFG-DEMO-01/access-supplier-signals")
    assert resp.status_code == 200
    body = resp.json()

    async def _direct():
        pool = await get_pool()
        import time

        now_ns = time.time_ns()
        reviews = await pool.fetch(
            "SELECT id FROM access_reviews WHERE system_id = $1 "
            "AND status != 'COMPLETED' AND scheduled_date_ns < $2",
            "GXP-MFG-DEMO-01",
            now_ns,
        )
        suppliers = await pool.fetch(
            "SELECT id, name FROM suppliers WHERE system_id = $1 "
            "AND reassessment_due_date_ns < $2",
            "GXP-MFG-DEMO-01",
            now_ns,
        )
        return reviews, suppliers

    reviews, suppliers = asyncio.run(_direct())
    assert body["overdue_access_reviews"] == len(reviews)
    assert body["overdue_suppliers"] == len(suppliers)
    assert set(body["overdue_supplier_names"]) == {row["name"] for row in suppliers}
