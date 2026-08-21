"""
Tests for `app.agents.a0_orchestrator` (Phase 3, plan 03-03, ORC-02).

Every one of A0's nine behaviors reaches either a narrowed
`active_agents` list from a successful mocked classification, or the
identical full-set fallback. Follows the established
`asyncio.run()`-inside-a-plain-`def`-test convention (no pytest-asyncio),
matching test_llm_router.py / test_hero_tracer.py.
"""

import asyncio
import time

import httpx
import respx
from langchain_core.messages import HumanMessage

from app.agents.a0_orchestrator import (
    A0_SYSTEM_PROMPT,
    A0_TIMEOUT_SECONDS,
    FULL_AGENT_SET,
    classify_intent,
    run_a0,
)

GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-2.5-flash:generateContent"
)
SYSTEM_ID = "GXP-MFG-DEMO-01"
QUERY = "Is GXP-MFG-DEMO-01 audit ready?"


def _state(query: str = QUERY, system_id: str = SYSTEM_ID):
    return {
        "messages": [HumanMessage(content=query)],
        "system_id": system_id,
        "user_intent": "",
        "active_agents": [],
        "findings": [],
        "proposed_actions": [],
        "verification_results": {},
        "final_synthesis": "",
    }


def _mock_gemini_json(text: str):
    return respx.post(GEMINI_URL).mock(
        return_value=httpx.Response(
            200, json={"candidates": [{"content": {"parts": [{"text": text}]}}]}
        )
    )


def test_mocked_classification_narrows_active_agents(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")

    async def _run():
        with respx.mock:
            _mock_gemini_json(
                '{"active_agents": ["A1", "A2"], "intent_category": "audit_readiness"}'
            )
            return await run_a0(_state())

    result = asyncio.run(_run())
    assert result["active_agents"] == ["A1", "A2"]
    assert result["user_intent"] == "audit_readiness"


def test_request_targets_gemini_thinking_budget_and_json_mime(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")

    async def _run():
        with respx.mock:
            route = _mock_gemini_json(
                '{"active_agents": ["A2"], "intent_category": "audit_readiness"}'
            )
            await run_a0(_state())
            return route

    route = asyncio.run(_run())
    assert route.called
    import json as _json

    sent = _json.loads(route.calls.last.request.content)
    assert sent["generationConfig"]["thinkingConfig"]["thinkingBudget"] == 512
    assert sent["generationConfig"]["responseMimeType"] == "application/json"


def test_timeout_over_2000ms_falls_back_to_full_set_within_2500ms(monkeypatch):
    async def _slow_classify(user_query, system_id):
        await asyncio.sleep(3.0)
        raise AssertionError("should have been cancelled before completing")

    monkeypatch.setattr("app.agents.a0_orchestrator.classify_intent", _slow_classify)

    async def _run():
        start = time.monotonic()
        result = await run_a0(_state())
        elapsed = time.monotonic() - start
        return result, elapsed

    result, elapsed = asyncio.run(_run())
    assert result["active_agents"] == FULL_AGENT_SET
    assert result["user_intent"] == "unclassified_fallback"
    assert elapsed < 2.5, f"expected cancellation near {A0_TIMEOUT_SECONDS}s, took {elapsed}s"


def test_mocked_read_timeout_produces_full_set_fallback_no_exception(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    # A real OPENROUTER_API_KEY is configured in this repo's root .env
    # (D-01 follow-up) — deleted here so call_llm()'s own cascade-on-timeout
    # hits a clean missing-key degrade instead of attempting a real,
    # unmocked HTTP request to openrouter.ai under respx.mock.
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    async def _run():
        with respx.mock:
            respx.post(GEMINI_URL).mock(side_effect=httpx.TimeoutException("timed out"))
            return await run_a0(_state())

    result = asyncio.run(_run())
    assert result["active_agents"] == FULL_AGENT_SET
    assert result["user_intent"] == "unclassified_fallback"


def test_invalid_json_candidate_text_falls_back(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")

    async def _run():
        with respx.mock:
            _mock_gemini_json("This is not JSON at all.")
            return await run_a0(_state())

    result = asyncio.run(_run())
    assert result["active_agents"] == FULL_AGENT_SET
    assert result["user_intent"] == "unclassified_fallback"


def test_unknown_agent_id_in_classification_falls_back(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")

    async def _run():
        with respx.mock:
            _mock_gemini_json(
                '{"active_agents": ["A1", "A9"], "intent_category": "audit_readiness"}'
            )
            return await run_a0(_state())

    result = asyncio.run(_run())
    assert result["active_agents"] == FULL_AGENT_SET
    assert result["user_intent"] == "unclassified_fallback"


def test_empty_active_agents_list_falls_back(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")

    async def _run():
        with respx.mock:
            _mock_gemini_json('{"active_agents": [], "intent_category": "audit_readiness"}')
            return await run_a0(_state())

    result = asyncio.run(_run())
    assert result["active_agents"] == FULL_AGENT_SET
    assert result["user_intent"] == "unclassified_fallback"


def test_no_provider_key_falls_back_no_outbound_request_no_exception(monkeypatch):
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
            # No routes registered at all: any accidental outbound request
            # raises respx's own "no matching route" error, making a
            # regression here fail loudly rather than silently pass.
            return await run_a0(_state())

    result = asyncio.run(_run())
    assert result["active_agents"] == FULL_AGENT_SET
    assert result["user_intent"] == "unclassified_fallback"


def test_every_fallback_returns_bible_ordered_full_set(monkeypatch):
    for env_name in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "OPENROUTER_API_KEY"):
        monkeypatch.delenv(env_name, raising=False)

    async def _run():
        with respx.mock:
            return await run_a0(_state())

    result = asyncio.run(_run())
    assert result["active_agents"] == ["A1", "A2", "A3", "A4", "A5", "A6"]


def test_classify_intent_directly_raises_valueerror_on_degraded_response(monkeypatch):
    for env_name in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "OPENROUTER_API_KEY"):
        monkeypatch.delenv(env_name, raising=False)

    async def _run():
        with respx.mock:
            try:
                await classify_intent(QUERY, SYSTEM_ID)
                return False
            except ValueError:
                return True

    raised = asyncio.run(_run())
    assert raised


def test_a0_system_prompt_contains_all_six_agent_capability_lines():
    for agent_id in ("A1", "A2", "A3", "A4", "A5", "A6"):
        assert f'"{agent_id}"' in A0_SYSTEM_PROMPT
