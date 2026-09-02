"""
Hero-loop end-to-end tracer test (Phase 3, plan 03-02; updated 03-04 when
A2 grew from one deterministic check to all three the Bible names; updated
03-05 when the traceability finding's corroboration defect was fixed).

Drives `compiled_graph.ainvoke()` — real Postgres, real OPA, respx-mocked
Gemini — over the query "Is GXP-MFG-DEMO-01 audit ready?". Proves the path
the tracer wires end to end: A0 (real classifier since 03-03, falling back
to the full `["A1".."A6"]` set here — see the Deviation note below) fans
out to A2's real checks, which against the seeded state (plus 03-04's
additive `DOC-2026-URS-01` APPROVED URS fixture, D-05) now fail exactly
two of the three Bible-named checks — `verify_periodic_eval_current`
(seeded `PE-2024-01` gap) and `verify_test_traceability` (seeded
`URS-042` / `TC-2026-042` DRAFT gap) — and produce two real
`AgentFinding`s; `verify_urs_approved` now passes and emits none. C1's
real `run_c1` then verifies both findings against live Postgres + live
OPA. Both findings score `MEDIUM`: 6-of-9 ALCOA fields true, real DB
record, real OPA corroboration (`ANNEX11-S11-PE-001` for the
periodic-evaluation finding, `ANNEX11-S4-TRC-001` for the traceability
finding) — `100 - (9 - 6) * 10 = 70`, which falls in `score >= 50`.

Until plan 03-05, the traceability finding scored `INSUFFICIENT_EVIDENCE`
instead, from a pre-existing defect in `c1_verifier.py`'s
`build_opa_payload()` (03-02, discovered in 03-04, out of 03-04's Rule 10
file boundary to fix): for a multi-input-key rule like
`ANNEX11-S4-TRC-001`, it queried the `test_cases` table using the
finding's own `evidence_ids` (`["URS-042"]`, a *requirement* id) instead
of the linked `test_case_id` (`"TC-2026-042"`) rule 5's own input shape
requires, so the OPA payload's `test_cases` object was always empty for
this rule and no violation was ever emitted regardless of how correct
A2's own DRAFT detection was. Plan 03-05 fixed `build_opa_payload()` (a
data-driven foreign-key resolution, `RULE_OPA_INPUT`'s new `id_source`
element — see `c1_verifier.py`'s module docstring) and closed
`.planning/WINDOWS.md` id 1; the assertions below were updated to the
correct, now-observed behavior. See `03-05-SUMMARY.md`.

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
finding" / "exactly two findings" assertions did not anticipate.
`_finding_by_id()` below now locates a finding by id among the full set
(dropping any assertion on the total finding count) rather than asserting
the set has exactly one or two members; every original assertion about
A2's own findings and their C1 verification results is unchanged.
"""

import asyncio

import httpx
import respx
from langchain_core.messages import HumanMessage

from app.graph.state import compiled_graph

SYSTEM_ID = "GXP-MFG-DEMO-01"
QUERY = "Is GXP-MFG-DEMO-01 audit ready?"
EXPECTED_FINDING_ID = "A2-ANNEX11-S11-PE-001-PE-2024-01"
# Added 03-04 when A2 grew to all three Bible-named checks: the
# traceability gap seeded by URS-042 -> TC-2026-042 (DRAFT).
EXPECTED_TRC_FINDING_ID = "A2-ANNEX11-S4-TRC-001-URS-042"

# The seeded PE-2024-01 row's due_date_ns (infra/postgres/seed/001_seed.sql,
# Bible Section 5) — asserted back out of the result to prove the score
# came from the live row, not a fixture.
SEEDED_DUE_DATE_NS = 1704067200000000000

_NARRATION_PROSE = (
    "Periodic evaluation PE-2024-01 is overdue under "
    "EU GMP Annex 11 Section 11 and requires immediate "
    "review to restore audit readiness."
)

# 2026-09-01: A0's classification now goes to the local Ollama entry, not
# Gemini (see llm_router.py's own PROVIDER_CONFIG comment for why). Mocked
# with the same prose as before, which deliberately fails
# classify_intent()'s strict JSON parse and falls back to the full agent
# set — see module docstring's Deviation note. Narration still routes to
# Groq (quick task 260826-p1q), so both mocks must be present alongside
# each other, not one replacing the other.
OLLAMA_SUCCESS_BODY = {
    "choices": [{"message": {"content": _NARRATION_PROSE}}],
    "model": "qwen2.5:7b-instruct",
}

GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"
GROQ_SUCCESS_BODY = {
    "choices": [
        {
            "message": {
                "content": (
                    "Periodic evaluation PE-2024-01 is overdue under "
                    "EU GMP Annex 11 Section 11 and requires immediate "
                    "review to restore audit readiness."
                )
            }
        }
    ],
    "model": "openai/gpt-oss-120b",
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
        # Phase 5 plan 05-06: C2 now fails closed on an absent role, so a
        # real graph invocation must carry identity.
        "user_id": "test-user",
        "user_role": "IT System Manager",
    }


def _finding_by_id(result, finding_id):
    """Locates a finding by id among `result["findings"]`. Since 03-03
    Task 2, A1/A3-A6 are also real and find their own gaps against this
    same live seeded Postgres (see module docstring's Deviation note), and
    since 03-04 A2 itself emits two findings (periodic-eval + traceability)
    rather than one — so this helper asserts nothing about the total
    finding count, only that exactly one finding with `finding_id` exists."""
    findings = result["findings"]
    matches = [f for f in findings if f["finding_id"] == finding_id]
    assert len(matches) == 1, (
        f"expected exactly one finding with id {finding_id!r} among "
        f"{len(findings)} total, got {findings!r}"
    )
    return matches[0]


