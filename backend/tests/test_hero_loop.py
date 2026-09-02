"""
Hero-loop end-to-end integration test — the Phase 3 gate (plan 03-06,
EVID-04, ROADMAP.md Phase 3 success criterion 5, T-03-29/30/31/32).

Ticket: SENT-2-12 (hero loop = product thesis) | Requirement: EVID-04

One invocation of the compiled `StateGraph` on the literal hero query
("Is GXP-MFG-DEMO-01 audit ready?") against live Postgres and the live OPA
sidecar, driving A0 -> A2 -> C1 (plus, in the fully-mocked scenario, the
five other real specialists A0's classification names) and producing a
verified finding sourced entirely from real state — with the LLM provider
the only mocked layer (EVID-01, D-04). A second invocation against the
healthy `BUS-IT-DEMO-02` system proves the loop discriminates rather than
always verifying (T-03-29). A third invocation with every provider key
removed proves the loop still closes end to end via A0/A2's degraded-mode
fallback paths, because C1 makes no model call at all (D-01).

This module is the phase's reviewable EVID-04 evidence
(`pytest tests/test_hero_loop.py -k hero -q`); it does not replace
`test_hero_tracer.py` (03-02/03-04/03-05's narrower single-check tracer),
which stays in place as its own regression suite.

Requires Postgres and OPA running and both seed scripts applied
(`infra/health-check.sh`, `infra/apply-seed.sh`). Follows the established
`asyncio.run()`-inside-a-plain-`def`-test convention (no pytest-asyncio),
matching test_hero_tracer.py / test_a0_orchestrator.py /
test_minimal_specialists.py.

Provider mock routing (03-06-PLAN.md <critical_findings>): A0's
classification call (task="orchestrator" -> `gemini_flash_thinking`) and
A2/A4's narration calls (task="compliance"/"change" -> `gemini_flash_fast`)
all resolve to the *same* Gemini `generateContent` URL — both
`PROVIDER_CONFIG` entries share `model="gemini-3.6-flash"` and the same
`base_url`. A single fixed respx response would feed A0's classification
JSON into A2's narration prompt (or vice versa) and the fully-mocked
scenario would assert nothing meaningful. `_gemini_side_effect` below
resolves this by inspecting the outgoing request body: a `systemInstruction`
naming `A0_SYSTEM_PROMPT`'s own marker text gets the classification JSON;
every other Gemini call gets a narration sentence. DeepSeek (A3), Groq
(A5/A6), and OpenRouter (the router's own fallback cascade) are mocked too
in the fully-mocked scenario, so it exercises every specialist's primary
provider directly rather than silently falling through to
`deterministic-fallback` for lack of a matching route.

Every test registers an explicit `respx.route(host="127.0.0.1",
port=8181).pass_through()` (mirrors test_hero_tracer.py's own convention
and rationale): C1's real `evaluate_opa_policy()` call must reach the live
OPA sidecar, not a mock. Neither Postgres nor OPA is mocked anywhere in
this module — `app.db.DATABASE_URL` and `app.opa_client.OPA_URL` are never
monkeypatched here.

A real GEMINI/DEEPSEEK/GROQ/OPENROUTER API key may already be present in
this repo's root `.env` (D-01 follow-up, same situation
test_minimal_specialists.py's own docstring documents). This does not
create a live-network risk under `respx.mock`'s default
`assert_all_mocked=True`: every outbound httpx call inside the `with
respx.mock:` block must match a registered route or respx itself raises
`AllMockedAssertionError` — no unmocked request ever reaches the real
network, keyed or not.
"""

import asyncio
import json

import httpx
import respx
from langchain_core.messages import HumanMessage

from app.agents.a0_orchestrator import A0_SYSTEM_PROMPT, FULL_AGENT_SET
from app.agents.c1_verifier import run_c1
from app.db import get_pool
from app.graph.state import compiled_graph

SYSTEM_ID = "GXP-MFG-DEMO-01"
HEALTHY_SYSTEM_ID = "BUS-IT-DEMO-02"
QUERY = "Is GXP-MFG-DEMO-01 audit ready?"

