"""
Tests for `app.agents.c1_verifier` — the SENT-2-12 Critical-review bar
(Phase 3, plan 03-05; extends the tracer proved in plan 03-02).

CLAUDE.md Rule 6 requires unit + negative + edge-case + integration
coverage for C1, not a smoke test — the tracer (`test_hero_tracer.py`)
proved C1 works on one happy path; this file proves it fails correctly,
which is the harder and more important half (EVID-02). Structured in four
clearly commented sections, one per Rule 6 coverage class, so a reviewer
can see each class is present:

- UNIT: `calculate_confidence()` exercised directly — the grade ladder,
  every threshold boundary, and the arithmetic guarantee that a policy
  contradiction always dominates a perfect ALCOA score.
- NEGATIVE: an LLM-shaped claim that contradicts real Postgres + real OPA
  state (EVID-02), a fabricated evidence id, and the positive-control
  truthful claim that proves the two negative results are discrimination,
  not a mechanism that always refuses.
- EDGE: guards — an unrecognised rule id, an empty `evidence_ids` list.
- INTEGRATION: `run_c1`'s full driver over a mixed finding list (plan
  03-05 Task 1), extended in plan 03-05 Task 2 with all ten
  `policies/gxp_rules.rego` rule ids and both fail-closed outage paths.

Every NEGATIVE-section test that needs real evidence runs against live
Postgres and the live OPA sidecar (`infra/health-check.sh`,
`infra/apply-seed.sh`) — neither is ever mocked in this file (D-04): C1's
entire thesis is that a claim is checked against real state, so a test
proving it fails correctly must use real state too. Follows the
established `asyncio.run()`-inside-a-plain-`def`-test convention
(`test_opa_client.py`, `test_a2_compliance.py`, `test_hero_tracer.py`);
pytest-asyncio is deliberately absent.

`calculate_confidence()`'s constants are NOT under test for correctness
tuning here — they are fixed by transcription (backend/README.md
Deviation 7, D-06) and this file only proves the existing arithmetic
against every boundary, never proposes a different one.
"""

import asyncio

import app.agents.c1_verifier as c1_verifier_module
from app.agents.c1_verifier import (
    calculate_confidence,
    fetch_evidence_record,
    run_c1,
    verify_finding,
)
from app.db import get_pool
from app.schemas import ALCOAScore

ALCOA_FIELDS = [
    "attributable",
    "legible",
    "contemporaneous",
    "original",
    "accurate",
    "complete",
    "consistent",
    "enduring",
    "available",
]


def _alcoa_with_n_true(n: int) -> dict:
    """Builds an ALCOAScore-shaped mapping with exactly `n` of the nine
    fields true, driving the ladder/boundary tests through the real field
    name set on `app.schemas.ALCOAScore` rather than an invented shape —
    so the arithmetic under test is `calculate_confidence()`'s, not the
    fixture's."""
    return {field: (i < n) for i, field in enumerate(ALCOA_FIELDS)}


def _agent_finding(finding_id: str, rule_id: str, evidence_id: str, claim: str, alcoa: dict = None) -> dict:
    """Builds a finding dict shaped exactly like the findings `run_a2`
    actually emits (`backend/README.md`'s "AgentFinding conventions
    (Phase 3)" table) — same keys, same `UNVERIFIED` confidence, same
    nine-field ALCOA mapping — so every fixture below is a plausible agent
    output, not a synthetic shape C1 would never see."""
    return {
        "finding_id": finding_id,
        "claim": claim,
        "regulatory_citations": [rule_id],
        "confidence_score": "UNVERIFIED",
        "evidence_ids": [evidence_id],
        "alcoa_score": alcoa if alcoa is not None else ALCOAScore().model_dump(),
        "model_attribution": "gemini-2.5-flash",
    }


