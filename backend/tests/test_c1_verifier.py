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
import app.opa_client as opa_client_module
from app import db
from app.agents.c1_verifier import (
    RULE_EVIDENCE_TABLES,
    RULE_OPA_INPUT,
    build_opa_payload,
    calculate_alcoa_score,
    calculate_confidence,
    fetch_evidence_record,
    run_c1,
    verify_finding,
)
from app.db import get_pool
from app.schemas import ALCOAScore

# The ten Rego rule ids paired with the exact seeded record each one fires
# on (infra/postgres/seed/001_seed.sql, plan 03-05-PLAN.md <action>), in
# policies/gxp_rules.rego's own declared order.
TEN_RULE_RECORD_PAIRS = [
    ("ANNEX11-S4-DOC-001", "DOC-2026-OM-99"),
    ("ANNEX11-S12-ACC-001", "AR-2026-05"),
    ("ICH-Q9-RSK-001", "RSK-2024-11"),
    ("ANNEX11-S13-INC-001", "INC-849201"),
    ("ANNEX11-S4-TRC-001", "URS-042"),
    ("ANNEX11-S3-SUP-001", "SUP-2026-01"),
    ("ANNEX11-S11-PE-001", "PE-2024-01"),
    ("ANNEX11-S16-BCK-001", "GXP-MFG-DEMO-01"),
    ("ANNEX11-S12-ACC-002", "ACC-2026-99"),
    ("ANNEX11-S10-CHG-001", "CR-2026-089"),
]

VALID_GRADES = {"HIGH", "MEDIUM", "LOW", "INSUFFICIENT_EVIDENCE"}

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
# UNIT -- calculate_alcoa_score() (SENT-9-01): each of the nine dimensions
# checked independently against synthetic record shapes matching this
# schema's real column names, so each assertion pins one dimension's real
# behavior rather than an end-to-end grade that could pass for the wrong
# reason.
# ---------------------------------------------------------------------------


def test_unit_attributable_true_when_a_recognised_who_column_is_populated():
    record = {"id": "DOC-1", "author": "jsmith"}
    assert calculate_alcoa_score(record, {}).attributable is True


def test_unit_attributable_false_when_no_who_column_present_or_populated():
    assert calculate_alcoa_score({"id": "REQ-1"}, {}).attributable is False
    assert calculate_alcoa_score({"id": "DOC-1", "author": None}, {}).attributable is False


def test_unit_legible_true_when_no_text_column_exists_on_this_table():
    # e.g. `periodic_evaluations` has no description/title/req_text/
    # risk_summary column at all -- nothing to check, so this dimension
    # defaults True rather than being fabricated as False.
    record = {"id": "PE-1", "due_date_ns": 123, "status": "DUE"}
    assert calculate_alcoa_score(record, {}).legible is True


def test_unit_legible_false_when_present_text_column_is_empty():
    record = {"id": "REQ-1", "req_text": ""}
    assert calculate_alcoa_score(record, {}).legible is False


def test_unit_legible_true_when_present_text_column_is_populated():
    record = {"id": "REQ-1", "req_text": "The system shall log all access attempts."}
    assert calculate_alcoa_score(record, {}).legible is True


def test_unit_contemporaneous_true_for_a_real_past_timestamp():
    record = {"id": "PE-1", "due_date_ns": 1000}  # far in the past
    assert calculate_alcoa_score(record, {}).contemporaneous is True


def test_unit_contemporaneous_false_when_no_timestamp_column_present():
    # e.g. `requirements` has no timestamp column at all in this schema.
    record = {"id": "REQ-1", "req_text": "some text"}
    assert calculate_alcoa_score(record, {}).contemporaneous is False


def test_unit_contemporaneous_false_for_a_future_dated_anomaly():
    far_future_ns = int(1e19)  # comfortably past any real epoch
    record = {"id": "PE-1", "due_date_ns": far_future_ns}
    assert calculate_alcoa_score(record, {}).contemporaneous is False


