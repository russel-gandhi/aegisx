"""
Tests for `app.routes.findings` (Phase 4, plan 04-03; SSE streaming
sibling route + concurrency added quick task 260826-p1q).

Ticket: SENT-3-05 | Requirement: EVID-03 | Decision: D-04
Source: 04-03-PLAN.md <behavior>; 260826-p1q-PLAN.md Task 2 <behavior>.

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
  unknown system_id 404s (blocking AND streaming route).
- EDGE: an unreachable Postgres 503s instead of fabricating a card; an
  unreachable OPA still 200s but every card grades
  `INSUFFICIENT_EVIDENCE` (C1 fails closed). Both checked against the
  streaming route as well as the blocking one -- these HTTPException
  guards must fire BEFORE `StreamingResponse` commits its 200 status
  line, never inside the generator.
- INTEGRATION: `GXP-MFG-DEMO-01` against live, seeded Postgres and live
  OPA -- never mocked (this suite's standing convention; no provider key
  is set in this file, so every narration call resolves via the real
  keyless-degrade path, `_MissingKeyError` before any HTTP attempt --
  never a real network call) -- including a provenance check that the
  periodic-evaluation card's evidence id resolves to a real
  `periodic_evaluations` row, the streaming route's frame sequence and
  single terminal frame, and the Rule-6 equivalence proof that the
  concurrent streaming path's deterministic fields exactly match the
  concurrent blocking path's for the same system.
"""

import asyncio
import json

import app.opa_client as opa_client_module
import app.routes.findings as findings_route
from app import db
from app.agents.c1_verifier import RULE_EVIDENCE_TABLES
from app.db import get_pool
from app.routes.findings import _assemble_card
from app.schemas import ALCOAScore

STREAM_PATH = "/api/systems/{system_id}/assurance-cards/stream"


def _read_stream_frames(client, system_id):
    """Drives the streaming route via `client.stream(...)`, parsing each
    `data: ` line into its JSON frame. Returns `(status_code, frames)`."""
    frames = []
    with client.stream("GET", STREAM_PATH.format(system_id=system_id)) as response:
        status_code = response.status_code
        for line in response.iter_lines():
            if not line or not line.startswith("data: "):
                continue
            frames.append(json.loads(line[len("data: ") :]))
    return status_code, frames

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


def test_negative_stream_unknown_system_returns_404_as_a_real_status_not_an_error_frame(client):
    # The 404 guard runs in the route function, above the generator, so an
    # unknown system_id never gets as far as StreamingResponse committing a
    # 200 status line -- this must be a real 404, not a 200 stream
    # containing an error frame.
    resp = client.get("/api/systems/NO-SUCH-SYSTEM/assurance-cards/stream")
    assert resp.status_code == 404
    assert resp.headers["content-type"].startswith("application/json")


# ---------------------------------------------------------------------------
# EDGE
# ---------------------------------------------------------------------------


def test_edge_postgres_unreachable_returns_503(client, monkeypatch, reset_db_pool):
    monkeypatch.setattr(
        db, "DATABASE_URL", "postgresql://sentinel:sentinel@127.0.0.1:1/sentinel"
    )
    resp = client.get("/api/systems/GXP-MFG-DEMO-01/assurance-cards")
    assert resp.status_code == 503


def test_edge_stream_postgres_unreachable_returns_503_as_a_real_status_not_an_error_frame(
    client, monkeypatch, reset_db_pool
):
    # Same guard-before-generator requirement as the 404 case above: the
    # pool-unavailable check runs before StreamingResponse is even
    # constructed, so this must be a real 503, not a 200 stream containing
    # an error frame.
    monkeypatch.setattr(
        db, "DATABASE_URL", "postgresql://sentinel:sentinel@127.0.0.1:1/sentinel"
    )
    resp = client.get("/api/systems/GXP-MFG-DEMO-01/assurance-cards/stream")
    assert resp.status_code == 503
    assert resp.headers["content-type"].startswith("application/json")


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
    # Count-agnostic since the route widened past A2's four checks: what
    # this test guards is the GRADE, not how many cards exist.
    assert len(body["cards"]) > 0
    assert all(c["confidence"] == "INSUFFICIENT_EVIDENCE" for c in body["cards"])
    assert all(c["deterministic_check"]["opa_corroborated"] is False for c in body["cards"])


# ---------------------------------------------------------------------------
# INTEGRATION
# ---------------------------------------------------------------------------


def test_integration_gxp_demo_returns_a_card_per_failing_rule(client):
    """2026-09-09: was `..._returns_exactly_two_cards`. This route ran
    `A2_CHECKS` alone, so only 4 of the 10 rules in
    `policies/gxp_rules.rego` could ever reach the Command Centre -- the
    risk, change, incident and access rules were evaluated by A3-A6 on
    every Copilot query, verified by C1, and then never surfaced on the
    page that exists to summarise compliance posture. Asserted as a range
    against the seeded gaps rather than a fixed 2, so adding a seeded gap
    does not fail an unrelated test."""
    resp = client.get("/api/systems/GXP-MFG-DEMO-01/assurance-cards")
    assert resp.status_code == 200
    body = resp.json()
    assert body["system_id"] == "GXP-MFG-DEMO-01"
    assert 2 < len(body["cards"]) <= 10, "A2's own checks plus the specialist rules"