class _PoisonPool:
    """A pool double whose `fetchrow`/`fetch` raise if called at all —
    proves a code path never touches Postgres, not merely that its
    eventual result happens to be `None`. Used for the guard tests where
    the whole point is that no SQL statement is ever built."""

    async def fetchrow(self, *args, **kwargs):
        raise AssertionError("fetchrow must not be called on this path")

    async def fetch(self, *args, **kwargs):
        raise AssertionError("fetch must not be called on this path")


# ---------------------------------------------------------------------------
# UNIT -- calculate_confidence() grade ladder, threshold boundaries, and the
# policy-contradiction-dominates / falsy-db-record / absent-alcoa guarantees
# ---------------------------------------------------------------------------


def test_unit_grade_ladder_full_sweep():
    record = {"id": "DUMMY-RECORD"}
    expectations = {9: "HIGH", 8: "HIGH", 7: "MEDIUM", 6: "MEDIUM", 4: "MEDIUM", 3: "LOW", 0: "LOW"}
    for n_true, expected_grade in expectations.items():
        finding = {"alcoa_score": _alcoa_with_n_true(n_true)}
        got = calculate_confidence(finding, record, True)
        assert got == expected_grade, f"{n_true} true dimensions: expected {expected_grade}, got {got}"


def test_unit_boundary_exclusive_above_80_seven_true_dims_grades_medium_not_high():
    # 7 true dims, policy corroborating: score == 100 - (9-7)*10 == 80.
    # The `> 80` threshold is exclusive, so exactly 80 must be MEDIUM.
    record = {"id": "DUMMY-RECORD"}
    finding = {"alcoa_score": _alcoa_with_n_true(7)}
    assert calculate_confidence(finding, record, True) == "MEDIUM"


def test_unit_boundary_inclusive_at_50_four_true_dims_grades_medium_not_low():
    # 4 true dims, policy corroborating: score == 100 - (9-4)*10 == 50.
    # The `>= 50` threshold is inclusive, so exactly 50 must be MEDIUM.
    record = {"id": "DUMMY-RECORD"}
    finding = {"alcoa_score": _alcoa_with_n_true(4)}
    assert calculate_confidence(finding, record, True) == "MEDIUM"


def test_unit_boundary_exclusive_above_0_nine_true_dims_policy_false_grades_insufficient_not_low():
    # 9 true dims (perfect ALCOA), policy NOT corroborating: score ==
    # 100 - (9-9)*10 - 100 == 0. The `> 0` threshold is exclusive, so
    # exactly 0 must be INSUFFICIENT_EVIDENCE, not LOW -- even a perfect
    # 9-of-9 finding cannot buy its way past a real policy contradiction.
    record = {"id": "DUMMY-RECORD"}
    finding = {"alcoa_score": _alcoa_with_n_true(9)}
    assert calculate_confidence(finding, record, False) == "INSUFFICIENT_EVIDENCE"


def test_unit_policy_contradiction_dominates_across_all_dimension_counts():
    # T-03-25: the -100 policy penalty must guarantee INSUFFICIENT_EVIDENCE
    # for every possible ALCOA dimension count, not just the boundary case.
    record = {"id": "DUMMY-RECORD"}
    for n_true in range(10):  # every possible dimension count, 0 through 9
        finding = {"alcoa_score": _alcoa_with_n_true(n_true)}
        assert calculate_confidence(finding, record, False) == "INSUFFICIENT_EVIDENCE", (
            f"{n_true} true dimensions with a non-corroborating policy must still be "
            "INSUFFICIENT_EVIDENCE"
        )


def test_unit_falsy_db_record_grades_insufficient_regardless_of_dimensions_or_policy():
    for n_true in (0, 5, 9):
        for policy_result in (True, False):
            finding = {"alcoa_score": _alcoa_with_n_true(n_true)}
            assert calculate_confidence(finding, None, policy_result) == "INSUFFICIENT_EVIDENCE"
            assert calculate_confidence(finding, {}, policy_result) == "INSUFFICIENT_EVIDENCE"