def test_unit_original_true_when_documents_version_is_populated():
    record = {"id": "DOC-1", "version": "1.0"}
    assert calculate_alcoa_score(record, {}).original is True


def test_unit_original_false_when_documents_version_is_missing():
    record = {"id": "DOC-1", "version": None}
    assert calculate_alcoa_score(record, {}).original is False


def test_unit_original_true_by_default_when_table_has_no_version_concept():
    # e.g. `risks` has no `version` column at all -- nothing to check.
    record = {"id": "RSK-1", "severity": "HIGH"}
    assert calculate_alcoa_score(record, {}).original is True


def test_unit_accurate_false_when_a_present_status_column_is_null():
    record = {"id": "CHG-1", "status": None}
    assert calculate_alcoa_score(record, {}).accurate is False


def test_unit_accurate_true_when_status_column_is_populated():
    record = {"id": "CHG-1", "status": "CLOSED"}
    assert calculate_alcoa_score(record, {}).accurate is True


def test_unit_complete_false_when_any_non_id_field_is_null_or_empty():
    record = {"id": "PE-1", "system_id": "SYS-1", "due_date_ns": 123, "status": None}
    assert calculate_alcoa_score(record, {}).complete is False


def test_unit_complete_true_when_every_non_id_field_is_populated():
    record = {"id": "PE-1", "system_id": "SYS-1", "due_date_ns": 123, "status": "DUE"}
    assert calculate_alcoa_score(record, {}).complete is True


def test_unit_consistent_true_when_record_id_is_among_findings_evidence_ids():
    record = {"id": "PE-2024-01"}
    finding = {"evidence_ids": ["PE-2024-01"]}
    assert calculate_alcoa_score(record, finding).consistent is True


def test_unit_consistent_false_when_record_id_does_not_match_evidence_ids():
    # Proves this is a real check, not a tautology -- a fetched record
    # whose id doesn't match what the finding claims as its own evidence
    # must be caught, even though `verify_finding`'s own fetch path in
    # practice always fetches by the finding's first evidence_id (this
    # unit test exercises the function directly, independent of that
    # caller's own guarantee).
    record = {"id": "PE-OTHER"}
    finding = {"evidence_ids": ["PE-2024-01"]}
    assert calculate_alcoa_score(record, finding).consistent is False


def test_unit_enduring_and_available_are_true_for_any_fetched_record():
    # Both are true by construction: this function only ever runs on a
    # record that was already successfully, durably fetched from Postgres.
    score = calculate_alcoa_score({"id": "ANYTHING"}, {})
    assert score.enduring is True
    assert score.available is True


def test_unit_real_score_differs_between_two_different_real_record_shapes():
    # The whole point of SENT-9-01: two different records must NOT produce
    # the same score just because both are "some record" -- a complete,
    # attributable, contemporaneous document scores higher than a bare
    # partial record with none of that.
    rich_record = {
        "id": "DOC-1", "system_id": "SYS-1", "author": "jsmith",
        "created_date": 1000, "version": "2.0", "status": "APPROVED",
        "title": "SOP-001",
    }
    sparse_record = {"id": "REQ-1", "system_id": "SYS-1"}

    rich_score = calculate_alcoa_score(rich_record, {"evidence_ids": ["DOC-1"]})
    sparse_score = calculate_alcoa_score(sparse_record, {"evidence_ids": ["REQ-1"]})

    assert sum(rich_score.model_dump().values()) > sum(sparse_score.model_dump().values())


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