def test_success_path_real_finding_verified_medium_confidence(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-groq-key")

    async def _run():
        with respx.mock:
            respx.route(host="127.0.0.1", port=8181).pass_through()
            # orchestrator/compliance/knowledge/change/rerank/risk_assessment
            # all resolve to the local Ollama entry now (needs no key).
            respx.post("http://127.0.0.1:11434/v1/chat/completions").mock(
                return_value=httpx.Response(200, json=OLLAMA_SUCCESS_BODY)
            )
            respx.post("http://127.0.0.1:11434/api/embed").mock(
                return_value=httpx.Response(
                    200, json={"model": "nomic-embed-text", "embeddings": [[0.1] * 768]}
                )
            )
            respx.post(GROQ_ENDPOINT).mock(
                return_value=httpx.Response(200, json=GROQ_SUCCESS_BODY)
            )
            return await compiled_graph.ainvoke(_initial_state())

    result = asyncio.run(_run())

    finding = _finding_by_id(result, EXPECTED_FINDING_ID)
    assert finding["regulatory_citations"] == ["ANNEX11-S11-PE-001"]
    assert finding["evidence_ids"] == ["PE-2024-01"]
    assert finding["model_attribution"] == "openai/gpt-oss-120b"
    assert finding["claim"] == GROQ_SUCCESS_BODY["choices"][0]["message"]["content"]

    trc_finding = _finding_by_id(result, EXPECTED_TRC_FINDING_ID)
    assert trc_finding["regulatory_citations"] == ["ANNEX11-S4-TRC-001"]
    assert trc_finding["evidence_ids"] == ["URS-042"]

    verification = result["verification_results"]
    # See module docstring's Deviation note: A1/A3-A6 also fire for real
    # against this same live seeded Postgres since 03-03 Task 2, so this
    # asserts both of A2's own entries are present rather than that they
    # are the only ones.
    assert {EXPECTED_FINDING_ID, EXPECTED_TRC_FINDING_ID} <= set(verification.keys())
    entry = verification[EXPECTED_FINDING_ID]
    assert entry["db_record_found"] is True
    assert entry["opa_corroborated"] is True
    assert entry["confidence"] == "MEDIUM"

    # Plan 03-05 fixed build_opa_payload()'s multi-input-key resolution
    # (see module docstring): rule 5's test_cases input is now correctly
    # keyed by the requirement's linked test_case_id, so this finding now
    # corroborates and scores MEDIUM, exactly as 03-04-PLAN.md's
    # <critical_findings> originally predicted.
    trc_entry = verification[EXPECTED_TRC_FINDING_ID]
    assert trc_entry["db_record_found"] is True
    assert trc_entry["opa_corroborated"] is True
    assert trc_entry["confidence"] == "MEDIUM"


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
            # Groq/OpenRouter fail on their own missing keys, zero HTTP
            # attempted. Ollama needs no key at all, so it's genuinely
            # reached for both narration/classification and A1's embedding
            # call -- mocked unreachable (the realistic local-provider
            # failure mode) so the whole pipeline still degrades cleanly.
            respx.post("http://127.0.0.1:11434/v1/chat/completions").mock(
                side_effect=httpx.ConnectError("connection refused")
            )
            respx.post("http://127.0.0.1:11434/api/embed").mock(
                side_effect=httpx.ConnectError("connection refused")
            )
            respx.route(host="127.0.0.1", port=8181).pass_through()
            return await compiled_graph.ainvoke(_initial_state())

    result = asyncio.run(_run())

    finding = _finding_by_id(result, EXPECTED_FINDING_ID)
    assert finding["model_attribution"] == "deterministic-fallback"
    assert finding["claim"]  # non-empty

    trc_finding = _finding_by_id(result, EXPECTED_TRC_FINDING_ID)
    assert trc_finding["model_attribution"] == "deterministic-fallback"
    assert trc_finding["claim"]  # non-empty

    entry = result["verification_results"][EXPECTED_FINDING_ID]
    assert entry["confidence"] == "MEDIUM"
    # See test_success_path's comment: plan 03-05 fixed build_opa_payload(),
    # so this now corroborates and scores MEDIUM in the degraded path too —
    # narration provider degradation is orthogonal to C1's own verification.
    trc_entry = result["verification_results"][EXPECTED_TRC_FINDING_ID]
    assert trc_entry["confidence"] == "MEDIUM"


def test_evidence_provenance_reads_live_seeded_row(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-groq-key")

    async def _run():
        with respx.mock:
            respx.route(host="127.0.0.1", port=8181).pass_through()
            respx.post("http://127.0.0.1:11434/v1/chat/completions").mock(
                return_value=httpx.Response(200, json=OLLAMA_SUCCESS_BODY)
            )
            respx.post("http://127.0.0.1:11434/api/embed").mock(
                return_value=httpx.Response(
                    200, json={"model": "nomic-embed-text", "embeddings": [[0.1] * 768]}
                )
            )
            respx.post(GROQ_ENDPOINT).mock(
                return_value=httpx.Response(200, json=GROQ_SUCCESS_BODY)
            )
            return await compiled_graph.ainvoke(_initial_state())

    result = asyncio.run(_run())

    finding = _finding_by_id(result, EXPECTED_FINDING_ID)
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