EXPECTED_PE_FINDING_ID = "A2-ANNEX11-S11-PE-001-PE-2024-01"
EXPECTED_TRC_FINDING_ID = "A2-ANNEX11-S4-TRC-001-URS-042"

# The seeded PE-2024-01 row's due_date_ns (infra/postgres/seed/001_seed.sql,
# Bible Section 5) — read back from the live database in the provenance
# test and compared against the literal, proving the confidence score came
# from the real row, not a fixture.
SEEDED_DUE_DATE_NS = 1704067200000000000

FOUR_GRADES = {"HIGH", "MEDIUM", "LOW", "INSUFFICIENT_EVIDENCE"}
REQUIRED_VERIFICATION_KEYS = {
    "confidence", "db_record_found", "opa_corroborated", "opa_rule_ids", "evidence_ids",
}

# 2026-09-01: `gemini_flash_thinking`/`gemini_flash_fast`/`deepseek_r1`
# removed from PROVIDER_CONFIG entirely (see llm_router.py's own comment
# for the live evidence). `ollama_qwen` (local) now covers every task
# those three used to -- orchestrator, synthesis, compliance, knowledge,
# change, rerank, risk_assessment all resolve to it. Only three provider
# entries remain: ollama_qwen, groq_gpt_oss, openrouter_fallback.
OLLAMA_URL = "http://127.0.0.1:11434/v1/chat/completions"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

ALL_PROVIDER_KEYS = (
    "GEMINI_API_KEY", "GOOGLE_API_KEY", "DEEPSEEK_API_KEY", "GROQ_API_KEY", "OPENROUTER_API_KEY",
)