def test_unit_run_c1_no_pool_still_attaches_opa_bundle_hash(monkeypatch):
    """2026-09-02 incident remediation: run_c1's own no-pool fail-closed
    branch (every finding forced to INSUFFICIENT_EVIDENCE) never touches
    Postgres — but the bundle fingerprint is a local filesystem read, not a
    DB read, so it must still be present even here."""
    async def _no_pool():
        return None

    monkeypatch.setattr(c1_verifier_module, "acquire_pool_or_none", _no_pool)

    finding = _agent_finding(
        "NO-POOL-1", "ANNEX11-S11-PE-001", "PE-2024-01", "irrelevant claim text",
    )

    async def _run():
        return await run_c1({"findings": [finding]})

    result = asyncio.run(_run())
    entry = result["verification_results"]["NO-POOL-1"]
    assert entry["confidence"] == "INSUFFICIENT_EVIDENCE"
    assert entry["opa_bundle_hash"] not in (None, "")
    assert len(entry["opa_bundle_hash"]) == 64


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
    # 2026-09-02 incident remediation: the bundle fingerprint is a pure
    # filesystem read, independent of db_record_found/OPA outcome — present
    # on every verify_finding() branch, including this missing-record one.
    assert result["opa_bundle_hash"] not in (None, "")
    assert len(result["opa_bundle_hash"]) == 64


def test_negative_positive_control_truthful_claim_against_real_row_scores_high():
    # In the same module as the two negative fixtures above: a truthful
    # claim against the real, genuinely overdue PE-2024-01 row must still
    # corroborate -- proving the negative results above are discrimination,
    # not a mechanism that always refuses.
    #
    # SENT-9-01: this graded MEDIUM before real per-record ALCOA+ scoring
    # replaced the fixed `ALCOAScore()` default every finding used to carry
    # regardless of its actual record. `_agent_finding`'s fixture default is
    # now irrelevant to the grade -- `verify_finding` overwrites it with a
    # real score computed from `periodic_evaluations`' actual columns
    # (`due_date_ns`, `status`), and PE-2024-01 genuinely has both
    # populated, non-future, internally consistent (its own `id` matches
    # the finding's `evidence_ids`) -- 8 of 9 real dimensions true (only
    # `attributable` is false: `periodic_evaluations` has no author/owner
    # column at all), grading HIGH rather than the old constant MEDIUM.
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
    assert result["confidence"] == "HIGH"


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
    # SENT-9-01: see test_negative_positive_control_truthful_claim_against_
    # real_row_scores_high's comment -- PE-2024-01's real ALCOA+ dimensions
    # (8 of 9 true) now grade HIGH, not the old fixed-default MEDIUM.
    assert verification["MIX-PE-2024-01"]["confidence"] == "HIGH"
    assert verification["MIX-DOC-2026-URS-01"]["confidence"] == "INSUFFICIENT_EVIDENCE"
    assert verification["MIX-PE-9999-FAKE"]["confidence"] == "INSUFFICIENT_EVIDENCE"


def test_integration_ten_rules_resolve_real_record_and_payload_shape_matches_documented_input():
    async def _run():
        pool = await get_pool()
        results = []
        for rule_id, record_id in TEN_RULE_RECORD_PAIRS:
            finding = _agent_finding(f"TENRULE-{rule_id}-{record_id}", rule_id, record_id, "claim text")
            record = await fetch_evidence_record(pool, finding)
            payload = await build_opa_payload(pool, finding)
            results.append((rule_id, record, payload))
        return results

    results = asyncio.run(_run())
    assert len(results) == len(TEN_RULE_RECORD_PAIRS) == len(RULE_EVIDENCE_TABLES) == 10
    for rule_id, record, payload in results:
        assert record is not None, f"{rule_id}: expected a real Postgres row, got None"
        expected_keys = {spec[0] for spec in RULE_OPA_INPUT[rule_id]}
        assert set(payload.keys()) == expected_keys, (
            f"{rule_id}: payload keys {set(payload.keys())} != documented input {expected_keys}"
        )


