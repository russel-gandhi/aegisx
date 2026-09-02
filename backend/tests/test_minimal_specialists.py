"""
Tests for `app.agents.minimal_specialists` (Phase 3, plan 03-03).

Covers all ten of Task 2's behaviors against the live seeded Postgres
(infra/postgres/seed/001_seed.sql). Follows the established
`asyncio.run()`-inside-a-plain-`def`-test convention (no pytest-asyncio),
matching test_hero_tracer.py / test_a0_orchestrator.py.

A real OPENROUTER_API_KEY (and DEEPSEEK/GROQ) are configured in this
repo's root `.env` (D-01 follow-up) — every test below explicitly deletes
the provider keys it does not intend to exercise, so an unmocked-but-keyed
request never reaches respx's own "no matching route" error path by
accident (mirrors test_a0_orchestrator.py's same convention).
"""

import asyncio

import httpx
import respx
from langchain_core.messages import HumanMessage

from app import db, schemas
from app.agents import minimal_specialists
from app.agents.c1_verifier import RULE_EVIDENCE_TABLES, RULE_OPA_INPUT
from app.agents.minimal_specialists import (
    SPECIALIST_CONFIG,
    _a1_abstain_finding,
    _is_json_shaped,
    _strip_markdown_code_fence,
    run_a1,
    run_a3,
    run_a4,
    run_a5,
    run_a6,
)
from app.retrieval import hybrid_search
from app.schemas import ALCOAScore

SYSTEM_ID = "GXP-MFG-DEMO-01"
# 2026-09-01: `risk_assessment` (was deepseek_r1) and `orchestrator` (was
# gemini_flash_thinking) both now route to the same local `ollama_qwen`
# entry -- see llm_router.py's own PROVIDER_CONFIG comment for why
# (Gemini/DeepSeek both structurally broken: a confirmed free-tier quota
# and an inactive billing account, not a provisional choice).
OLLAMA_URL = "http://127.0.0.1:11434/v1/chat/completions"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

ALL_PROVIDER_KEYS = (
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "DEEPSEEK_API_KEY",
    "GROQ_API_KEY",
    "OPENROUTER_API_KEY",
)

RUNNERS = {"A1": run_a1, "A3": run_a3, "A4": run_a4, "A5": run_a5, "A6": run_a6}


def test_strip_markdown_code_fence_removes_json_fence():
    fenced = '```json\n{"finding_id": "X", "risk_score": 12}\n```'
    assert _strip_markdown_code_fence(fenced) == '{"finding_id": "X", "risk_score": 12}'


def test_strip_markdown_code_fence_removes_bare_fence():
    fenced = '```\n{"a": 1}\n```'
    assert _strip_markdown_code_fence(fenced) == '{"a": 1}'


def test_strip_markdown_code_fence_leaves_unfenced_text_unchanged():
    assert _strip_markdown_code_fence("plain prose claim.") == "plain prose claim."


def test_is_json_shaped_detects_fenced_json_object():
    # Regression: a model that wraps its JSON echo in a ```json fence
    # must still be caught as JSON-shaped -- previously this text slipped
    # past the guard (it doesn't start with "{"/"[") and the raw fenced
    # blob leaked into the user-facing claim verbatim.
    fenced = (
        '```json\n{\n  "finding_id": "FIND-RSK-2024-11",\n  "risk_score": 12\n}\n```'
    )
    assert _is_json_shaped(fenced) is True


def test_is_json_shaped_false_for_fenced_prose():
    fenced = "```\nnot actually json, just fenced prose.\n```"
    assert _is_json_shaped(fenced) is False


def _state(system_id: str = SYSTEM_ID):
    return {
        "messages": [HumanMessage(content="Is GXP-MFG-DEMO-01 audit ready?")],
        "system_id": system_id,
        "user_intent": "",
        "active_agents": [],
        "findings": [],
        "proposed_actions": [],
        "verification_results": {},
        "final_synthesis": "",
    }


def _delete_all_keys(monkeypatch):
    for env_name in ALL_PROVIDER_KEYS:
        monkeypatch.delenv(env_name, raising=False)