def _initial_state(system_id: str, query: str = QUERY):
    return {
        "messages": [HumanMessage(content=query)],
        "system_id": system_id,
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


def _delete_all_provider_keys(monkeypatch):
    for env_name in ALL_PROVIDER_KEYS:
        monkeypatch.delenv(env_name, raising=False)


def _ollama_side_effect(active_agents_named):
    """Routes A0's classification prompt vs. every other Ollama caller's
    narration/rerank prompt by inspecting the outgoing request body's
    system message content -- the OpenAI-compatible shape Ollama shares
    with Groq/OpenRouter (a `messages` list with an optional
    `role: "system"` entry), not Gemini's old `systemInstruction` field."""

    def _side_effect(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        system_message = next(
            (m["content"] for m in body.get("messages", []) if m.get("role") == "system"), ""
        )
        if A0_SYSTEM_PROMPT[:20] in system_message:
            text = json.dumps(
                {"active_agents": active_agents_named, "intent_category": "audit_readiness"}
            )
        else:
            text = (
                "A deterministic compliance gap was narrated for this "
                "hero-loop test by a mocked Ollama response."
            )
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": text}}], "model": "qwen2.5:7b-instruct"},
        )

    return _side_effect


def _openai_body(text: str, model: str) -> httpx.Response:
    return httpx.Response(200, json={"choices": [{"message": {"content": text}}], "model": model})


def _mock_all_four_providers(active_agents_named):
    """Installs all three remaining provider routes (ollama_qwen,
    groq_gpt_oss, openrouter_fallback -- named `_mock_all_four_providers`
    for historical continuity with earlier call sites, kept rather than
    renamed everywhere purely to limit this diff's blast radius) plus the
    real-OPA passthrough. Nothing else is mocked — the graph, the
    database, and the policy engine stay live (EVID-01, D-04)."""
    respx.post(OLLAMA_URL).mock(side_effect=_ollama_side_effect(active_agents_named))
    respx.post(GROQ_URL).mock(
        return_value=_openai_body(
            "Gap narrated by a mocked Groq response.", "openai/gpt-oss-120b"
        )
    )
    respx.post(OPENROUTER_URL).mock(
        return_value=_openai_body(
            "Fallback narration by a mocked OpenRouter response.", "openrouter/auto"
        )
    )
    respx.route(host="127.0.0.1", port=8181).pass_through()


def _run_full_provider_hero_loop(system_id: str, active_agents_named):
    async def _run():
        with respx.mock:
            _mock_all_four_providers(active_agents_named)
            return await compiled_graph.ainvoke(_initial_state(system_id))

    return asyncio.run(_run())


def _finding_by_id(result, finding_id):
    findings = result["findings"]
    matches = [f for f in findings if f["finding_id"] == finding_id]
    assert len(matches) == 1, (
        f"expected exactly one finding with id {finding_id!r} among "
        f"{len(findings)} total, got {findings!r}"
    )
    return matches[0]


# --- Scenario 1: fully-mocked run against the unhealthy demo system,     --
# --- driving A0 -> A2 -> C1 (plus the four other real specialists)       --


def test_hero_fully_mocked_run_completes_and_routes_to_a2(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-deepseek-key")
    monkeypatch.setenv("GROQ_API_KEY", "test-groq-key")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter-key")

    result = _run_full_provider_hero_loop(SYSTEM_ID, list(FULL_AGENT_SET))

    assert result["active_agents"] == list(FULL_AGENT_SET)
    assert "A2" in result["active_agents"]


def test_hero_fully_mocked_run_produces_periodic_eval_and_traceability_findings(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-deepseek-key")
    monkeypatch.setenv("GROQ_API_KEY", "test-groq-key")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter-key")

    result = _run_full_provider_hero_loop(SYSTEM_ID, list(FULL_AGENT_SET))

    pe_finding = _finding_by_id(result, EXPECTED_PE_FINDING_ID)
    assert pe_finding["evidence_ids"] == ["PE-2024-01"]

    trc_finding = _finding_by_id(result, EXPECTED_TRC_FINDING_ID)
    assert trc_finding["evidence_ids"] == ["URS-042"]


def test_hero_fully_mocked_run_verification_results_shape_and_four_grades(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-deepseek-key")
    monkeypatch.setenv("GROQ_API_KEY", "test-groq-key")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter-key")

    result = _run_full_provider_hero_loop(SYSTEM_ID, list(FULL_AGENT_SET))

    findings = result["findings"]
    verification = result["verification_results"]
    assert findings, "expected at least one finding against the seeded unhealthy system"
    assert len(verification) == len(findings)
    for finding in findings:
        entry = verification[finding["finding_id"]]
        assert REQUIRED_VERIFICATION_KEYS <= set(entry.keys())
        assert entry["confidence"] in FOUR_GRADES


def test_hero_fully_mocked_run_at_least_one_finding_verified_medium_or_better(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-deepseek-key")
    monkeypatch.setenv("GROQ_API_KEY", "test-groq-key")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter-key")

    result = _run_full_provider_hero_loop(SYSTEM_ID, list(FULL_AGENT_SET))

    entry = result["verification_results"][EXPECTED_PE_FINDING_ID]
    assert entry["db_record_found"] is True
    assert entry["opa_corroborated"] is True
    assert entry["confidence"] in {"MEDIUM", "HIGH"}


def test_hero_provenance_periodic_eval_matches_live_seeded_row(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-deepseek-key")
    monkeypatch.setenv("GROQ_API_KEY", "test-groq-key")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter-key")

    result = _run_full_provider_hero_loop(SYSTEM_ID, list(FULL_AGENT_SET))
    finding = _finding_by_id(result, EXPECTED_PE_FINDING_ID)

    async def _fetch_seeded_row():
        pool = await get_pool()
        return await pool.fetchrow(
            "SELECT due_date_ns FROM periodic_evaluations WHERE id = $1",
            finding["evidence_ids"][0],
        )

    row = asyncio.run(_fetch_seeded_row())
    assert row is not None
    assert row["due_date_ns"] == SEEDED_DUE_DATE_NS


def test_hero_fully_mocked_run_model_attribution_names_real_provider(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-deepseek-key")
    monkeypatch.setenv("GROQ_API_KEY", "test-groq-key")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter-key")

    result = _run_full_provider_hero_loop(SYSTEM_ID, list(FULL_AGENT_SET))

    findings = result["findings"]
    assert findings, "expected at least one finding against the seeded unhealthy system"
    for finding in findings:
        assert finding["model_attribution"] != "deterministic-fallback"
        assert finding["model_attribution"]


# --- Scenario 2: discrimination control — the healthy demo system grades --
# --- everything INSUFFICIENT_EVIDENCE (T-03-29)                          --


def test_hero_discrimination_control_healthy_system_grades_insufficient_evidence(monkeypatch):
    _delete_all_provider_keys(monkeypatch)
    # A2's two NO-RECORD checks against BUS-IT-DEMO-02 still narrate via the
    # dedicated "narration" task (routed to Groq, quick task 260826-p1q),
    # independent of A0's classification provider (Ollama, needs no key) —
    # both mocks must be present alongside each other.
    monkeypatch.setenv("GROQ_API_KEY", "test-groq-key")

    async def _run():
        with respx.mock:
            # BUS-IT-DEMO-02 is healthy — the classification only needs to
            # name A2 to exercise the discrimination control.
            respx.post(OLLAMA_URL).mock(side_effect=_ollama_side_effect(["A2"]))
            respx.post(GROQ_URL).mock(
                return_value=_openai_body(
                    "Gap narrated by a mocked Groq response.", "openai/gpt-oss-120b"
                )
            )
            respx.route(host="127.0.0.1", port=8181).pass_through()
            return await compiled_graph.ainvoke(_initial_state(HEALTHY_SYSTEM_ID))

    result = asyncio.run(_run())

    # A2's checks against BUS-IT-DEMO-02: no URS document and no periodic
    # evaluation exist at all, so verify_urs_approved and
    # verify_periodic_eval_current each fail with a NO-RECORD finding
    # (empty evidence_ids); verify_test_traceability passes trivially (no
    # requirements rows to fail). C1 short-circuits both NO-RECORD findings
    # to INSUFFICIENT_EVIDENCE before ever calling OPA (fetch_evidence_record
    # requires a non-empty evidence_ids list).
    findings = result["findings"]
    assert findings, "expected A2 to still emit findings for its no-record checks"
    verification = result["verification_results"]
    for finding in findings:
        entry = verification[finding["finding_id"]]
        assert entry["confidence"] == "INSUFFICIENT_EVIDENCE"
        assert entry["db_record_found"] is False


# --- Scenario 3: keyless run — the loop closes without any provider key --
# --- (D-01): full agent-set fallback, deterministic-fallback narration,  --
# --- and C1's grade unchanged because it makes no model call at all      --


def test_hero_keyless_run_falls_back_to_full_agent_set_and_deterministic_fallback(monkeypatch):
    _delete_all_provider_keys(monkeypatch)

    async def _run():
        with respx.mock:
            # Groq and OpenRouter fail on their own missing keys with zero
            # outbound HTTP attempted, exactly as before. Ollama needs no
            # key at all, so it's genuinely reached -- mocked unreachable
            # here (the realistic local-provider failure mode) so the
            # cascade still exhausts cleanly instead of respx raising on
            # an unmocked live request.
            respx.post(OLLAMA_URL).mock(side_effect=httpx.ConnectError("connection refused"))
            # A1's embedding call (also Ollama, also needs no key) is
            # genuinely reached too -- same treatment.
            respx.post("http://127.0.0.1:11434/api/embed").mock(
                side_effect=httpx.ConnectError("connection refused")
            )
            respx.route(host="127.0.0.1", port=8181).pass_through()
            return await compiled_graph.ainvoke(_initial_state(SYSTEM_ID))

    result = asyncio.run(_run())

    assert result["active_agents"] == list(FULL_AGENT_SET)

    findings = result["findings"]
    assert findings, "expected the full agent set to still find its own real gaps"
    for finding in findings:
        assert finding["model_attribution"] == "deterministic-fallback"

    entry = result["verification_results"][EXPECTED_PE_FINDING_ID]
    assert entry["confidence"] == "MEDIUM"


# --- Scenario 4: no unverified default — C1 never fabricates a verified --
# --- entry, and an empty findings list yields an empty mapping           --


def test_hero_run_c1_with_no_findings_returns_empty_verification_mapping():
    result = asyncio.run(run_c1({"findings": []}))
    assert result == {}
