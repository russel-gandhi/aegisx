"""
Tests for `app.agents.a2_compliance` — all three Bible-named deterministic
checks (Phase 3, plan 03-04).

Runs against the live seeded Postgres (`infra/apply-seed.sh`, extended by
`infra/postgres/seed/002_urs_fixture.sql`, D-05). Every test that needs
rows the seed does not provide inserts them inside an explicit
transaction that is rolled back in a `finally` block, so this suite
leaves the seeded database byte-identical and stays re-runnable
(`infra/verify-seed.sh` must still report `SEED OK` after this file runs).

Follows the established `asyncio.run()`-inside-a-plain-`def`-test
convention (`test_opa_client.py`, `test_hero_tracer.py`); pytest-asyncio
is deliberately absent.
"""

import asyncio

import httpx
import respx

from app import db
from app.db import get_pool
from app.agents.a2_compliance import (
    A2_CHECKS,
    build_finding,
    run_a2,
    verify_periodic_eval_current,
    verify_test_traceability,
    verify_urs_approved,
)

GXP_SYSTEM = "GXP-MFG-DEMO-01"
HEALTHY_SYSTEM = "BUS-IT-DEMO-02"

GEMINI_SUCCESS_BODY = {
    "candidates": [
        {
            "content": {
                "parts": [
                    {
                        "text": (
                            "Compliance gap confirmed against the deterministic "
                            "check result; review required under EU GMP Annex 11."
                        )
                    }
                ]
            }
        }
    ]
}

GEMINI_ENDPOINT = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-2.5-flash:generateContent"
)


def _no_provider_keys(monkeypatch):
    for env_name in (
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
        "DEEPSEEK_API_KEY",
        "GROQ_API_KEY",
        "OPENROUTER_API_KEY",
    ):
        monkeypatch.delenv(env_name, raising=False)


# ---------------------------------------------------------------------------
# verify_urs_approved
# ---------------------------------------------------------------------------


def test_verify_urs_approved_passes_against_seeded_approved_row():
    async def _run():
        pool = await get_pool()
        return await verify_urs_approved(pool, GXP_SYSTEM)

    result = asyncio.run(_run())
    assert result["passed"] is True
    assert result["record"]["id"] == "DOC-2026-URS-01"


def test_verify_urs_approved_fails_with_null_record_when_no_urs_document():
    async def _run():
        pool = await get_pool()
        return await verify_urs_approved(pool, HEALTHY_SYSTEM)

    result = asyncio.run(_run())
    assert result["passed"] is False
    assert result["record"] is None


def test_verify_urs_approved_fails_when_urs_document_not_approved():
    async def _run():
        pool = await get_pool()
        async with pool.acquire() as conn:
            tr = conn.transaction()
            await tr.start()
            try:
                await conn.execute(
                    "INSERT INTO gxp_systems (id, name, system_owner, lifecycle_state) "
                    "VALUES ($1, $2, $3, $4)",
                    "TEST-A2-URS-DRAFT", "Test URS-Draft System", "Test Owner", "OPERATIONAL",
                )
                await conn.execute(
                    "INSERT INTO documents (id, system_id, doc_type, status) "
                    "VALUES ($1, $2, $3, $4)",
                    "TEST-DOC-URS-DRAFT", "TEST-A2-URS-DRAFT", "URS", "DRAFT",
                )
                return await verify_urs_approved(conn, "TEST-A2-URS-DRAFT")
            finally:
                await tr.rollback()

    result = asyncio.run(_run())
    assert result["passed"] is False
    assert result["record"]["id"] == "TEST-DOC-URS-DRAFT"
    assert result["record"]["status"] == "DRAFT"


# ---------------------------------------------------------------------------
# verify_test_traceability
# ---------------------------------------------------------------------------


def test_verify_test_traceability_fails_naming_urs_042_draft_test_case():
    async def _run():
        pool = await get_pool()
        return await verify_test_traceability(pool, GXP_SYSTEM)

    result = asyncio.run(_run())
    assert result["passed"] is False
    assert result["record"]["id"] == "URS-042"
    assert result["record"]["test_case_id"] == "TC-2026-042"
    assert result["record"]["test_case_status"] == "DRAFT"


def test_verify_test_traceability_passes_when_every_requirement_resolves_non_draft():
    async def _run():
        pool = await get_pool()
        async with pool.acquire() as conn:
            tr = conn.transaction()
            await tr.start()
            try:
                await conn.execute(
                    "INSERT INTO gxp_systems (id, name, system_owner, lifecycle_state) "
                    "VALUES ($1, $2, $3, $4)",
                    "TEST-A2-TRC-PASS", "Test Traceability-Pass System", "Test Owner", "OPERATIONAL",
                )
                await conn.execute(
                    "INSERT INTO test_cases (id, system_id, status) VALUES ($1, $2, $3)",
                    "TEST-TC-PASS", "TEST-A2-TRC-PASS", "EXECUTED",
                )
                await conn.execute(
                    "INSERT INTO requirements (id, system_id, req_text, test_case_id) "
                    "VALUES ($1, $2, $3, $4)",
                    "TEST-REQ-PASS", "TEST-A2-TRC-PASS", "Test requirement text", "TEST-TC-PASS",
                )
                return await verify_test_traceability(conn, "TEST-A2-TRC-PASS")
            finally:
                await tr.rollback()

    result = asyncio.run(_run())
    assert result["passed"] is True
    assert result["record"] is None


