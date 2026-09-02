"""
Tests for `app.llm_router` — provider routing, wire-contract correctness
(respx-mocked), and the degraded-mode fallback contract.

2026-09-01: rewritten for the local-first routing change. `gemini_flash_thinking`,
`gemini_flash_fast`, and `deepseek_r1` no longer exist in `PROVIDER_CONFIG` --
`ollama_qwen` (local, no API key) now covers every task those three used to
serve. `groq_gpt_oss` and `openrouter_fallback` are unchanged. See
`llm_router.py`'s own `PROVIDER_CONFIG`/`FALLBACK_CASCADE` comments for the
live evidence behind the removal (real 429/402 responses, an inactive
billing account) -- this is not a speculative or provisional change.

No LLM provider API key is configured for Ollama -- it's local, no auth.
Every test here proves request construction and response parsing against
provider-shaped mocked responses, plus the degraded/failure paths. It does
NOT prove that a live Groq/OpenRouter call returns useful content, and for
Ollama specifically, does not require a running local server at all --
every test still mocks the wire, exactly as before.

Follows the established `asyncio.run()`-inside-a-plain-`def`-test
convention; pytest-asyncio is deliberately absent.
"""

import asyncio

import httpx
import pytest
import respx

from app import llm_router
from app.llm_router import (
    PROVIDER_CONFIG,
    _build_openai_compatible_request,
    call_llm,
    select_provider,
)


OLLAMA_SUCCESS_BODY = {
    "choices": [{"message": {"content": "The system appears audit ready."}}],
    "model": "qwen2.5:7b-instruct",
}

OPENAI_COMPATIBLE_SUCCESS_BODY = {
    "choices": [{"message": {"content": "Incident routed to A5."}}],
    "model": "openai/gpt-oss-120b",
}


def test_select_provider_routes_by_task():
    assert select_provider("orchestrator") == "ollama_qwen"
    assert select_provider("compliance") == "ollama_qwen"
    assert select_provider("fallback") == "openrouter_fallback"


def test_select_provider_routes_remediation_to_groq_not_ollama(monkeypatch):
    """260826-rsw: 'remediation' lives on `groq_gpt_oss`, not the local
    provider that now covers every other judgment/synthesis task. This
    must hold in both directions -- the moved key resolves to Groq, and
    the tasks that stay on `ollama_qwen` (orchestrator, synthesis) are
    unaffected."""
    assert select_provider("remediation") == "groq_gpt_oss"
    assert select_provider("orchestrator") == "ollama_qwen"
    assert select_provider("synthesis") == "ollama_qwen"
    assert "remediation" not in PROVIDER_CONFIG["ollama_qwen"]["use_for"]
    assert "remediation" in PROVIDER_CONFIG["groq_gpt_oss"]["use_for"]


def test_select_provider_raises_keyerror_on_unknown_task():
    with pytest.raises(KeyError):
        select_provider("no_such_task")


def test_select_provider_resolves_every_task_to_its_documented_provider():
    """Every task name `PROVIDER_CONFIG` declares resolves to the provider
    that actually claims it -- a single source-of-truth check against the
    live table rather than a hardcoded duplicate of `use_for`, so this
    test can't silently drift from the config it's checking."""
    for expected_provider, entry in PROVIDER_CONFIG.items():
        for task in entry["use_for"]:
            assert select_provider(task) == expected_provider


def test_call_llm_parses_mocked_ollama_response(monkeypatch):
    """Ollama needs no API key -- this test deliberately does NOT set one,
    proving `_send_one`'s empty-`api_key_env` handling works end to end,
    not just that the route matches."""

    async def _run():
        with respx.mock:
            route = respx.post("http://127.0.0.1:11434/v1/chat/completions").mock(
                return_value=httpx.Response(200, json=OLLAMA_SUCCESS_BODY)
            )
            result = await call_llm(task="orchestrator", prompt="Is GXP-MFG-DEMO-01 audit ready?")
            return result, route

    result, route = asyncio.run(_run())
    assert route.called
    assert result.text == "The system appears audit ready."
    assert result.model_id == "qwen2.5:7b-instruct"
    assert result.degraded is False
    assert result.provider == "ollama"

    import json as _json

    sent_body = _json.loads(route.calls.last.request.content)
    assert sent_body["model"] == "qwen2.5:7b-instruct"
    assert sent_body["messages"][-1]["content"] == "Is GXP-MFG-DEMO-01 audit ready?"


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


