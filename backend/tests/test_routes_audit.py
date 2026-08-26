"""
Tests for the audit-chain HTTP routes (Phase 5, plan 05-03).

Ticket: SENT-4-06, SENT-4-07 | Requirement: AUDIT-02, AUDIT-03

Follows this suite's established `TestClient` module-level pattern
(`test_routes_actions.py`) plus `asyncio.run()` inside plain `def test_*`
bodies (`conftest.py`) for direct-DB setup/teardown. Every test in this
module uses `audit_chain_isolation` so a later test in the same session
sees a clean append point (05-RESEARCH.md Pitfall 3).
"""

import asyncio

import pytest
from fastapi.testclient import TestClient

from app.audit_trail import log_event, verify_chain
from app.db import get_pool
from app.main import app

client = TestClient(app)

IT_MANAGER_HEADERS = {"X-User-Id": "test-it-manager", "X-User-Role": "IT System Manager"}
AUDITOR_HEADERS = {"X-User-Id": "test-auditor", "X-User-Role": "Auditor"}
QA_COMPLIANCE_HEADERS = {"X-User-Id": "test-qa-compliance", "X-User-Role": "QA/Compliance"}


def _event(action_type: str) -> dict:
    return {
        "session_id": "SESSION-TEST-ROUTES-AUDIT",
        "user_id": "tester",
        "user_role": "IT System Manager",
        "agent_id": "A7",
        "action_type": action_type,
        "target_system_id": "GXP-MFG-DEMO-01",
        "output_summary": action_type,
        "evidence_ids": [],
        "opa_rule_ids": [],
    }


def test_get_audit_verify_returns_200_with_status():
    response = client.get("/api/audit/verify")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] in ("VERIFIED", "TAMPERED")


def test_demonstrate_tamper_without_identity_headers_returns_422():
    response = client.post(
        "/api/audit/demonstrate-tamper", json={"event_id": "EVT-does-not-exist"}
    )
    assert response.status_code == 422


@pytest.mark.parametrize(
    "denied_headers,sentinel_event_id",
    [
        (AUDITOR_HEADERS, "EVT-cr01-denied-auditor-260827-045"),
        (QA_COMPLIANCE_HEADERS, "EVT-cr01-denied-qa-compliance-260827-045"),
    ],
)
def test_demonstrate_tamper_denies_non_it_manager_roles_before_any_write(
    audit_chain_isolation, denied_headers, sentinel_event_id
):
    """CR-01: only IT System Manager (the sole `PERMISSION_MATRIX` holder
    of "A7") may invoke the tamper demo. Auditor and QA/Compliance are
    both denied with 403, and -- because the guard runs before
    `acquire_pool_or_none` and before `log_event` -- neither denial writes
    a `TAMPER_DEMO_INVOKED` row for this sentinel `event_id`."""

    async def run():
        response = client.post(
            "/api/audit/demonstrate-tamper",
            json={"event_id": sentinel_event_id},
            headers=denied_headers,
        )
        assert response.status_code == 403

        pool = await get_pool()
        invoked_row = await pool.fetchrow(
            "SELECT event_id FROM audit_events WHERE action_type = 'TAMPER_DEMO_INVOKED' "
            "AND target_record_id = $1",
            sentinel_event_id,
        )
        if invoked_row is not None:
            audit_chain_isolation.append(invoked_row["event_id"])
        assert invoked_row is None

    asyncio.run(run())


def test_demonstrate_tamper_unknown_event_id_returns_no_such_event(audit_chain_isolation):
    """A TAMPER_DEMO_INVOKED audit row is written before demonstrate_tamper
    runs (route docstring) regardless of whether the target id exists --
    capture and clean up that row via the isolation fixture."""

    async def run():
        response = client.post(
            "/api/audit/demonstrate-tamper",
            json={"event_id": "EVT-this-id-was-never-inserted-05-03-route"},
            headers=IT_MANAGER_HEADERS,
        )
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "NO_SUCH_EVENT"
        assert body["rows_modified"] == 0

        pool = await get_pool()
        invoked_row = await pool.fetchrow(
            "SELECT event_id FROM audit_events WHERE action_type = 'TAMPER_DEMO_INVOKED' "
            "AND target_record_id = $1",
            "EVT-this-id-was-never-inserted-05-03-route",
        )
        if invoked_row is not None:
            audit_chain_isolation.append(invoked_row["event_id"])

    asyncio.run(run())


def test_demonstrate_tamper_endpoint_reports_tampered(audit_chain_isolation):
    """The full demonstrate-tamper round trip through TestClient: the
    response's status is TAMPERED and its broken_at_index matches a
    direct verify_chain call made immediately after."""

    async def run():
        pool = await get_pool()
        ids = []
        for i in range(2):
            event_id = await log_event(pool, _event(f"TEST_HTTP_TAMPER_{i}"))
            ids.append(event_id)
        audit_chain_isolation.extend(ids)

        target_id = ids[-1]
        response = client.post(
            "/api/audit/demonstrate-tamper",
            json={"event_id": target_id},
            headers=IT_MANAGER_HEADERS,
        )
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "TAMPERED"
        assert body["event_id"] == target_id

        direct = await verify_chain(pool)
        assert direct["status"] == "TAMPERED"
        assert body["broken_at_index"] == direct["broken_at_index"]

        # Capture and clean up the TAMPER_DEMO_INVOKED audit row the route
        # itself wrote before issuing the tamper.
        invoked_row = await pool.fetchrow(
            "SELECT event_id FROM audit_events WHERE action_type = 'TAMPER_DEMO_INVOKED' "
            "AND target_record_id = $1",
            target_id,
        )
        if invoked_row is not None:
            audit_chain_isolation.append(invoked_row["event_id"])

    asyncio.run(run())