# ---------------------------------------------------------------------------
# run_a2 — assembly, conventions, and the narration-cannot-alter-result proof
# ---------------------------------------------------------------------------


def test_run_a2_emits_exactly_two_findings_for_seeded_system(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")

    async def _run():
        with respx.mock:
            respx.post(GEMINI_ENDPOINT).mock(
                return_value=httpx.Response(200, json=GEMINI_SUCCESS_BODY)
            )
            return await run_a2({"system_id": GXP_SYSTEM})

    result = asyncio.run(_run())
    findings = result["findings"]
    assert len(findings) == 2

    rule_ids = {f["regulatory_citations"][0] for f in findings}
    assert rule_ids == {"ANNEX11-S11-PE-001", "ANNEX11-S4-TRC-001"}
    # The now-passing URS check must not produce a finding.
    assert "ANNEX11-S4-DOC-001" not in rule_ids


def test_run_a2_findings_conform_to_phase3_agentfinding_conventions(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")

    async def _run():
        with respx.mock:
            respx.post(GEMINI_ENDPOINT).mock(
                return_value=httpx.Response(200, json=GEMINI_SUCCESS_BODY)
            )
            return await run_a2({"system_id": GXP_SYSTEM})

    result = asyncio.run(_run())
    findings = result["findings"]
    assert len(findings) == 2

    alcoa_fields = {
        "attributable", "legible", "contemporaneous", "original", "accurate",
        "complete", "consistent", "enduring", "available",
    }
    for finding in findings:
        assert finding["confidence_score"] == "UNVERIFIED"
        assert len(finding["regulatory_citations"]) == 1
        assert len(finding["evidence_ids"]) == 1
        assert finding["evidence_ids"][0] in finding["finding_id"]
        assert set(finding["alcoa_score"].keys()) == alcoa_fields
        assert finding["model_attribution"]  # non-empty


def test_build_finding_with_null_record_has_empty_evidence_and_marks_no_record():
    check_result = {
        "check": "verify_urs_approved",
        "rule_id": "ANNEX11-S4-DOC-001",
        "passed": False,
        "record": None,
    }
    finding = build_finding(check_result, "claim text", "deterministic-fallback")
    assert finding["evidence_ids"] == []
    assert finding["finding_id"] == "A2-ANNEX11-S4-DOC-001-NO-RECORD"


def test_run_a2_narration_mocked_vs_degraded_same_two_checks_fail(monkeypatch):
    # Mocked-provider run: claim equals the mocked candidate text, model
    # attribution is the real Gemini model id.
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")

    async def _run_mocked():
        with respx.mock:
            respx.post(GEMINI_ENDPOINT).mock(
                return_value=httpx.Response(200, json=GEMINI_SUCCESS_BODY)
            )
            return await run_a2({"system_id": GXP_SYSTEM})

    mocked_result = asyncio.run(_run_mocked())
    mocked_findings = mocked_result["findings"]
    expected_claim = GEMINI_SUCCESS_BODY["candidates"][0]["content"]["parts"][0]["text"]
    for finding in mocked_findings:
        assert finding["claim"] == expected_claim
        assert finding["model_attribution"] == "gemini-2.5-flash"
    mocked_rule_ids = {f["regulatory_citations"][0] for f in mocked_findings}

    # Degraded run: no provider key anywhere — claim is the deterministic
    # template, attribution records the fallback.
    _no_provider_keys(monkeypatch)

    async def _run_degraded():
        with respx.mock:
            # No routes registered — an accidental outbound call fails loudly.
            return await run_a2({"system_id": GXP_SYSTEM})

    degraded_result = asyncio.run(_run_degraded())
    degraded_findings = degraded_result["findings"]
    for finding in degraded_findings:
        assert finding["model_attribution"] == "deterministic-fallback"
        assert finding["claim"]  # non-empty template sentence
    degraded_rule_ids = {f["regulatory_citations"][0] for f in degraded_findings}

    # Narration cannot alter which checks failed: identical rule-id sets.
    assert mocked_rule_ids == degraded_rule_ids == {"ANNEX11-S11-PE-001", "ANNEX11-S4-TRC-001"}


def test_run_a2_postgres_unreachable_returns_bible_failure_behavior(monkeypatch, reset_db_pool):
    monkeypatch.setattr(
        db, "DATABASE_URL", "postgresql://sentinel:sentinel@127.0.0.1:1/sentinel"
    )

    async def _run():
        return await run_a2({"system_id": GXP_SYSTEM})

    result = asyncio.run(_run())  # must not raise
    findings = result["findings"]
    assert len(findings) == 1
    assert findings[0]["finding_id"] == "ERR-A2"
    assert findings[0]["claim"] == "Traceability verification failed."
    assert findings[0]["confidence_score"] == "LOW"


def test_a2_checks_tuple_matches_bible_order():
    names = [fn.__name__ for fn in A2_CHECKS]
    assert names == [
        "verify_urs_approved",
        "verify_periodic_eval_current",
        "verify_test_traceability",
    ]