def test_unit_absent_or_empty_alcoa_score_grades_low_and_does_not_raise():
    # A1's Bible abstain finding carries "alcoa_score": {} (see
    # minimal_specialists._a1_abstain_finding); an absent key must be
    # tolerated identically. sum({}.values()) == 0, so score ==
    # 100 - (9-0)*10 == 10, which with a corroborating policy is LOW
    # (> 0, not >= 50).
    record = {"id": "DUMMY-RECORD"}
    finding_absent_key = {}
    finding_empty_mapping = {"alcoa_score": {}}
    assert calculate_confidence(finding_absent_key, record, True) == "LOW"
    assert calculate_confidence(finding_empty_mapping, record, True) == "LOW"


def test_unit_run_c1_empty_findings_returns_empty_mapping():
    # The product's core thesis: nothing is trusted by default. An empty
    # findings list must never fall back to a hardcoded verified literal.
    async def _run():
        return await run_c1({"findings": []})

    assert asyncio.run(_run()) == {}


# ---------------------------------------------------------------------------
# NEGATIVE -- EVID-02: an LLM-shaped claim that contradicts real Postgres +
# real OPA state, a fabricated evidence id, and the positive-control proof
# that both negative results are discrimination, not blanket refusal
# ---------------------------------------------------------------------------


def test_negative_evid02_contradiction_against_real_approved_urs_row():
    # infra/postgres/seed/002_urs_fixture.sql seeds DOC-2026-URS-01 as a
    # genuinely real, genuinely APPROVED Postgres row. Rego rule 1
    # (ANNEX11-S4-DOC-001) fires only for doc_type == "O&M"
    # (policies/gxp_rules.rego lines 27-39); this row's doc_type is "URS",
    # so the rule body never matches and OPA returns no violation for it.
    # The claim below asserts the opposite of the real row's real state --
    # real row says APPROVED, real policy engine says nothing -- so this
    # is a genuine contradiction, not an invented one (D-04).
    finding = _agent_finding(
        "TEST-CONTRADICT-DOC-2026-URS-01",
        "ANNEX11-S4-DOC-001",
        "DOC-2026-URS-01",
        "DOC-2026-URS-01 is not in APPROVED state, a violation of EU GMP "
        "Annex 11 Section 4 documentation control.",
    )

    async def _run():
        pool = await get_pool()
        return await verify_finding(pool, finding)

    result = asyncio.run(_run())
    assert result["db_record_found"] is True
    assert result["opa_corroborated"] is False
    assert result["confidence"] == "INSUFFICIENT_EVIDENCE"


def test_negative_evid02_fabricated_evidence_short_circuits_before_opa_call(monkeypatch):
    # PE-9999-FAKE names no row in periodic_evaluations at all. Proving
    # the missing-record short-circuit by call-counting the real
    # evaluate_opa_policy() the module calls (not by reading the source):
    # the count must be zero once this returns.
    calls = {"n": 0}
    real_evaluate = c1_verifier_module.evaluate_opa_policy

    async def _counting_evaluate(payload):
        calls["n"] += 1
        return await real_evaluate(payload)

    monkeypatch.setattr(c1_verifier_module, "evaluate_opa_policy", _counting_evaluate)

    finding = _agent_finding(
        "TEST-FABRICATED-PE-9999-FAKE",
        "ANNEX11-S11-PE-001",
        "PE-9999-FAKE",
        "Periodic evaluation PE-9999-FAKE is overdue under EU GMP Annex 11 Section 11.",
    )

    async def _run():
        pool = await get_pool()
        return await verify_finding(pool, finding)

    result = asyncio.run(_run())
    assert result["db_record_found"] is False
    assert result["confidence"] == "INSUFFICIENT_EVIDENCE"
    assert calls["n"] == 0