def test_call_llm_cascades_ollama_to_groq_to_openrouter_on_429(monkeypatch):
    """Full 3-hop cascade, in the current FALLBACK_CASCADE order
    (ollama_qwen -> groq_gpt_oss -> openrouter_fallback). Ollama needs no
    key; Groq and OpenRouter both do."""
    monkeypatch.setenv("GROQ_API_KEY", "test-groq-key")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter-key")

    async def _run():
        with respx.mock:
            respx.post("http://127.0.0.1:11434/v1/chat/completions").mock(
                return_value=httpx.Response(429, json={"error": "rate limited"})
            )
            respx.post("https://api.groq.com/openai/v1/chat/completions").mock(
                return_value=httpx.Response(429, json={"error": "rate limited"})
            )
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
    monkeypatch.setenv("GROQ_API_KEY", "test-groq-key")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter-key")

    async def _run_500():
        with respx.mock:
            respx.post("http://127.0.0.1:11434/v1/chat/completions").mock(
                return_value=httpx.Response(500, json={"error": "internal"})
            )
            respx.post("https://api.groq.com/openai/v1/chat/completions").mock(
                return_value=httpx.Response(500, json={"error": "internal"})
            )
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
            respx.post("http://127.0.0.1:11434/v1/chat/completions").mock(
                side_effect=httpx.TimeoutException("timed out")
            )
            respx.post("https://api.groq.com/openai/v1/chat/completions").mock(
                side_effect=httpx.TimeoutException("timed out")
            )
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


def test_call_llm_ollama_unreachable_cascades_without_needing_a_key(monkeypatch):
    """Ollama's empty `api_key_env` means a connection failure (server not
    running, or any transport error) is what surfaces for it -- never a
    `missing_key` reason, since no key was ever required. This is the
    scenario `_send_one`'s empty-tuple handling exists for."""
    monkeypatch.setenv("GROQ_API_KEY", "test-groq-key")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    async def _run():
        with respx.mock:
            respx.post("http://127.0.0.1:11434/v1/chat/completions").mock(
                side_effect=httpx.ConnectError("connection refused")
            )
            route = respx.post("https://api.groq.com/openai/v1/chat/completions").mock(
                return_value=httpx.Response(200, json=OPENAI_COMPATIBLE_SUCCESS_BODY)
            )
            result = await call_llm(task="orchestrator", prompt="q")
            return result, route

    result, route = asyncio.run(_run())
    assert route.called
    assert result.degraded is False
    assert "missing_key:ollama_qwen" not in (result.failure_reason or "")


def test_call_llm_no_providers_reachable_returns_degraded_and_makes_no_unexpected_requests(monkeypatch):
    for env_name in ("GEMINI_API_KEY", "GOOGLE_API_KEY", "DEEPSEEK_API_KEY", "GROQ_API_KEY", "OPENROUTER_API_KEY"):
        monkeypatch.delenv(env_name, raising=False)

    async def _run():
        with respx.mock:
            # Ollama needs no key, so it's still attempted -- mock it
            # failing (server down) so the cascade proceeds to Groq/
            # OpenRouter, which both degrade on `missing_key` since
            # neither has one configured.
            respx.post("http://127.0.0.1:11434/v1/chat/completions").mock(
                side_effect=httpx.ConnectError("connection refused")
            )
            result = await call_llm(task="orchestrator", prompt="q")
            return result

    result = asyncio.run(_run())
    assert result.degraded is True
    assert result.text == ""
    assert result.failure_reason is not None
    assert "missing_key:groq_gpt_oss" in result.failure_reason
    assert "missing_key:openrouter_fallback" in result.failure_reason


def test_call_llm_never_logs_the_key_value_on_failure(monkeypatch, caplog):
    """The sentinel key belongs to Groq now (the first hop that actually
    requires one) since Ollama, the first hop in the cascade, needs none
    at all."""
    sentinel_key = "sk-do-not-leak-this-value-12345"
    monkeypatch.setenv("GROQ_API_KEY", sentinel_key)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    async def _run():
        with respx.mock:
            respx.post("http://127.0.0.1:11434/v1/chat/completions").mock(
                side_effect=httpx.ConnectError("connection refused")
            )
            respx.post("https://api.groq.com/openai/v1/chat/completions").mock(
                return_value=httpx.Response(500, json={"error": "internal"})
            )
            return await call_llm(task="orchestrator", prompt="q")

    with caplog.at_level("WARNING"):
        result = asyncio.run(_run())

    assert result.degraded is True
    for record in caplog.records:
        assert sentinel_key not in record.getMessage()
        assert sentinel_key not in str(record.args)


