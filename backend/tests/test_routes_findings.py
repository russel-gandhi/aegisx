"""
Tests for `app.routes.findings` (Phase 4, plan 04-03).

Ticket: SENT-3-05 | Requirement: EVID-03 | Decision: D-04
Source: 04-03-PLAN.md <behavior>.

CLAUDE.md Rule 6 requires unit + negative + edge-case + integration
coverage, not a smoke test. Structured in four clearly commented
sections, one per coverage class (mirrors test_c1_verifier.py):

- UNIT: `_assemble_card()` exercised directly against hand-built
  check-result/finding/verification-result dicts -- no Postgres, no OPA.
  Proves confidence is read from the verification result, never from
  the finding's own `UNVERIFIED` placeholder (critical finding 6).
- NEGATIVE / discrimination: `BUS-IT-DEMO-02` (whose periodic-evaluation
  check fails with no record) must grade every card
  `INSUFFICIENT_EVIDENCE`, proving the endpoint refuses as readily as it
  verifies; no card anywhere carries the `UNVERIFIED` placeholder; an
  unknown system_id 404s.
- EDGE: an unreachable Postgres 503s instead of fabricating a card; an
  unreachable OPA still 200s but every card grades
  `INSUFFICIENT_EVIDENCE` (C1 fails closed).
- INTEGRATION: `GXP-MFG-DEMO-01` against live, seeded Postgres and live
  OPA -- never mocked (this suite's standing convention) -- including a
  provenance check that the periodic-evaluation card's evidence id
  resolves to a real `periodic_evaluations` row.
"""

import asyncio

import app.opa_client as opa_client_module
from app import db
from app.agents.c1_verifier import RULE_EVIDENCE_TABLES
from app.db import get_pool
from app.routes.findings import _assemble_card
from app.schemas import ALCOAScore

# ---------------------------------------------------------------------------
# UNIT
# ---------------------------------------------------------------------------


def test_unit_assemble_card_reads_confidence_from_verification_not_finding():
    check_result = {
        "check": "verify_periodic_eval_current",
        "rule_id": "ANNEX11-S11-PE-001",
        "passed": False,
        "record": {"id": "PE-2024-01"},
    }
    finding = {
        "finding_id": "A2-ANNEX11-S11-PE-001-PE-2024-01",
        "claim": "The periodic evaluation is overdue.",
        "regulatory_citations": ["ANNEX11-S11-PE-001"],
        "confidence_score": "UNVERIFIED",
        "evidence_ids": ["PE-2024-01"],
        "alcoa_score": ALCOAScore().model_dump(),
        "model_attribution": "deterministic-fallback",
    }
    verification_result = {
        "confidence": "MEDIUM",
        "db_record_found": True,
        "opa_corroborated": True,
        "opa_rule_ids": ["ANNEX11-S11-PE-001"],
        "evidence_ids": ["PE-2024-01"],
    }

    card = _assemble_card(check_result, finding, verification_result)

    # The finding's own placeholder is UNVERIFIED -- the card must never
    # echo it. This is the single most important assertion in this file.
    assert finding["confidence_score"] == "UNVERIFIED"
    assert card.confidence == "MEDIUM"
    assert card.confidence != finding["confidence_score"]
    assert card.finding_id == finding["finding_id"]
    assert card.claim == finding["claim"]
    assert card.evidence_ids == finding["evidence_ids"]
    assert card.regulatory_citations == finding["regulatory_citations"]
    assert card.model_attribution == finding["model_attribution"]
    assert card.alcoa_score == finding["alcoa_score"]
    assert card.deterministic_check.check_name == "verify_periodic_eval_current"
    assert card.deterministic_check.passed is False
    assert card.deterministic_check.db_record_found is True
    assert card.deterministic_check.opa_corroborated is True
    assert card.deterministic_check.opa_rule_ids == ["ANNEX11-S11-PE-001"]


def test_unit_assemble_card_no_record_yields_insufficient_evidence():
    check_result = {
        "check": "verify_periodic_eval_current",
        "rule_id": "ANNEX11-S11-PE-001",
        "passed": False,
        "record": None,
    }
    finding = {
        "finding_id": "A2-ANNEX11-S11-PE-001-NO-RECORD",
        "claim": "No periodic evaluation record exists.",
        "regulatory_citations": ["ANNEX11-S11-PE-001"],
        "confidence_score": "UNVERIFIED",
        "evidence_ids": [],
        "alcoa_score": ALCOAScore().model_dump(),
        "model_attribution": "deterministic-fallback",
    }
    verification_result = {
        "confidence": "INSUFFICIENT_EVIDENCE",
        "db_record_found": False,
        "opa_corroborated": False,
        "opa_rule_ids": ["ANNEX11-S11-PE-001"],
        "evidence_ids": [],
    }

    card = _assemble_card(check_result, finding, verification_result)

    assert card.confidence == "INSUFFICIENT_EVIDENCE"
    assert card.evidence_ids == []
    assert card.deterministic_check.db_record_found is False
    assert card.deterministic_check.opa_corroborated is False


# ---------------------------------------------------------------------------
# NEGATIVE / discrimination
# ---------------------------------------------------------------------------