def test_integration_ten_rules_verify_finding_grades_and_at_least_eight_corroborate():
    async def _run():
        pool = await get_pool()
        results = []
        for rule_id, record_id in TEN_RULE_RECORD_PAIRS:
            finding = _agent_finding(f"TENRULE-{rule_id}-{record_id}", rule_id, record_id, "claim text")
            results.append((rule_id, await verify_finding(pool, finding)))
        return results

    results = asyncio.run(_run())
    corroborated_count = 0
    for rule_id, result in results:
        assert result["confidence"] in VALID_GRADES, f"{rule_id}: unexpected grade {result['confidence']!r}"
        assert result["db_record_found"] is True, f"{rule_id}: expected a real seeded record"
        if result["opa_corroborated"] is True:
            corroborated_count += 1
    assert corroborated_count >= 8, (
        f"expected at least 8 of 10 seeded gap records to corroborate, got {corroborated_count}"
    )


def test_integration_rule_5_payload_test_cases_object_shape_and_corroborates():
    finding = _agent_finding("TENRULE-TRC-URS-042", "ANNEX11-S4-TRC-001", "URS-042", "claim text")

    async def _run():
        pool = await get_pool()
        payload = await build_opa_payload(pool, finding)
        result = await verify_finding(pool, finding)
        return payload, result

    payload, result = asyncio.run(_run())
    assert isinstance(payload["test_cases"], dict), "rule 5's test_cases must be an object, not a list"
    assert "TC-2026-042" in payload["test_cases"]
    assert result["opa_corroborated"] is True


def test_integration_rule_10_payload_carries_both_changes_and_change_actions_keys():
    finding = _agent_finding("TENRULE-CHG-CR-2026-089", "ANNEX11-S10-CHG-001", "CR-2026-089", "claim text")

    async def _run():
        pool = await get_pool()
        return await build_opa_payload(pool, finding)

    payload = asyncio.run(_run())
    assert set(payload.keys()) == {"changes", "change_actions"}
    assert len(payload["change_actions"]) >= 1


def test_integration_fail_closed_opa_unreachable_all_ten_grade_insufficient_evidence(monkeypatch):
    # Same closed-port monkeypatch pattern as test_opa_client.py's own
    # unreachable-host test; the monkeypatch fixture restores OPA_URL
    # automatically after this test, so no later test inherits it.
    monkeypatch.setattr(opa_client_module, "OPA_URL", "http://127.0.0.1:9/v1/data/sentinel/gxp/violation")

    async def _run():
        pool = await get_pool()
        results = []
        for rule_id, record_id in TEN_RULE_RECORD_PAIRS:
            finding = _agent_finding(f"TENRULE-{rule_id}-{record_id}", rule_id, record_id, "claim text")
            results.append((rule_id, await verify_finding(pool, finding)))
        return results

    results = asyncio.run(_run())
    for rule_id, result in results:
        assert result["confidence"] == "INSUFFICIENT_EVIDENCE", (
            f"{rule_id}: OPA outage must fail closed, got {result['confidence']!r}"
        )
        assert result["opa_corroborated"] is False


def test_integration_fail_closed_postgres_unreachable_run_c1_all_insufficient_evidence(monkeypatch, reset_db_pool):
    # Same unreachable-DATABASE_URL monkeypatch pattern
    # test_a2_compliance.py's own Postgres-unreachable test uses;
    # reset_db_pool closes the pool before and after so this does not leak
    # a broken pool into a later test.
    monkeypatch.setattr(db, "DATABASE_URL", "postgresql://sentinel:sentinel@127.0.0.1:1/sentinel")

    findings = [
        _agent_finding(f"TENRULE-{rule_id}-{record_id}", rule_id, record_id, "claim text")
        for rule_id, record_id in TEN_RULE_RECORD_PAIRS
    ]

    async def _run():
        return await run_c1({"findings": findings})

    result = asyncio.run(_run())  # must not raise
    verification = result["verification_results"]
    assert len(verification) == 10
    for finding_id, entry in verification.items():
        assert entry["confidence"] == "INSUFFICIENT_EVIDENCE", (
            f"{finding_id}: Postgres outage must fail closed, got {entry['confidence']!r}"
        )
