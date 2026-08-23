"""
Tests for the audit-chain HTTP routes (Phase 5, plan 05-03).

Ticket: SENT-4-06, SENT-4-07 | Requirement: AUDIT-02, AUDIT-03

Follows this suite's established `TestClient` module-level pattern
(`test_routes_actions.py`) plus `asyncio.run()` inside plain `def test_*`
bodies (`conftest.py`) for direct-DB setup/teardown. Every test that
appends `audit_events` rows uses `audit_chain_isolation` (added in Task 2)
so a later test in the same session sees a clean append point.
"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

IT_MANAGER_HEADERS = {"X-User-Id": "test-it-manager", "X-User-Role": "IT System Manager"}


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


def test_demonstrate_tamper_unknown_event_id_returns_no_such_event():
    response = client.post(
        "/api/audit/demonstrate-tamper",
        json={"event_id": "EVT-this-id-was-never-inserted"},
        headers=IT_MANAGER_HEADERS,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "NO_SUCH_EVENT"
    assert body["rows_modified"] == 0