def test_negative_positive_control_truthful_claim_against_real_row_scores_medium():
    # In the same module as the two negative fixtures above: a truthful
    # claim against the real, genuinely overdue PE-2024-01 row must still
    # corroborate and score MEDIUM -- proving the negative results above
    # are discrimination, not a mechanism that always refuses.
    finding = _agent_finding(
        "TEST-POSITIVE-PE-2024-01",
        "ANNEX11-S11-PE-001",
        "PE-2024-01",
        "Periodic evaluation PE-2024-01 is overdue under EU GMP Annex 11 "
        "Section 11 and requires immediate review to restore audit readiness.",
    )

    async def _run():
        pool = await get_pool()
        return await verify_finding(pool, finding)

    result = asyncio.run(_run())
    assert result["db_record_found"] is True
    assert result["opa_corroborated"] is True
    assert result["confidence"] == "MEDIUM"


# ---------------------------------------------------------------------------
# EDGE -- guards: an unrecognised rule id resolves no record and builds no
# SQL statement; an empty evidence_ids list is tolerated, not raised on
# ---------------------------------------------------------------------------


def test_edge_unrecognised_rule_id_resolves_no_record_without_building_sql():
    finding = _agent_finding("TEST-UNKNOWN-RULE", "UNKNOWN-RULE-ID-999", "SOME-RECORD-ID", "claim text")

    async def _run():
        record = await fetch_evidence_record(_PoisonPool(), finding)
        result = await verify_finding(_PoisonPool(), finding)
        return record, result

    record, result = asyncio.run(_run())
    assert record is None
    assert result["db_record_found"] is False
    assert result["confidence"] == "INSUFFICIENT_EVIDENCE"


def test_edge_empty_evidence_ids_list_resolves_no_record_without_raising():
    finding = {
        "finding_id": "TEST-EMPTY-EVIDENCE-IDS",
        "claim": "claim text",
        "regulatory_citations": ["ANNEX11-S11-PE-001"],
        "confidence_score": "UNVERIFIED",
        "evidence_ids": [],
        "alcoa_score": ALCOAScore().model_dump(),
        "model_attribution": "gemini-2.5-flash",
    }

    async def _run():
        return await fetch_evidence_record(_PoisonPool(), finding)

    assert asyncio.run(_run()) is None


# ---------------------------------------------------------------------------
# INTEGRATION -- run_c1's full driver over a mixed finding list (plan 03-05
# Task 1); extended in Task 2 with all ten Rego rules and both fail-closed
# outage paths
# ---------------------------------------------------------------------------


def test_integration_run_c1_mixed_list_returns_three_distinct_graded_entries():
    corroborated = _agent_finding(
        "MIX-PE-2024-01",
        "ANNEX11-S11-PE-001",
        "PE-2024-01",
        "Periodic evaluation PE-2024-01 is overdue under EU GMP Annex 11 Section 11.",
    )
    contradicted = _agent_finding(
        "MIX-DOC-2026-URS-01",
        "ANNEX11-S4-DOC-001",
        "DOC-2026-URS-01",
        "DOC-2026-URS-01 is not in APPROVED state, a violation of EU GMP "
        "Annex 11 Section 4 documentation control.",
    )
    fabricated = _agent_finding(
        "MIX-PE-9999-FAKE",
        "ANNEX11-S11-PE-001",
        "PE-9999-FAKE",
        "Periodic evaluation PE-9999-FAKE is overdue under EU GMP Annex 11 Section 11.",
    )
    state = {"findings": [corroborated, contradicted, fabricated]}

    async def _run():
        return await run_c1(state)

    result = asyncio.run(_run())
    verification = result["verification_results"]
    assert set(verification.keys()) == {"MIX-PE-2024-01", "MIX-DOC-2026-URS-01", "MIX-PE-9999-FAKE"}
    assert verification["MIX-PE-2024-01"]["confidence"] == "MEDIUM"
    assert verification["MIX-DOC-2026-URS-01"]["confidence"] == "INSUFFICIENT_EVIDENCE"
    assert verification["MIX-PE-9999-FAKE"]["confidence"] == "INSUFFICIENT_EVIDENCE"