def test_leak_key_absent_from_log_on_missing_key_path(monkeypatch, caplog):
    """Named to match `-k leak` selection per the plan's acceptance
    criteria. Ollama's own hop never has a 'missing key' path (it needs
    none) -- this now exercises Groq's and OpenRouter's missing-key paths
    instead, reached after Ollama itself fails to connect."""
    for env_name in ("GROQ_API_KEY", "OPENROUTER_API_KEY"):
        monkeypatch.delenv(env_name, raising=False)

    async def _run():
        with respx.mock:
            respx.post("http://127.0.0.1:11434/v1/chat/completions").mock(
                side_effect=httpx.ConnectError("connection refused")
            )
            return await call_llm(task="orchestrator", prompt="q")

    with caplog.at_level("WARNING"):
        result = asyncio.run(_run())

    assert result.degraded is True
    for record in caplog.records:
        assert "sk-" not in record.getMessage()


# ---------------------------------------------------------------------------
# _build_openai_compatible_request -- json_output plumbing (260826-rsw)
# ---------------------------------------------------------------------------
#
# T-rsw-02: this is the plan's whole premise. Presence AND absence of
# response_format are both asserted -- absence is what protects every
# already-shipped narration/incident/access call from silently changing
# shape. `ollama_qwen` replaces `deepseek_r1` in this parametrize list --
# both are plain OpenAI-compatible entries with no Groq-specific vendor
# fields, so the same assertions apply unchanged.


@pytest.mark.parametrize("entry_key", ["groq_gpt_oss", "ollama_qwen", "openrouter_fallback"])
def test_build_openai_compatible_request_carries_response_format_when_json_output_true(entry_key):
    entry = PROVIDER_CONFIG[entry_key]
    request = _build_openai_compatible_request(entry, "test-key", "prompt", "system", True)
    assert request["json"]["response_format"] == {"type": "json_object"}


@pytest.mark.parametrize("entry_key", ["groq_gpt_oss", "ollama_qwen", "openrouter_fallback"])
def test_build_openai_compatible_request_omits_response_format_when_json_output_false(entry_key):
    entry = PROVIDER_CONFIG[entry_key]
    request = _build_openai_compatible_request(entry, "test-key", "prompt", "system", False)
    assert "response_format" not in request["json"]


def test_build_openai_compatible_request_groq_completion_cap_differs_by_json_output():
    entry = PROVIDER_CONFIG["groq_gpt_oss"]
    without_json = _build_openai_compatible_request(entry, "k", "p", "s", False)
    with_json = _build_openai_compatible_request(entry, "k", "p", "s", True)
    assert without_json["json"]["max_completion_tokens"] == 512
    assert with_json["json"]["max_completion_tokens"] > 512


@pytest.mark.parametrize("json_output", [True, False])
def test_build_openai_compatible_request_openrouter_never_carries_groq_vendor_fields(json_output):
    entry = PROVIDER_CONFIG["openrouter_fallback"]
    request = _build_openai_compatible_request(entry, "k", "p", "s", json_output)
    assert "reasoning_effort" not in request["json"]
    assert "max_completion_tokens" not in request["json"]


@pytest.mark.parametrize("json_output", [True, False])
def test_build_openai_compatible_request_ollama_never_carries_groq_vendor_fields(json_output):
    """Ollama shares the OpenAI-compatible builder with Groq/DeepSeek/
    OpenRouter but is not Groq -- the reasoning_effort/max_completion_tokens
    gate stays strictly `provider == "groq"`."""
    entry = PROVIDER_CONFIG["ollama_qwen"]
    request = _build_openai_compatible_request(entry, "k", "p", "s", json_output)
    assert "reasoning_effort" not in request["json"]
    assert "max_completion_tokens" not in request["json"]


def test_call_llm_remediation_task_reaches_groq_with_json_mode_on_the_wire(monkeypatch):
    """The end-to-end proof: driving the REAL call_llm through the
    remediation task key hits the Groq endpoint (proving the routing move
    landed) with a captured request body carrying JSON mode (proving the
    json_output flag actually reaches the wire), not merely that a mock
    happened to return parseable text."""
    monkeypatch.setenv("GROQ_API_KEY", "test-groq-key")

    async def _run():
        with respx.mock:
            route = respx.post("https://api.groq.com/openai/v1/chat/completions").mock(
                return_value=httpx.Response(
                    200,
                    json={
                        "choices": [{"message": {"content": '{"root_cause": "x"}'}}],
                        "model": "openai/gpt-oss-120b",
                    },
                )
            )
            result = await call_llm(
                task="remediation", prompt="Draft a CAPA.", json_output=True
            )
            return result, route

    result, route = asyncio.run(_run())
    assert route.called
    assert result.degraded is False

    import json as _json

    sent_body = _json.loads(route.calls.last.request.content)
    assert sent_body["response_format"] == {"type": "json_object"}
    assert sent_body["max_completion_tokens"] == 2048
