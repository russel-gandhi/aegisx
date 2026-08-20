"""
Integration and failure-path tests for app.opa_client (SENT-1-04, POL-02).

Covers the plan's <behavior> list:
- live single-document positive case (DRAFT O&M doc) returns
  ANNEX11-S4-DOC-001 against DOC-2026-OM-99
- live single-document negative case (APPROVED) returns []
- live whole-bundle case, built from all 10 seeded gap records (the exact
  literals plan 02-01 seeded — see .planning/phases/02-foundation/
  02-01-PLAN.md Task 2), returns exactly 10 violations whose rule_id set
  equals the full 10-rule set
- every returned dict validates as app.schemas.OPAViolation without
  adaptation
- pointing OPA_URL at a closed local port returns [] and logs a warning,
  without raising
- pointing OPA_URL at a path OPA does not serve (non-2xx) also returns []
  and logs a warning, without raising

Drives the async evaluate_opa_policy() with asyncio.run() inside ordinary
synchronous test functions — pytest-asyncio is intentionally not used (see
02-RESEARCH.md Package Legitimacy Audit; not needed for this suite).

The whole-bundle payload's dates are all real, historical epoch-ns
literals from Bible Section 5 / plan 02-01's seed script (years in the
past relative to any plausible run date), so the date-sensitive rules
remain overdue under the real wall clock without needing to pin
time.now_ns() the way the Rego test suite does — this is deliberate: this
suite proves the same 10 rules fire over HTTP, through Python, against the
running server, under the real clock, which is a different claim than
plan 02-02's `opa test` (pinned clock) proved.
"""

import asyncio
import logging

from app.opa_client import evaluate_opa_policy
from app.schemas import OPAViolation

ALL_TEN_RULE_IDS = {
    "ANNEX11-S4-DOC-001",
    "ANNEX11-S12-ACC-001",
    "ICH-Q9-RSK-001",
    "ANNEX11-S13-INC-001",
    "ANNEX11-S4-TRC-001",
    "ANNEX11-S3-SUP-001",
    "ANNEX11-S11-PE-001",
    "ANNEX11-S16-BCK-001",
    "ANNEX11-S12-ACC-002",
    "ANNEX11-S10-CHG-001",
}

# Full whole-bundle payload, built from the exact literals plan 02-01
# seeded (Bible Section 5 / 02-01-PLAN.md Task 2) — not invented values.
WHOLE_BUNDLE_PAYLOAD = {
    "documents": [{
        "id": "DOC-2026-OM-99", "system_id": "GXP-MFG-DEMO-01",
        "doc_type": "O&M", "status": "DRAFT",
    }],
    "access_reviews": [{
        "id": "AR-2026-05", "system_id": "GXP-MFG-DEMO-01",
        "status": "PENDING", "scheduled_date_ns": 1715424000000000000,
    }],
    "risks": [{
        "id": "RSK-2024-11", "system_id": "GXP-MFG-DEMO-01",
        "last_review_date_ns": 1723718400000000000,
    }],
    "incidents": [{
        "id": "INC-849201", "system_id": "GXP-MFG-DEMO-01",
        "severity": "P1", "status": "OPEN", "rca_started": False,
        "opened_date_ns": 1719830400000000000,
    }],
    "requirements": [{
        "id": "URS-042", "system_id": "GXP-MFG-DEMO-01",
        "test_case_id": "TC-2026-042",
    }],
    # The one input key in the bundle that is a map keyed by id, not a list.
    "test_cases": {"TC-2026-042": {"status": "DRAFT"}},
    "suppliers": [{
        "id": "SUP-2026-01", "system_id": "GXP-MFG-DEMO-01",
        "reassessment_due_date_ns": 1708214400000000000,
    }],
    "periodic_evaluations": [{
        "id": "PE-2024-01", "system_id": "GXP-MFG-DEMO-01",
        "due_date_ns": 1704067200000000000,
    }],
    "gxp_systems": [{
        "id": "GXP-MFG-DEMO-01", "last_backup_test_ns": 1709251200000000000,
    }],
    "access_records": [{
        "id": "ACC-2026-99", "system_id": "GXP-MFG-DEMO-01",
        "is_privileged": True, "user_status": "DEPARTED",
    }],
    "changes": [{
        "id": "CR-2026-089", "system_id": "GXP-MFG-DEMO-01", "status": "CLOSED",
    }],
    "change_actions": [{
        "id": "CA-2026-089-1", "change_id": "CR-2026-089", "status": "OPEN",
    }],
}


def test_live_single_document_positive_case_returns_annex11_s4_doc_001():
    payload = {
        "documents": [{
            "id": "DOC-2026-OM-99", "system_id": "GXP-MFG-DEMO-01",
            "doc_type": "O&M", "status": "DRAFT",
        }]
    }
    violations = asyncio.run(evaluate_opa_policy(payload))
    assert len(violations) == 1
    assert violations[0]["rule_id"] == "ANNEX11-S4-DOC-001"
    assert violations[0]["record_id"] == "DOC-2026-OM-99"


def test_live_single_document_negative_case_returns_empty_list():
    payload = {
        "documents": [{
            "id": "DOC-2026-OM-99", "system_id": "GXP-MFG-DEMO-01",
            "doc_type": "O&M", "status": "APPROVED",
        }]
    }
    violations = asyncio.run(evaluate_opa_policy(payload))
    assert violations == []


def test_live_empty_payload_returns_empty_list_without_error():
    violations = asyncio.run(evaluate_opa_policy({}))
    assert violations == []


def test_live_whole_bundle_all_10_seeded_gaps_produce_exactly_10_violations():
    violations = asyncio.run(evaluate_opa_policy(WHOLE_BUNDLE_PAYLOAD))
    assert len(violations) == 10
    got_ids = {v["rule_id"] for v in violations}
    assert got_ids == ALL_TEN_RULE_IDS


def test_every_returned_violation_validates_as_opa_violation_model():
    violations = asyncio.run(evaluate_opa_policy(WHOLE_BUNDLE_PAYLOAD))
    assert len(violations) == 10
    for v in violations:
        # Constructing without adaptation proves the contract between the
        # Rego rule objects and the Pydantic model holds today.
        model = OPAViolation(**v)
        assert model.rule_id == v["rule_id"]


def test_unreachable_host_returns_empty_list_and_logs_warning(monkeypatch, caplog):
    import app.opa_client as opa_client_module

    monkeypatch.setattr(opa_client_module, "OPA_URL", "http://127.0.0.1:9/v1/data/sentinel/gxp/violation")

    with caplog.at_level(logging.WARNING, logger="app.opa_client"):
        violations = asyncio.run(opa_client_module.evaluate_opa_policy({"documents": []}))

    assert violations == []
    assert any("OPA call failed" in record.message for record in caplog.records)


def test_non_2xx_status_returns_empty_list_and_logs_warning(monkeypatch, caplog):
    import app.opa_client as opa_client_module

    # A valid host (the live OPA server), but a path it does not serve —
    # OPA answers 404, exercising the httpx.HTTPStatusError branch
    # (deviation 2, backend tier) rather than the connection-error branch.
    monkeypatch.setattr(opa_client_module, "OPA_URL", "http://127.0.0.1:8181/nonexistent-route")

    with caplog.at_level(logging.WARNING, logger="app.opa_client"):
        violations = asyncio.run(opa_client_module.evaluate_opa_policy({"documents": []}))

    assert violations == []
    assert any("OPA call failed" in record.message for record in caplog.records)
