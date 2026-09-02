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

# 2026-09-01: "orchestrator" now routes to the local `ollama_qwen` entry,
# not `gemini_flash_thinking` (removed from PROVIDER_CONFIG entirely --
# see llm_router.py's own comment for the live evidence). Ollama shares
# the OpenAI-compatible request/response shape with Groq/OpenRouter, not
# Gemini's `generationConfig`/`candidates` shape.
OLLAMA_URL = "http://127.0.0.1:11434/v1/chat/completions"
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


def _mock_ollama_json(text: str):
    return respx.post(OLLAMA_URL).mock(
        return_value=httpx.Response(
            200, json={"choices": [{"message": {"content": text}}], "model": "qwen2.5:7b-instruct"}
        )
    )


def test_mocked_classification_narrows_active_agents(monkeypatch):
    async def _run():
        with respx.mock:
            _mock_ollama_json(
                '{"active_agents": ["A1", "A2"], "intent_category": "audit_readiness"}'
            )
            return await run_a0(_state())

    result = asyncio.run(_run())
    assert result["active_agents"] == ["A1", "A2"]
    assert result["user_intent"] == "audit_readiness"


def test_request_targets_ollama_model_and_json_mode(monkeypatch):
    """Ollama has no per-request thinking-budget concept (that was
    Gemini-specific) -- the equivalent wire-contract proof for the
    OpenAI-compatible shape is the model id and JSON mode field."""

    async def _run():
        with respx.mock:
            route = _mock_ollama_json(
                '{"active_agents": ["A2"], "intent_category": "audit_readiness"}'
            )
            await run_a0(_state())
            return route

    route = asyncio.run(_run())
    assert route.called
    import json as _json

    sent = _json.loads(route.calls.last.request.content)
    assert sent["model"] == "qwen2.5:7b-instruct"
    assert sent["response_format"] == {"type": "json_object"}


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
    # A real OPENROUTER_API_KEY is configured in this repo's root .env
    # (D-01 follow-up) — deleted here so call_llm()'s own cascade-on-timeout
    # hits a clean missing-key degrade instead of attempting a real,
    # unmocked HTTP request to openrouter.ai under respx.mock.
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    async def _run():
        with respx.mock:
            respx.post(OLLAMA_URL).mock(side_effect=httpx.TimeoutException("timed out"))
            return await run_a0(_state())

    result = asyncio.run(_run())
    assert result["active_agents"] == FULL_AGENT_SET
    assert result["user_intent"] == "unclassified_fallback"


def test_invalid_json_candidate_text_falls_back(monkeypatch):
    async def _run():
        with respx.mock:
            _mock_ollama_json("This is not JSON at all.")
            return await run_a0(_state())

    result = asyncio.run(_run())
    assert result["active_agents"] == FULL_AGENT_SET
    assert result["user_intent"] == "unclassified_fallback"


def test_unknown_agent_id_in_classification_falls_back(monkeypatch):
    async def _run():
        with respx.mock:
            _mock_ollama_json(
                '{"active_agents": ["A1", "A9"], "intent_category": "audit_readiness"}'
            )
            return await run_a0(_state())

    result = asyncio.run(_run())
    assert result["active_agents"] == FULL_AGENT_SET
    assert result["user_intent"] == "unclassified_fallback"


def test_empty_active_agents_list_falls_back(monkeypatch):
    async def _run():
        with respx.mock:
            _mock_ollama_json('{"active_agents": [], "intent_category": "audit_readiness"}')
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
            # Groq/OpenRouter fail on their own missing keys, zero HTTP
            # attempted. Ollama needs no key at all, so it's genuinely
            # reached -- mocked unreachable here (the realistic
            # local-provider failure mode) rather than relying on a
            # missing credential that doesn't apply to it.
            respx.post(OLLAMA_URL).mock(side_effect=httpx.ConnectError("connection refused"))
            return await run_a0(_state())

    result = asyncio.run(_run())
    assert result["active_agents"] == FULL_AGENT_SET
    assert result["user_intent"] == "unclassified_fallback"


def test_every_fallback_returns_bible_ordered_full_set(monkeypatch):
    for env_name in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "OPENROUTER_API_KEY", "GROQ_API_KEY"):
        monkeypatch.delenv(env_name, raising=False)

    async def _run():
        with respx.mock:
            respx.post(OLLAMA_URL).mock(side_effect=httpx.ConnectError("connection refused"))
            return await run_a0(_state())

    result = asyncio.run(_run())
    assert result["active_agents"] == ["A1", "A2", "A3", "A4", "A5", "A6"]


def test_classify_intent_directly_raises_valueerror_on_degraded_response(monkeypatch):
    for env_name in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "OPENROUTER_API_KEY", "GROQ_API_KEY"):
        monkeypatch.delenv(env_name, raising=False)

    async def _run():
        with respx.mock:
            respx.post(OLLAMA_URL).mock(side_effect=httpx.ConnectError("connection refused"))
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