def _openai_body(text: str, model: str):
    return httpx.Response(200, json={"choices": [{"message": {"content": text}}], "model": model})


def test_all_five_return_findings_list_and_none_are_unconditionally_empty(monkeypatch):
    _delete_all_keys(monkeypatch)

    async def _run():
        with respx.mock:
            results = {}
            for agent_id, runner in RUNNERS.items():
                results[agent_id] = await runner(_state())
            return results

    results = asyncio.run(_run())
    for agent_id, result in results.items():
        assert isinstance(result["findings"], list), agent_id

    # Real seeded gaps exist for A3 (RSK-2024-11), A4 (CR-2026-089), A5
    # (INC-849201), A6 (AR-2026-05 + ACC-2026-99) — each must produce at
    # least one finding against the live seeded DB.
    for agent_id in ("A3", "A4", "A5", "A6"):
        assert len(results[agent_id]["findings"]) >= 1, agent_id


def test_every_finding_validates_against_phase3_conventions(monkeypatch):
    _delete_all_keys(monkeypatch)
    rego_rule_ids = set(RULE_EVIDENCE_TABLES)

    async def _run():
        with respx.mock:
            results = {}
            for agent_id, runner in RUNNERS.items():
                results[agent_id] = await runner(_state())
            return results

    results = asyncio.run(_run())
    for agent_id, result in results.items():
        for finding in result["findings"]:
            assert finding["claim"], f"{agent_id} finding has empty claim"
            assert set(finding["regulatory_citations"]) <= rego_rule_ids, agent_id
            assert finding["model_attribution"], agent_id
            # ALCOAScore's 9 fields (A1's Bible-literal fallback uses {}
            # deliberately — see minimal_specialists._a1_abstain_finding).
            if finding["finding_id"] != "ERR-A1":
                assert len(finding["alcoa_score"]) == 9, agent_id
            if finding["finding_id"] not in ("ERR-A1",) and not finding["finding_id"].startswith("ERR-"):
                assert finding["evidence_ids"], agent_id


def test_every_rule_id_specialist_emits_is_key_in_c1_frozen_maps():
    assert sorted(SPECIALIST_CONFIG) == ["A1", "A3", "A4", "A5", "A6"]
    rule_ids = {
        rid
        for cfg in SPECIALIST_CONFIG.values()
        for rid in ([cfg["rule_id"]] if isinstance(cfg["rule_id"], str) else cfg["rule_id"])
    }
    assert rule_ids <= set(RULE_EVIDENCE_TABLES)
    assert rule_ids <= set(RULE_OPA_INPUT)


def test_a1_absent_system_returns_err_a1_abstain_finding(monkeypatch):
    _delete_all_keys(monkeypatch)

    async def _run():
        with respx.mock:
            return await run_a1(_state(system_id="NO-SUCH-SYSTEM"))

    result = asyncio.run(_run())
    assert len(result["findings"]) == 1
    finding = result["findings"][0]
    assert finding["finding_id"] == "ERR-A1"
    assert finding["claim"] == "Unable to verify documentation inventory due to retrieval timeout."
    assert finding["confidence_score"] == "LOW"
    assert finding["regulatory_citations"] == []
    assert finding["evidence_ids"] == []
    assert finding["alcoa_score"] == {}
    assert finding["model_attribution"] == "gemini-2.5-flash"


def test_a1_abstain_finding_round_trips_through_agent_finding_schema():
    """`AgentFinding`'s seven-field shape (`app.schemas`) is unchanged by
    this plan -- `_a1_abstain_finding()` still constructs a valid instance,
    proving no field was added to accommodate retrieval provenance (Task 1
    <action> item 3: the provenance rides the sibling
    `retrieval_evidence` key, not `AgentFinding`)."""
    finding = schemas.AgentFinding(**_a1_abstain_finding())
    assert finding.finding_id == "ERR-A1"
    assert finding.alcoa_score.model_dump() == ALCOAScore().model_dump()


