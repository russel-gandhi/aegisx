"""
Tests for `app.routes.opa` (REMEDIATION-PLAN.md #6).

Points `OPA_URL` at a closed local port to exercise the degrade-to-fallback
path deterministically without needing a live OPA sidecar, the same
technique `test_opa_client.py` already uses for `evaluate_opa_policy()`
itself -- this module tests the HTTP route wrapping it, not
`evaluate_opa_policy()`'s own OPA-vs-fallback branching again.
"""

from fastapi.testclient import TestClient

from app import opa_client as opa_client_module
from app.main import app

client = TestClient(app)

AUDITOR_HEADERS = {"X-User-Id": "test-auditor", "X-User-Role": "Auditor"}


def test_missing_identity_headers_returns_422():
    resp = client.post("/api/opa/evaluate", json={"some": "payload"})
    assert resp.status_code == 422


def test_unrecognised_role_returns_403():
    resp = client.post(
        "/api/opa/evaluate",
        json={"some": "payload"},
        headers={"X-User-Id": "test-user", "X-User-Role": "Not A Real Role"},
    )
    assert resp.status_code == 403


def test_auditor_role_is_permitted_a_read_only_policy_query(monkeypatch):
    # Auditor is the most-restricted role in PERMISSION_MATRIX -- if this
    # route were meant to exclude anyone, Auditor is who it would exclude.
    # It doesn't (see opa.py's own docstring on why gating this on any
    # single PERMISSION_MATRIX agent id would be dead code), so a 200 here
    # is the actual acceptance criterion, not merely convenient.
    monkeypatch.setattr(
        opa_client_module, "OPA_URL", "http://127.0.0.1:9/v1/data/sentinel/gxp/violation"
    )
    resp = client.post(
        "/api/opa/evaluate",
        json={"documents": [{"id": "DOC-1", "status": "DRAFT"}]},
        headers=AUDITOR_HEADERS,
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_opa_unreachable_degrades_to_fallback_rules_not_a_502(monkeypatch):
    monkeypatch.setattr(
        opa_client_module, "OPA_URL", "http://127.0.0.1:9/v1/data/sentinel/gxp/violation"
    )
    resp = client.post(
        "/api/opa/evaluate",
        json={"documents": [{"id": "DOC-1", "status": "DRAFT"}]},
        headers=AUDITOR_HEADERS,
    )
    # Never a 502/504 for an OPA outage -- evaluate_opa_policy() degrades
    # to python_fallback_rules() internally and this route returns
    # whatever that produces as a normal 200, per its own docstring.
    assert resp.status_code == 200
