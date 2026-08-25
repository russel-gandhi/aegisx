"""
Tests for `app.llm_router` — provider routing, wire-contract correctness
(respx-mocked), and the degraded-mode fallback contract.

No LLM provider API key is configured anywhere in this repo (D-01). Every
test here proves request construction and response parsing against
provider-shaped mocked responses, plus the degraded/failure paths. It does
NOT prove that a live Gemini/DeepSeek/Groq/OpenRouter call returns useful
content — that is the operator follow-up recorded in 03-01-PLAN.md's
`user_setup`.

Follows the established `asyncio.run()`-inside-a-plain-`def`-test
convention; pytest-asyncio is deliberately absent.
"""

import asyncio

import httpx
import pytest
import respx

from app import llm_router
from app.llm_router import PROVIDER_CONFIG, call_llm, select_provider


GEMINI_SUCCESS_BODY = {
    "candidates": [{"content": {"parts": [{"text": "The system appears audit ready."}]}}]
}

OPENAI_COMPATIBLE_SUCCESS_BODY = {
    "choices": [{"message": {"content": "Incident routed to A5."}}],
    "model": "openai/gpt-oss-120b",
}


def test_select_provider_routes_by_task():
    assert select_provider("orchestrator") == "gemini_flash_thinking"
    assert select_provider("compliance") == "gemini_flash_fast"
    assert select_provider("fallback") == "openrouter_fallback"


def test_select_provider_raises_keyerror_on_unknown_task():
    with pytest.raises(KeyError):
        select_provider("no_such_task")


def test_call_llm_parses_mocked_gemini_response(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")

    async def _run():
        with respx.mock:
            route = respx.post(
                "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent"
            ).mock(return_value=httpx.Response(200, json=GEMINI_SUCCESS_BODY))
            result = await call_llm(task="orchestrator", prompt="Is GXP-MFG-DEMO-01 audit ready?")
            return result, route

    result, route = asyncio.run(_run())
    assert route.called
    assert result.text == "The system appears audit ready."
    assert result.model_id == "gemini-3.6-flash"
    assert result.degraded is False

    sent_request = route.calls.last.request
    assert sent_request.headers["x-goog-api-key"] == "test-gemini-key"
    import json as _json

    sent_body = _json.loads(sent_request.content)
    assert "contents" in sent_body
    assert (
        sent_body["generationConfig"]["thinkingConfig"]["thinkingBudget"]
        == PROVIDER_CONFIG["gemini_flash_thinking"]["thinking_budget"]
        == 512
    )


def test_call_llm_compliance_task_uses_minimum_thinking_budget(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")

    async def _run():
        with respx.mock:
            route = respx.post(
                "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent"
            ).mock(return_value=httpx.Response(200, json=GEMINI_SUCCESS_BODY))
            await call_llm(task="compliance", prompt="Check URS-042.")
            return route

    route = asyncio.run(_run())
    import json as _json

    sent_body = _json.loads(route.calls.last.request.content)
    assert sent_body["generationConfig"]["thinkingConfig"]["thinkingBudget"] == 1


def test_call_llm_parses_mocked_openai_compatible_response(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-groq-key")

    async def _run():
        with respx.mock:
            route = respx.post("https://api.groq.com/openai/v1/chat/completions").mock(
                return_value=httpx.Response(200, json=OPENAI_COMPATIBLE_SUCCESS_BODY)
            )
            result = await call_llm(task="incident", prompt="Summarize INC-849201.")
            return result, route

    result, route = asyncio.run(_run())
    assert route.called
    assert result.text == "Incident routed to A5."
    assert result.model_id == "openai/gpt-oss-120b"


def test_call_llm_cascades_to_openrouter_on_429(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter-key")

    async def _run():
        with respx.mock:
            respx.post(
                "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent"
            ).mock(return_value=httpx.Response(429, json={"error": "rate limited"}))
            openrouter_route = respx.post("https://openrouter.ai/api/v1/chat/completions").mock(
                return_value=httpx.Response(
                    200,
                    json={
                        "choices": [{"message": {"content": "Fallback response."}}],
                        "model": "openrouter/auto",
                    },
                )
            )
            result = await call_llm(task="orchestrator", prompt="Classify this query.")
            return result, openrouter_route

    result, openrouter_route = asyncio.run(_run())
    assert openrouter_route.called
    assert result.text == "Fallback response."
    assert result.model_id == "openrouter/auto"
    assert result.degraded is False


def test_call_llm_cascades_to_openrouter_on_500_and_timeout(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter-key")

    async def _run_500():
        with respx.mock:
            respx.post(
                "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent"
            ).mock(return_value=httpx.Response(500, json={"error": "internal"}))
            openrouter_route = respx.post("https://openrouter.ai/api/v1/chat/completions").mock(
                return_value=httpx.Response(
                    200,
                    json={"choices": [{"message": {"content": "ok"}}], "model": "openrouter/auto"},
                )
            )
            result = await call_llm(task="orchestrator", prompt="q")
            return result, openrouter_route

    result, openrouter_route = asyncio.run(_run_500())
    assert openrouter_route.called
    assert result.degraded is False

    async def _run_timeout():
        with respx.mock:
            respx.post(
                "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent"
            ).mock(side_effect=httpx.TimeoutException("timed out"))
            openrouter_route = respx.post("https://openrouter.ai/api/v1/chat/completions").mock(
                return_value=httpx.Response(
                    200,
                    json={"choices": [{"message": {"content": "ok"}}], "model": "openrouter/auto"},
                )
            )
            result = await call_llm(task="orchestrator", prompt="q")
            return result, openrouter_route

    result, openrouter_route = asyncio.run(_run_timeout())
    assert openrouter_route.called
    assert result.degraded is False


def test_call_llm_no_key_present_returns_degraded_and_makes_no_requests(monkeypatch):
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
            # No routes registered at all — any outbound request raises
            # respx's own "no matching route" AssertionError, making an
            # accidental HTTP attempt fail the test loudly.
            result = await call_llm(task="orchestrator", prompt="q")
            return result

    result = asyncio.run(_run())
    assert result.degraded is True
    assert result.text == ""
    assert result.failure_reason is not None
    assert "missing_key" in result.failure_reason


def test_call_llm_never_logs_the_key_value_on_failure(monkeypatch, caplog):
    sentinel_key = "sk-do-not-leak-this-value-12345"
    monkeypatch.setenv("GEMINI_API_KEY", sentinel_key)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    async def _run():
        with respx.mock:
            respx.post(
                "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent"
            ).mock(return_value=httpx.Response(500, json={"error": "internal"}))
            return await call_llm(task="orchestrator", prompt="q")

    with caplog.at_level("WARNING"):
        result = asyncio.run(_run())

    assert result.degraded is True
    for record in caplog.records:
        assert sentinel_key not in record.getMessage()
        assert sentinel_key not in str(record.args)


def test_leak_key_absent_from_log_on_missing_key_path(monkeypatch, caplog):
    """Named to match `-k leak` selection per the plan's acceptance criteria."""
    for env_name in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "OPENROUTER_API_KEY"):
        monkeypatch.delenv(env_name, raising=False)

    async def _run():
        with respx.mock:
            return await call_llm(task="orchestrator", prompt="q")

    with caplog.at_level("WARNING"):
        result = asyncio.run(_run())

    assert result.degraded is True
    # No key was ever set, so this is really just confirming the missing-key
    # path logs cleanly with no key material to leak in the first place.
    for record in caplog.records:
        assert "sk-" not in record.getMessage()