def test_run_a1_real_retrieval_success_returns_empty_findings_and_populates_evidence(monkeypatch):
    """Phase 06.1 plan 06.1-02 (D-06): a successful retrieval contributes
    no `findings` entry of its own -- A1 asserts no compliance gap;
    `retrieval_evidence`/`retrieval_trace` carry the real
    `hybrid_retrieve()` outcome instead."""
    fake_outcome = hybrid_search.RetrievalOutcome(
        evidence=[{"evidence_id": "EV-abcd1234", "chunk_id": "abcd1234-0000-0000-0000-000000000000"}],
        trace=[{"stage_id": "evaluating", "label": "Evaluating evidence", "status": "complete", "detail": "1 of 1"}],
        insufficient_evidence=False,
        model_attribution="gemini-embedding-001",
    )

    async def _fake_hybrid_retrieve(pool, query, system_id):
        assert system_id == SYSTEM_ID
        assert query == "Is GXP-MFG-DEMO-01 audit ready?"
        return fake_outcome

    monkeypatch.setattr(minimal_specialists, "hybrid_retrieve", _fake_hybrid_retrieve)

    result = asyncio.run(run_a1(_state()))
    assert result["findings"] == []
    assert result["retrieval_evidence"] == fake_outcome.evidence
    assert result["retrieval_trace"] == fake_outcome.trace


def test_run_a1_degrades_to_abstain_when_pool_unavailable(monkeypatch):
    async def _no_pool():
        return None

    monkeypatch.setattr(minimal_specialists, "acquire_pool_or_none", _no_pool)

    result = asyncio.run(run_a1(_state()))
    assert result["findings"] == [_a1_abstain_finding()]
    assert result["retrieval_evidence"] == []
    assert result["retrieval_trace"] == []


def test_run_a1_degrades_to_abstain_when_retrieval_raises_unexpectedly(monkeypatch):
    """`hybrid_retrieve` itself never raises (its own module contract),
    but `run_a1`'s own defensive guard (mirrors `_safe_call_llm`) still
    degrades cleanly if it ever did, rather than crashing the concurrent
    A1-A6 fan-out."""

    async def _raising_hybrid_retrieve(pool, query, system_id):
        raise RuntimeError("unexpected failure deep in the retrieval stack")

    monkeypatch.setattr(minimal_specialists, "hybrid_retrieve", _raising_hybrid_retrieve)

    result = asyncio.run(run_a1(_state()))
    assert result["findings"] == [_a1_abstain_finding()]
    assert result["retrieval_evidence"] == []
    assert result["retrieval_trace"] == []


def test_a3_ollama_timeout_cascades_to_groq_and_narrates(monkeypatch):
    """A3's own docstring-level "downgrade to gemini_flash_thinking, retry
    once" behavior (`_narrate_a3`'s outer retry via `task="orchestrator"`)
    is now, mechanically, a retry against the SAME provider entry that
    `task="risk_assessment"` already uses -- `ollama_qwen` covers both
    tasks post-2026-09-01 (see this file's own OLLAMA_URL comment). The
    behavior worth proving is therefore one level down: `call_llm`'s own
    internal cascade (ollama_qwen -> groq_gpt_oss -> openrouter_fallback)
    absorbing a timeout on the very first attempt, before `_narrate_a3`'s
    own retry logic is ever needed."""
    monkeypatch.setenv("GROQ_API_KEY", "test-groq-key")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    async def _run():
        with respx.mock:
            respx.post(OLLAMA_URL).mock(side_effect=httpx.TimeoutException("timed out"))
            respx.post(GROQ_URL).mock(
                return_value=httpx.Response(
                    200,
                    json={
                        "choices": [{"message": {"content": "Risk RSK-2024-11 is overdue for review."}}],
                        "model": "openai/gpt-oss-120b",
                    },
                )
            )
            return await run_a3(_state())

    result = asyncio.run(_run())
    findings = [f for f in result["findings"] if f["finding_id"].startswith("A3-")]
    assert len(findings) == 1
    finding = findings[0]
    assert finding["model_attribution"] == "openai/gpt-oss-120b"
    assert finding["claim"] == "Risk RSK-2024-11 is overdue for review."
    assert finding["regulatory_citations"] == ["ICH-Q9-RSK-001"]
    assert finding["evidence_ids"] == ["RSK-2024-11"]