def test_integration_gxp_demo_surfaces_both_a2_and_specialist_checks(client):
    """The point of the widening, asserted in both directions: A2's two
    failing checks are still present, AND specialist rules now appear."""
    resp = client.get("/api/systems/GXP-MFG-DEMO-01/assurance-cards")
    body = resp.json()
    check_names = {c["deterministic_check"]["check_name"] for c in body["cards"]}

    assert {"verify_periodic_eval_current", "verify_test_traceability"} <= check_names
    # Still passing on this system, so still no card -- the widening must
    # not have turned a passing check into a spurious finding.
    assert "verify_urs_approved" not in check_names
    # At least one rule that only A3-A6 can produce.
    assert check_names & set(findings_route._SPECIALIST_CHECK_NAMES.values())


def test_specialist_check_names_cover_every_specialist_rule():
    """Guard for the map that gives A3-A6 findings a check name: a finding
    whose rule is unmapped is dropped from the grid rather than shown under
    a guessed name, so a missing entry fails silently in production."""
    assert set(findings_route._SPECIALIST_CHECK_NAMES) == {
        "ICH-Q9-RSK-001",
        "ANNEX11-S10-CHG-001",
        "ANNEX11-S13-INC-001",
        "ANNEX11-S12-ACC-001",
        "ANNEX11-S12-ACC-002",
    }
    # Names must be unique -- two rules sharing one name would collapse into
    # a single tile on the Command Centre.
    names = list(findings_route._SPECIALIST_CHECK_NAMES.values())
    assert len(names) == len(set(names))


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


def test_integration_periodic_evaluation_card_grades_high_with_real_evidence(client):
    # SENT-9-01: PE-2024-01's real per-record ALCOA+ score (8 of 9
    # dimensions true against `periodic_evaluations`' actual columns) now
    # grades HIGH, not the old fixed-`ALCOAScore()`-default MEDIUM -- see
    # test_c1_verifier.py's identical fix for the full derivation.
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
    assert pe_card["confidence"] == "HIGH"


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


# ---------------------------------------------------------------------------
# INTEGRATION -- streaming route (quick task 260826-p1q)
# ---------------------------------------------------------------------------


def test_integration_stream_gxp_demo_yields_a_card_frame_per_gap_then_one_terminal_frame(client):
    status_code, frames = _read_stream_frames(client, "GXP-MFG-DEMO-01")
    assert status_code == 200

    card_frames = [f for f in frames if f["event"] == "card"]
    terminal_frames = [f for f in frames if f["event"] == "done"]
    error_frames = [f for f in frames if f["event"] == "error"]

    assert error_frames == []
    assert len(card_frames) > 2, "A2's checks plus the specialist rules"
    # Exactly one terminal frame, and it comes last.
    assert len(terminal_frames) == 1
    assert frames[-1]["event"] == "done"
    assert terminal_frames[0]["system_id"] == "GXP-MFG-DEMO-01"
    # The terminal count must equal the frames actually emitted, whatever
    # that number is -- a stale literal here would hide a dropped card.
    assert terminal_frames[0]["count"] == len(card_frames)

    check_names = {f["card"]["deterministic_check"]["check_name"] for f in card_frames}
    # A2's two failing checks are still streamed, and the specialist rules
    # now stream alongside them -- asserted as a superset plus a non-empty
    # specialist intersection rather than an exact set, so the stream stays
    # in step with the blocking route without pinning a card count.
    assert {"verify_periodic_eval_current", "verify_test_traceability"} <= check_names
    assert check_names & set(findings_route._SPECIALIST_CHECK_NAMES.values())


def test_integration_stream_bus_it_demo_all_cards_grade_insufficient_evidence(client):
    status_code, frames = _read_stream_frames(client, "BUS-IT-DEMO-02")
    assert status_code == 200

    card_frames = [f for f in frames if f["event"] == "card"]
    terminal_frames = [f for f in frames if f["event"] == "done"]
    assert len(card_frames) > 0
    assert all(f["card"]["confidence"] == "INSUFFICIENT_EVIDENCE" for f in card_frames)
    assert terminal_frames[0]["count"] == len(card_frames)


def test_integration_blocking_and_streaming_routes_agree_on_every_deterministic_field(client):
    # Rule-6 proof (CLAUDE.md): concurrency must change no grade.
    # verify_finding() is untouched -- still synchronous per finding, still
    # uncached, still awaited to completion before any card is emitted --
    # and this test proves that by fetching both the sequential-order
    # blocking route and the completion-order streaming route for the same
    # system under identical live Postgres/OPA state, then asserting the
    # SET of (finding_id, confidence, db_record_found, opa_corroborated,
    # opa_rule_ids) tuples is exactly the same regardless of which order
    # each path computed them in.
    def _tuple_set(cards):
        return {
            (
                c["finding_id"],
                c["confidence"],
                c["deterministic_check"]["db_record_found"],
                c["deterministic_check"]["opa_corroborated"],
                tuple(c["deterministic_check"]["opa_rule_ids"]),
            )
            for c in cards
        }

    blocking_resp = client.get("/api/systems/GXP-MFG-DEMO-01/assurance-cards")
    assert blocking_resp.status_code == 200
    blocking_cards = blocking_resp.json()["cards"]

    _, stream_frames = _read_stream_frames(client, "GXP-MFG-DEMO-01")
    streaming_cards = [f["card"] for f in stream_frames if f["event"] == "card"]

    # The two routes must agree on COUNT and content. Pinning a literal
    # here let the routes silently diverge when only one of them was
    # widened to include the specialist rules.
    assert len(blocking_cards) == len(streaming_cards)
    assert len(blocking_cards) > 0
    assert _tuple_set(blocking_cards) == _tuple_set(streaming_cards)