def test_negative_bus_it_demo_all_cards_grade_insufficient_evidence(client):
    resp = client.get("/api/systems/BUS-IT-DEMO-02/assurance-cards")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["cards"]) > 0
    assert all(c["confidence"] == "INSUFFICIENT_EVIDENCE" for c in body["cards"])


def test_negative_no_card_anywhere_carries_the_unverified_placeholder(client):
    for system_id in ("GXP-MFG-DEMO-01", "BUS-IT-DEMO-02"):
        resp = client.get(f"/api/systems/{system_id}/assurance-cards")
        assert resp.status_code == 200
        for card in resp.json()["cards"]:
            assert card["confidence"] != "UNVERIFIED"


def test_negative_unknown_system_returns_404(client):
    resp = client.get("/api/systems/NO-SUCH-SYSTEM/assurance-cards")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# EDGE
# ---------------------------------------------------------------------------


def test_edge_postgres_unreachable_returns_503(client, monkeypatch, reset_db_pool):
    monkeypatch.setattr(
        db, "DATABASE_URL", "postgresql://sentinel:sentinel@127.0.0.1:1/sentinel"
    )
    resp = client.get("/api/systems/GXP-MFG-DEMO-01/assurance-cards")
    assert resp.status_code == 503


def test_edge_opa_unreachable_all_cards_grade_insufficient_evidence(client, monkeypatch):
    # Same closed-port monkeypatch pattern as test_c1_verifier.py's own
    # OPA-unreachable test; the endpoint must still 200 (it verifies, it
    # does not crash) but every card must fail closed rather than papering
    # over the outage.
    monkeypatch.setattr(
        opa_client_module, "OPA_URL", "http://127.0.0.1:9/v1/data/sentinel/gxp/violation"
    )
    resp = client.get("/api/systems/GXP-MFG-DEMO-01/assurance-cards")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["cards"]) == 2
    assert all(c["confidence"] == "INSUFFICIENT_EVIDENCE" for c in body["cards"])
    assert all(c["deterministic_check"]["opa_corroborated"] is False for c in body["cards"])


# ---------------------------------------------------------------------------
# INTEGRATION
# ---------------------------------------------------------------------------


def test_integration_gxp_demo_returns_exactly_two_cards(client):
    resp = client.get("/api/systems/GXP-MFG-DEMO-01/assurance-cards")
    assert resp.status_code == 200
    body = resp.json()
    assert body["system_id"] == "GXP-MFG-DEMO-01"
    assert len(body["cards"]) == 2


def test_integration_gxp_demo_check_names_are_exactly_the_two_failing_checks(client):
    resp = client.get("/api/systems/GXP-MFG-DEMO-01/assurance-cards")
    body = resp.json()
    check_names = {c["deterministic_check"]["check_name"] for c in body["cards"]}
    assert check_names == {"verify_periodic_eval_current", "verify_test_traceability"}
    assert "verify_urs_approved" not in check_names


def test_integration_gxp_demo_cards_have_valid_claim_citation_and_confidence_domain(client):
    resp = client.get("/api/systems/GXP-MFG-DEMO-01/assurance-cards")
    body = resp.json()
    assert len(body["cards"]) > 0
    for card in body["cards"]:
        assert card["claim"]
        assert card["regulatory_citations"]
        for rule_id in card["regulatory_citations"]:
            assert rule_id in RULE_EVIDENCE_TABLES
        assert card["confidence"] in {"HIGH", "MEDIUM", "LOW", "INSUFFICIENT_EVIDENCE"}


def test_integration_periodic_evaluation_card_grades_medium_with_real_evidence(client):
    resp = client.get("/api/systems/GXP-MFG-DEMO-01/assurance-cards")
    body = resp.json()
    pe_card = next(
        c
        for c in body["cards"]
        if c["deterministic_check"]["check_name"] == "verify_periodic_eval_current"
    )
    assert pe_card["evidence_ids"] == ["PE-2024-01"]
    assert pe_card["deterministic_check"]["passed"] is False
    assert pe_card["deterministic_check"]["db_record_found"] is True
    assert pe_card["deterministic_check"]["opa_corroborated"] is True
    assert pe_card["confidence"] == "MEDIUM"


def test_integration_periodic_evaluation_evidence_id_resolves_to_a_real_row(client):
    # Provenance check: a fabricated evidence id would fail here rather
    # than merely passing on shape alone.
    resp = client.get("/api/systems/GXP-MFG-DEMO-01/assurance-cards")
    body = resp.json()
    pe_card = next(
        c
        for c in body["cards"]
        if c["deterministic_check"]["check_name"] == "verify_periodic_eval_current"
    )
    evidence_id = pe_card["evidence_ids"][0]

    async def _count():
        pool = await get_pool()
        return await pool.fetchval(
            "SELECT count(*) FROM periodic_evaluations WHERE id = $1", evidence_id
        )

    assert asyncio.run(_count()) == 1


def test_integration_alcoa_score_has_exactly_the_nine_field_names_all_boolean(client):
    resp = client.get("/api/systems/GXP-MFG-DEMO-01/assurance-cards")
    body = resp.json()
    expected_keys = set(ALCOAScore().model_dump().keys())
    assert len(expected_keys) == 9
    for card in body["cards"]:
        alcoa = card["alcoa_score"]
        assert set(alcoa.keys()) == expected_keys
        assert all(isinstance(v, bool) for v in alcoa.values())