def test_a4_emits_finding_from_direct_change_metadata_only(monkeypatch):
    _delete_all_keys(monkeypatch)

    async def _run():
        with respx.mock:
            return await run_a4(_state())

    result = asyncio.run(_run())
    findings = result["findings"]
    assert len(findings) == 1
    finding = findings[0]
    assert finding["finding_id"] == "A4-ANNEX11-S10-CHG-001-CR-2026-089"
    assert finding["evidence_ids"] == ["CR-2026-089"]
    assert finding["model_attribution"] == "deterministic-fallback"


def test_a5_provider_failure_still_emits_rule_only_overdue_rca_finding(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-groq-key")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    async def _run():
        with respx.mock:
            respx.post(GROQ_URL).mock(return_value=httpx.Response(500, json={"error": "internal"}))
            return await run_a5(_state())

    result = asyncio.run(_run())
    findings = result["findings"]
    assert len(findings) == 1
    finding = findings[0]
    assert finding["finding_id"] == "A5-ANNEX11-S13-INC-001-INC-849201"
    assert finding["model_attribution"] == "deterministic-fallback"
    assert finding["claim"]


def test_a6_429_cascades_to_openrouter_before_abstain(monkeypatch):
    """`FALLBACK_CASCADE` is now (ollama_qwen, groq_gpt_oss,
    openrouter_fallback) -- on Groq's 429, the next untried hop is Ollama
    (local, needs no key), not OpenRouter directly. Mocked unreachable
    here so the cascade proceeds on to OpenRouter, matching this test's
    original "429 -> eventually reaches OpenRouter" intent."""
    monkeypatch.setenv("GROQ_API_KEY", "test-groq-key")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter-key")

    async def _run():
        with respx.mock:
            respx.post(GROQ_URL).mock(return_value=httpx.Response(429, json={"error": "rate limited"}))
            respx.post(OLLAMA_URL).mock(side_effect=httpx.ConnectError("connection refused"))
            openrouter_route = respx.post(OPENROUTER_URL).mock(
                return_value=_openai_body("Access review AR-2026-05 is overdue.", "openrouter/auto")
            )
            result = await run_a6(_state())
            return result, openrouter_route

    result, openrouter_route = asyncio.run(_run())
    assert openrouter_route.called
    review_findings = [f for f in result["findings"] if "ACC-001" in f["finding_id"]]
    assert len(review_findings) == 1
    assert review_findings[0]["model_attribution"] == "openrouter/auto"
    # The orphaned-privileged-account check also finds a real gap
    # (ACC-2026-99) independent of the review-overdue narration above.
    orphan_findings = [f for f in result["findings"] if "ACC-002" in f["finding_id"]]
    assert len(orphan_findings) == 1


def test_all_five_complete_with_no_provider_key_present_and_postgres_reachable(monkeypatch):
    _delete_all_keys(monkeypatch)

    async def _run():
        with respx.mock:
            results = {}
            for agent_id, runner in RUNNERS.items():
                results[agent_id] = await runner(_state())
            return results

    results = asyncio.run(_run())  # must not raise
    for agent_id, result in results.items():
        assert isinstance(result["findings"], list), agent_id
        for finding in result["findings"]:
            assert finding["claim"], agent_id


def test_all_five_return_bible_fallback_with_postgres_unreachable(monkeypatch, reset_db_pool):
    _delete_all_keys(monkeypatch)
    monkeypatch.setattr(db, "DATABASE_URL", "postgresql://sentinel:sentinel@127.0.0.1:1/sentinel")

    async def _run():
        with respx.mock:
            results = {}
            for agent_id, runner in RUNNERS.items():
                results[agent_id] = await runner(_state())
            return results

    results = asyncio.run(_run())  # must not raise
    for agent_id, result in results.items():
        findings = result["findings"]
        assert len(findings) == 1, agent_id
        assert findings[0]["finding_id"] == "ERR-" + agent_id
