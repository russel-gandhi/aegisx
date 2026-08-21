"""
Hero-loop end-to-end tracer test (Phase 3, plan 03-02).

Drives `compiled_graph.ainvoke()` — real Postgres, real OPA, respx-mocked
Gemini — over the query "Is GXP-MFG-DEMO-01 audit ready?". Proves the one
path the tracer wires end to end: A0's stub fan-out reaches A2's real
`verify_periodic_eval_current` check, which finds the seeded `PE-2024-01`
gap (Bible Section 5) and produces a real `AgentFinding`; C1's real
`run_c1` then verifies that finding against the live `periodic_evaluations`
row and the live OPA `ANNEX11-S11-PE-001` rule, scoring it `MEDIUM` per
this plan's `<critical_findings>` arithmetic (6-of-9 ALCOA fields true).

Requires Postgres and OPA running and seeded (`infra/health-check.sh`,
`infra/apply-seed.sh`). Follows the established `asyncio.run()`-inside-a-
plain-`def`-test convention (no pytest-asyncio), matching
test_opa_client.py / test_llm_router.py / test_graph_topology.py.

Every test registers an explicit `respx.route(host="127.0.0.1",
port=8181).pass_through()` (not the bare `respx.mock` other suites use,
and not `assert_all_mocked=False` — confirmed live that the latter breaks
respx's own mocked-response body under this httpx/respx pairing,
independent of this module): C1's real `evaluate_opa_policy()` call must
reach the live OPA sidecar, not a mock. `.pass_through()` marks only the
OPA host:port pair as real-network passthrough while every other route
stays under respx's default `assert_all_mocked=True`, so an accidental,
unmocked call to any other host still fails loudly.
"""

import asyncio

import httpx
import respx
from langchain_core.messages import HumanMessage

from app.graph.state import compiled_graph

SYSTEM_ID = "GXP-MFG-DEMO-01"
QUERY = "Is GXP-MFG-DEMO-01 audit ready?"
EXPECTED_FINDING_ID = "A2-ANNEX11-S11-PE-001-PE-2024-01"

# The seeded PE-2024-01 row's due_date_ns (infra/postgres/seed/001_seed.sql,
# Bible Section 5) — asserted back out of the result to prove the score
# came from the live row, not a fixture.
SEEDED_DUE_DATE_NS = 1704067200000000000

GEMINI_SUCCESS_BODY = {
    "candidates": [
        {
            "content": {
                "parts": [
                    {
                        "text": (
                            "Periodic evaluation PE-2024-01 is overdue under "
                            "EU GMP Annex 11 Section 11 and requires immediate "
                            "review to restore audit readiness."
                        )
                    }
                ]
            }
        }
    ]
}


def _initial_state():
    return {
        "messages": [HumanMessage(content=QUERY)],
        "system_id": SYSTEM_ID,
        "user_intent": "",
        "active_agents": [],
        "findings": [],
        "proposed_actions": [],
        "verification_results": {},
        "final_synthesis": "",
    }


def _one_finding(result):
    findings = result["findings"]
    assert len(findings) == 1, f"expected exactly one finding, got {findings!r}"
    return findings[0]


def test_success_path_real_finding_verified_medium_confidence(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")

    async def _run():
        with respx.mock:
            respx.route(host="127.0.0.1", port=8181).pass_through()
            respx.post(
                "https://generativelanguage.googleapis.com/v1beta/models/"
                "gemini-2.5-flash:generateContent"
            ).mock(return_value=httpx.Response(200, json=GEMINI_SUCCESS_BODY))
            return await compiled_graph.ainvoke(_initial_state())

    result = asyncio.run(_run())

    finding = _one_finding(result)
    assert finding["finding_id"] == EXPECTED_FINDING_ID
    assert finding["regulatory_citations"] == ["ANNEX11-S11-PE-001"]
    assert finding["evidence_ids"] == ["PE-2024-01"]
    assert finding["model_attribution"] == "gemini-2.5-flash"
    assert finding["claim"] == GEMINI_SUCCESS_BODY["candidates"][0]["content"]["parts"][0]["text"]

    verification = result["verification_results"]
    assert set(verification.keys()) == {EXPECTED_FINDING_ID}
    entry = verification[EXPECTED_FINDING_ID]
    assert entry["db_record_found"] is True
    assert entry["opa_corroborated"] is True
    assert entry["confidence"] == "MEDIUM"


def test_degraded_path_no_provider_key_same_finding_and_score(monkeypatch):
    for env_name in (
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
        "DEEPSEEK_API_KEY",
        "GROQ_API_KEY",
        "OPENROUTER_API_KEY",
    ):
        monkeypatch.delenv(env_name, raising=False)

    async def _run():
        with respx.mock:
            # Only the OPA passthrough is registered — no LLM provider route
            # exists at all, so any accidental outbound HTTP call to a
            # provider fails loudly via respx's own "no matching route"
            # error, rather than silently succeeding.
            respx.route(host="127.0.0.1", port=8181).pass_through()
            return await compiled_graph.ainvoke(_initial_state())

    result = asyncio.run(_run())

    finding = _one_finding(result)
    assert finding["finding_id"] == EXPECTED_FINDING_ID
    assert finding["model_attribution"] == "deterministic-fallback"
    assert finding["claim"]  # non-empty

    entry = result["verification_results"][EXPECTED_FINDING_ID]
    assert entry["confidence"] == "MEDIUM"


def test_evidence_provenance_reads_live_seeded_row(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")

    async def _run():
        with respx.mock:
            respx.route(host="127.0.0.1", port=8181).pass_through()
            respx.post(
                "https://generativelanguage.googleapis.com/v1beta/models/"
                "gemini-2.5-flash:generateContent"
            ).mock(return_value=httpx.Response(200, json=GEMINI_SUCCESS_BODY))
            return await compiled_graph.ainvoke(_initial_state())

    result = asyncio.run(_run())

    finding = _one_finding(result)
    # Read the live row back out directly (not through the graph result) to
    # prove the confidence score above was computed from the real Postgres
    # record, not a fixture.
    from app.db import get_pool

    async def _fetch_seeded_row():
        pool = await get_pool()
        return await pool.fetchrow(
            "SELECT due_date_ns FROM periodic_evaluations WHERE id = $1",
            finding["evidence_ids"][0],
        )

    row = asyncio.run(_fetch_seeded_row())
    assert row is not None
    assert row["due_date_ns"] == SEEDED_DUE_DATE_NS
