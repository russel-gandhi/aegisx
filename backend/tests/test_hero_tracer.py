"""
Hero-loop end-to-end tracer test (Phase 3, plan 03-02).

Drives `compiled_graph.ainvoke()` — real Postgres, real OPA, respx-mocked
Gemini — over the query "Is GXP-MFG-DEMO-01 audit ready?". Proves the one
path the tracer wires end to end: A0's fan-out reaches A2's real
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

Deviation (plan 03-03): A0 became a real classifier in 03-03 Task 1, and
this module's single mocked Gemini response is prose, not the strict JSON
`classify_intent()` requires — so A0 correctly falls back to the full
`["A1".."A6"]` set here (proven independently in
`test_a0_orchestrator.py`), same as when A0 was still a stub. 03-03 Task 2
then made A1/A3-A6 genuinely real, and against this same live seeded
Postgres their deterministic checks find their own real gaps (RSK-2024-11,
CR-2026-089/CA-2026-089-1, INC-849201, AR-2026-05, ACC-2026-99) —
producing additional findings this tracer's original "exactly one
finding" assertions did not anticipate. `_one_finding()` below now
locates A2's finding by id among the full set rather than asserting the
set has exactly one member; every original assertion about A2's own
finding and its C1 verification result is unchanged.
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
    """Locates A2's finding by id among `result["findings"]`. Since
    03-03 Task 2, A1/A3-A6 are also real and find their own gaps against
    this same live seeded Postgres (see module docstring's Deviation
    note) — this helper's job is exclusively to hand back the one finding
    this suite's assertions were written about, not to assert anything
    about how many other agents also fired."""
    findings = result["findings"]
    matches = [f for f in findings if f["finding_id"] == EXPECTED_FINDING_ID]
    assert len(matches) == 1, (
        f"expected exactly one {EXPECTED_FINDING_ID} finding among "
        f"{len(findings)} total, got {findings!r}"
    )
    return matches[0]


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
    # See module docstring's Deviation note: A1/A3-A6 also fire for real
    # against this same live seeded Postgres since 03-03 Task 2, so this
    # asserts A2's own entry is present rather than that it is the only one.
    assert EXPECTED_FINDING_ID in verification
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
