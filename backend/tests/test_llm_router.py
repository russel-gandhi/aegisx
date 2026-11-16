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
    _estimate_request_tokens,
    _parse_reset_duration_seconds,
    _record_token_headers,
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
    assert select_provider("orchestrator") == "groq_gpt_oss"
    assert select_provider("compliance") == "groq_gpt_oss"
    assert select_provider("narration") == "groq_qwen"
    assert select_provider("fallback") == "openrouter_fallback"


def test_select_provider_routes_remediation_to_groq_not_ollama(monkeypatch):
    """260826-rsw: 'remediation' lives on `groq_gpt_oss`, never on the local
    provider."""
    assert select_provider("remediation") == "groq_gpt_oss"
    assert "remediation" not in PROVIDER_CONFIG["ollama_qwen"]["use_for"]
    assert "remediation" in PROVIDER_CONFIG["groq_gpt_oss"]["use_for"]


def test_no_task_leads_with_the_local_provider():
    """2026-11-16 (Deviation 20): hosted-first. While Ollama was the first
    hop, `orchestrator` could not finish inside A0's 2000ms budget (1.7s
    warm, 7.6s cold, ~2s just to be refused when Ollama is not running), so
    A0 fell back to the full agent set on every query. Ollama stays in the
    cascade; it must never again be a task's first hop."""
    assert PROVIDER_CONFIG["ollama_qwen"]["use_for"] == []
    assert "ollama_qwen" in llm_router.FALLBACK_CASCADE
    for entry_key, entry in PROVIDER_CONFIG.items():
        if entry["use_for"]:
            assert entry["provider"] != "ollama", entry_key


def test_fallback_cascade_is_hosted_first_and_ends_at_openrouter():
    cascade = llm_router.FALLBACK_CASCADE
    assert set(cascade) == set(PROVIDER_CONFIG)
    assert cascade[-1] == "openrouter_fallback"
    assert cascade.index("groq_gpt_oss") < cascade.index("ollama_qwen")
    assert cascade.index("groq_qwen") < cascade.index("ollama_qwen")
    assert cascade.index("groq_gpt_oss_20b") < cascade.index("ollama_qwen")


def test_groq_entries_use_three_distinct_models():
    """Groq rate-limits per model, so three entries only add capacity if
    they really are three models."""
    groq_models = [e["model"] for e in PROVIDER_CONFIG.values() if e["provider"] == "groq"]
    assert len(groq_models) == 3
    assert len(set(groq_models)) == 3


def test_select_provider_routes_synthesis_to_groq_not_ollama():
    """2026-09-08: 'synthesis' moved from `ollama_qwen` to `groq_gpt_oss`.

    The local hop was measured at 35.8s/52.7s on the real 13-excerpt
    Copilot prompt against a 10s default budget, so it could never
    complete and the Copilot emitted its deterministic fallback on every
    query. Asserted in both directions so a future edit cannot silently
    move it back and reintroduce a permanently-degraded answer path."""
    assert select_provider("synthesis") == "groq_gpt_oss"
    assert "synthesis" in PROVIDER_CONFIG["groq_gpt_oss"]["use_for"]
    assert "synthesis" not in PROVIDER_CONFIG["ollama_qwen"]["use_for"]


def test_rerank_also_routes_to_groq_not_ollama():
    """'rerank' moved with synthesis: 130.1s on the local model against
    the graph's own 45s ceiling means it could never complete there."""
    assert PROVIDER_CONFIG[select_provider("rerank")]["provider"] == "groq"
    assert "rerank" not in PROVIDER_CONFIG["ollama_qwen"]["use_for"]


def test_rerank_plus_synthesis_fit_one_groq_token_minute_together():
    """The constraint that makes co-locating rerank and synthesis on Groq
    safe at all, asserted against the real request-estimator rather than
    the hand-written numbers in the comments. Both calls land in the same
    user query, so their combined estimate must clear `groq_gpt_oss`'s
    real 8,000 tpm ceiling -- at the previous 800-char rerank excerpt they
    summed to ~9,159 and blew it on every single query."""
    from app.retrieval.hybrid_search import (
        RERANK_EXCERPT_MAX_CHARS,
        RERANK_MAX_CANDIDATES,
        RERANK_SYSTEM_PROMPT,
    )
    from app.routes.copilot_query import SYNTHESIS_SYSTEM_PROMPT

    # ~90 chars of "[i] chunk_id=... | section=... | text=" scaffolding per line.
    rerank_prompt = "x" * (RERANK_MAX_CANDIDATES * (RERANK_EXCERPT_MAX_CHARS + 90))
    rerank_estimate = _estimate_request_tokens("rerank", rerank_prompt, RERANK_SYSTEM_PROMPT)
    # 13 excerpts x ~1,000 chars is the real measured synthesis prompt.
    synthesis_estimate = _estimate_request_tokens("synthesis", "y" * 13248, SYNTHESIS_SYSTEM_PROMPT)

    tpm_limit = PROVIDER_CONFIG["groq_gpt_oss"]["tpm_limit"]
    assert rerank_estimate + synthesis_estimate < tpm_limit, (
        f"rerank ({rerank_estimate}) + synthesis ({synthesis_estimate}) must fit "
        f"Groq's {tpm_limit} tpm ceiling or they starve each other"
    )


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


def test_call_llm_cascades_on_200_response_missing_choices_key(monkeypatch):
    """A provider can return HTTP 200 with a body that isn't the expected
    `choices[0].message.content` shape (observed live: OpenRouter's
    fallback route returning an error payload with a 200 status). This
    must cascade to the next provider -- not crash `call_llm` with an
    unhandled KeyError, which would violate its documented never-raises
    contract."""
    monkeypatch.setenv("GROQ_API_KEY", "test-groq-key")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter-key")

    async def _run():
        with respx.mock:
            respx.post("http://127.0.0.1:11434/v1/chat/completions").mock(
                return_value=httpx.Response(200, json={"error": {"message": "rate limited"}})
            )
            respx.post("https://api.groq.com/openai/v1/chat/completions").mock(
                return_value=httpx.Response(200, json={"error": {"message": "rate limited"}})
            )
            openrouter_route = respx.post("https://openrouter.ai/api/v1/chat/completions").mock(
                return_value=httpx.Response(200, json=OPENAI_COMPATIBLE_SUCCESS_BODY)
            )
            result = await call_llm(task="orchestrator", prompt="q")
            return result, openrouter_route

    result, openrouter_route = asyncio.run(_run())
    assert openrouter_route.called
    assert result.degraded is False
    assert result.text == OPENAI_COMPATIBLE_SUCCESS_BODY["choices"][0]["message"]["content"]


def test_call_llm_all_providers_return_malformed_response_returns_degraded_not_raise(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-groq-key")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter-key")

    async def _run():
        with respx.mock:
            respx.post("http://127.0.0.1:11434/v1/chat/completions").mock(
                return_value=httpx.Response(200, json={"unexpected": "shape"})
            )
            respx.post("https://api.groq.com/openai/v1/chat/completions").mock(
                return_value=httpx.Response(200, json={"unexpected": "shape"})
            )
            respx.post("https://openrouter.ai/api/v1/chat/completions").mock(
                return_value=httpx.Response(200, json={"unexpected": "shape"})
            )
            return await call_llm(task="orchestrator", prompt="q")

    result = asyncio.run(_run())
    assert result.degraded is True


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


def test_build_openai_compatible_request_ollama_carries_keep_alive():
    """Ollama unloads a model from memory after its own default idle
    window, paying a real multi-second reload on the next call. Requesting
    a longer `keep_alive` keeps it resident across the gap between one
    query and the next in normal operation -- the fix for repeated
    rerank-call timeouts, not a timeout-tuning workaround."""
    entry = PROVIDER_CONFIG["ollama_qwen"]
    request = _build_openai_compatible_request(entry, "k", "p", "s", False)
    assert request["json"]["keep_alive"] == "30m"


def test_build_openai_compatible_request_non_ollama_omits_keep_alive():
    entry = PROVIDER_CONFIG["groq_gpt_oss"]
    request = _build_openai_compatible_request(entry, "k", "p", "s", False)
    assert "keep_alive" not in request["json"]


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


# ---------------------------------------------------------------------------
# SENT-8-02: circuit breaker integration with call_llm's real cascade loop
# ---------------------------------------------------------------------------


def test_circuit_breaker_skips_provider_tripped_by_a_prior_call(monkeypatch):
    """The exact scenario SENT-8-02 exists for: two concurrent agent calls
    both route to `groq_gpt_oss`. The first call discovers a real 429 and
    trips the breaker. The second call must skip Groq entirely -- proven
    here by leaving Groq's route completely unmocked on the second call;
    respx raises `AllMockedAssertionError` if the code actually tries to
    reach an unregistered route, so a clean pass proves the skip really
    happened, not just that the end result looked right."""
    monkeypatch.setenv("GROQ_API_KEY", "test-groq-key")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-openrouter-key")

    async def _first_call_trips_the_breaker():
        with respx.mock:
            respx.post("http://127.0.0.1:11434/v1/chat/completions").mock(
                return_value=httpx.Response(429, json={"error": "rate limited"})
            )
            respx.post("https://api.groq.com/openai/v1/chat/completions").mock(
                return_value=httpx.Response(
                    429,
                    json={"error": "rate limited"},
                    headers={"x-ratelimit-reset-tokens": "30s"},
                )
            )
            respx.post("https://openrouter.ai/api/v1/chat/completions").mock(
                return_value=httpx.Response(
                    200,
                    json={"choices": [{"message": {"content": "ok"}}], "model": "openrouter/auto"},
                )
            )
            return await call_llm(task="orchestrator", prompt="first")

    async def _second_call_must_skip_groq():
        with respx.mock:
            respx.post("http://127.0.0.1:11434/v1/chat/completions").mock(
                return_value=httpx.Response(429, json={"error": "rate limited"})
            )
            # Deliberately no route registered for Groq -- if call_llm
            # tries to reach it anyway, respx raises and this test fails.
            openrouter_route = respx.post("https://openrouter.ai/api/v1/chat/completions").mock(
                return_value=httpx.Response(
                    200,
                    json={"choices": [{"message": {"content": "second"}}], "model": "openrouter/auto"},
                )
            )
            result = await call_llm(task="orchestrator", prompt="second")
            return result, openrouter_route

    first_result = asyncio.run(_first_call_trips_the_breaker())
    assert first_result.degraded is False

    second_result, openrouter_route = asyncio.run(_second_call_must_skip_groq())
    assert openrouter_route.called
    assert second_result.text == "second"
    assert second_result.degraded is False


def test_circuit_breaker_does_not_skip_a_provider_that_has_not_failed(monkeypatch):
    """Negative case: a provider with no prior failure must still be
    attempted normally -- the breaker must not default to skipping."""
    monkeypatch.setenv("GROQ_API_KEY", "test-groq-key")

    async def _run():
        with respx.mock:
            respx.post("http://127.0.0.1:11434/v1/chat/completions").mock(
                return_value=httpx.Response(429, json={"error": "rate limited"})
            )
            groq_route = respx.post("https://api.groq.com/openai/v1/chat/completions").mock(
                return_value=httpx.Response(
                    200,
                    json={"choices": [{"message": {"content": "groq ok"}}], "model": "openai/gpt-oss-120b"},
                )
            )
            result = await call_llm(task="orchestrator", prompt="q")
            return result, groq_route

    result, groq_route = asyncio.run(_run())
    assert groq_route.called
    assert result.text == "groq ok"


# ---------------------------------------------------------------------------
# SENT-8-01: token-budget estimation and rate-limit header parsing
# ---------------------------------------------------------------------------


def test_estimate_request_tokens_scales_with_prompt_length():
    short = _estimate_request_tokens("narration", "hi", "")
    long = _estimate_request_tokens("narration", "hi " * 1000, "")
    assert long > short


def test_estimate_request_tokens_uses_task_specific_completion_budget():
    # "remediation" (700) has a larger completion budget than "narration"
    # (250) for the identical prompt -- the task-specific table must
    # actually be consulted, not a single flat default for every task.
    narration = _estimate_request_tokens("narration", "same prompt", "")
    remediation = _estimate_request_tokens("remediation", "same prompt", "")
    assert remediation > narration


def test_estimate_request_tokens_falls_back_to_default_for_unknown_task():
    # Must not raise on a task name absent from the completion-budget
    # table (e.g. a future task added to PROVIDER_CONFIG before this
    # table is updated) -- degrades to the documented default instead.
    estimate = _estimate_request_tokens("some_future_task", "hello", "")
    assert estimate > 0


@pytest.mark.parametrize(
    "raw,expected_seconds",
    [
        ("13.305s", pytest.approx(13.305)),
        ("57m36s", pytest.approx(57 * 60 + 36)),
        ("1h2m3.5s", pytest.approx(3600 + 120 + 3.5)),
        ("2h", pytest.approx(7200)),
    ],
)
def test_parse_reset_duration_seconds_handles_groqs_real_formats(raw, expected_seconds):
    assert _parse_reset_duration_seconds(raw) == expected_seconds


def test_parse_reset_duration_seconds_returns_none_for_empty_or_garbage():
    assert _parse_reset_duration_seconds(None) is None
    assert _parse_reset_duration_seconds("") is None
    assert _parse_reset_duration_seconds("not-a-duration") is None


def test_record_token_headers_reads_real_groq_header_names(monkeypatch):
    # Confirms the exact header names this function reads match what Groq
    # actually sends (captured live 2026-09-02) -- a typo in either name
    # would silently make every response a no-op for live-tracking.
    recorded = {}

    def _fake_record(key, remaining, reset_seconds):
        recorded["key"] = key
        recorded["remaining"] = remaining
        recorded["reset_seconds"] = reset_seconds

    monkeypatch.setattr("app.llm_router.record_token_usage", _fake_record)

    headers = httpx.Headers(
        {
            "x-ratelimit-limit-tokens": "8000",
            "x-ratelimit-remaining-tokens": "6226",
            "x-ratelimit-reset-tokens": "13.305s",
        }
    )
    _record_token_headers("groq_gpt_oss", headers)

    assert recorded == {
        "key": "groq_gpt_oss",
        "remaining": 6226,
        "reset_seconds": pytest.approx(13.305),
    }


def test_record_token_headers_is_a_noop_when_headers_absent(monkeypatch):
    # Ollama sends no rate-limit headers at all -- must call through with
    # `None`/`None` (rate_limiter.record_token_usage already no-ops on
    # that), never raise.
    recorded = {}

    def _fake_record(key, remaining, reset_seconds):
        recorded["remaining"] = remaining
        recorded["reset_seconds"] = reset_seconds

    monkeypatch.setattr("app.llm_router.record_token_usage", _fake_record)
    _record_token_headers("ollama_qwen", httpx.Headers({}))
    assert recorded == {"remaining": None, "reset_seconds": None}


def test_groq_entry_declares_real_live_confirmed_tpm_limit():
    # Regression pin: SENT-8-01's whole premise is that this specific
    # number (confirmed live via a real x-ratelimit-limit-tokens header)
    # is what the rate limiter throttles against, not just rpm_limit.
    assert PROVIDER_CONFIG["groq_gpt_oss"]["tpm_limit"] == 8000


def test_non_groq_entries_have_no_tpm_limit():
    # Every other provider has no live-confirmed token constraint -- must
    # stay `None` (token-check no-op) rather than acquiring a guessed
    # value that could wrongly throttle a provider with real headroom.
    assert PROVIDER_CONFIG["ollama_qwen"].get("tpm_limit") is None
    assert PROVIDER_CONFIG["openrouter_fallback"].get("tpm_limit") is None


# --- 2026-11-16 regressions: the "always deterministic-fallback" audit -----

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
OLLAMA_URL = "http://127.0.0.1:11434/v1/chat/completions"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


def _groq_model_router(responses_by_model):
    """respx side effect answering per requested Groq model -- all three
    Groq entries share one URL and differ only in the body's `model`."""
    import json as _json

    seen = []

    def _handler(request):
        model = _json.loads(request.content)["model"]
        seen.append(model)
        return responses_by_model[model]

    return _handler, seen


def test_cascade_tries_the_next_groq_model_when_one_is_rate_limited(monkeypatch):
    """A 429 is per model. The cascade must move on to the next Groq entry
    (its own token bucket), not write off the whole provider -- skipping by
    provider would have thrown away two thirds of the hosted capacity."""
    monkeypatch.setenv("GROQ_API_KEY", "test-groq-key")
    handler, seen = _groq_model_router({
        "openai/gpt-oss-120b": httpx.Response(429, json={"error": "rate limited"}),
        "qwen/qwen3.8-27b": httpx.Response(
            200, json={"choices": [{"message": {"content": "from qwen"}}], "model": "qwen/qwen3.8-27b"}
        ),
    })

    async def _run():
        with respx.mock:
            respx.post(GROQ_URL).mock(side_effect=handler)
            return await call_llm(task="orchestrator", prompt="q")

    result = asyncio.run(_run())
    assert seen == ["openai/gpt-oss-120b", "qwen/qwen3.8-27b"]
    assert result.degraded is False
    assert result.model_id == "qwen/qwen3.8-27b"


def test_rejected_groq_key_skips_every_groq_entry(monkeypatch):
    """A 401 is account-wide: retrying the same key against two more models
    is three round trips to learn one fact. Exactly one Groq request, then
    straight on to the next provider."""
    monkeypatch.setenv("GROQ_API_KEY", "revoked-key")

    async def _run():
        with respx.mock:
            groq = respx.post(GROQ_URL).mock(return_value=httpx.Response(401, json={"error": "bad key"}))
            ollama = respx.post(OLLAMA_URL).mock(return_value=httpx.Response(200, json=OLLAMA_SUCCESS_BODY))
            result = await call_llm(task="orchestrator", prompt="q")
            return result, groq.call_count, ollama.call_count

    result, groq_calls, ollama_calls = asyncio.run(_run())
    assert groq_calls == 1
    assert ollama_calls == 1
    assert result.degraded is False
    assert result.provider == "ollama"


def test_missing_groq_key_skips_every_groq_entry_without_a_request(monkeypatch):
    async def _run():
        with respx.mock:
            groq = respx.post(GROQ_URL).mock(return_value=httpx.Response(200, json=OPENAI_COMPATIBLE_SUCCESS_BODY))
            respx.post(OLLAMA_URL).mock(side_effect=httpx.ConnectError("refused"))
            result = await call_llm(task="narration", prompt="q")
            return result, groq.call_count

    result, groq_calls = asyncio.run(_run())
    assert groq_calls == 0
    assert result.degraded is True
    assert result.failure_reason.count("missing_key:groq") == 1
    assert "missing_key:openrouter_fallback" in result.failure_reason


def test_empty_completion_cascades_instead_of_returning_a_blank_answer(monkeypatch):
    """A reasoning model that spends its whole completion budget thinking
    returns `content: null`, `finish_reason: "length"`. That used to come
    back as `text=""`, `degraded=False` -- a blank answer wearing a real
    model id."""
    monkeypatch.setenv("GROQ_API_KEY", "test-groq-key")
    handler, seen = _groq_model_router({
        "openai/gpt-oss-120b": httpx.Response(
            200,
            json={"choices": [{"message": {"content": None}, "finish_reason": "length"}], "model": "openai/gpt-oss-120b"},
        ),
        "qwen/qwen3.8-27b": httpx.Response(
            200, json={"choices": [{"message": {"content": "   "}}], "model": "qwen/qwen3.8-27b"}
        ),
        "openai/gpt-oss-20b": httpx.Response(
            200, json={"choices": [{"message": {"content": "A real answer."}}], "model": "openai/gpt-oss-20b"}
        ),
    })

    async def _run():
        with respx.mock:
            respx.post(GROQ_URL).mock(side_effect=handler)
            return await call_llm(task="synthesis", prompt="q")

    result = asyncio.run(_run())
    assert len(seen) == 3
    assert result.text == "A real answer."
    assert result.degraded is False


def test_non_json_2xx_body_degrades_instead_of_raising(monkeypatch):
    """An HTML page served with a 200 (proxy, captive portal) made
    `response.json()` raise `ValueError` straight out of `call_llm`."""
    monkeypatch.setenv("GROQ_API_KEY", "test-groq-key")
    html = httpx.Response(200, text="<html>gateway</html>", headers={"content-type": "text/html"})

    async def _run():
        with respx.mock:
            respx.post(GROQ_URL).mock(return_value=html)
            respx.post(OLLAMA_URL).mock(return_value=html)
            return await call_llm(task="narration", prompt="q")

    result = asyncio.run(_run())
    assert result.degraded is True
    assert "malformed_response:groq" in result.failure_reason
    assert "malformed_response:ollama" in result.failure_reason


def _trip_then_expire(monkeypatch, key):
    """Leave `key`'s breaker OPEN with its cooldown already elapsed, so the
    very next `is_available(key)` grants the HALF_OPEN probe."""
    from app import circuit_breaker

    circuit_breaker.record_rate_limited(key, 5.0)
    circuit_breaker._circuits[key].opened_until = 0.0


def test_cancelled_half_open_probe_does_not_strand_the_breaker(monkeypatch):
    """The bug behind "falls back until I restart the server": the one
    HALF_OPEN probe is cancelled by its caller's own deadline (A0's 2000ms
    `wait_for`, a narration ceiling, the 45s graph timeout), nothing
    resolves it, and `is_available()` answers False forever."""
    from app import circuit_breaker

    monkeypatch.setenv("GROQ_API_KEY", "test-groq-key")
    _trip_then_expire(monkeypatch, "groq_gpt_oss")

    async def _slow(request):
        await asyncio.sleep(5)
        return httpx.Response(200, json=OPENAI_COMPATIBLE_SUCCESS_BODY)

    async def _run():
        with respx.mock:
            route = respx.post(GROQ_URL).mock(side_effect=_slow)
            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(call_llm(task="orchestrator", prompt="q"), timeout=0.05)
            assert circuit_breaker._circuits["groq_gpt_oss"].half_open_probe_in_flight is False
            # The provider is healthy again; the next caller must reach it.
            route.mock(return_value=httpx.Response(200, json=OPENAI_COMPATIBLE_SUCCESS_BODY))
            return await call_llm(task="orchestrator", prompt="q")

    result = asyncio.run(_run())
    assert result.degraded is False
    assert result.model_id == "openai/gpt-oss-120b"
    assert circuit_breaker._circuits["groq_gpt_oss"].state.value == "closed"


@pytest.mark.parametrize("status", [400, 404, 422])
def test_non_cascadable_4xx_on_a_half_open_probe_releases_it(monkeypatch, status):
    """Groq answers 400 (`json_validate_failed`) when JSON mode produces
    invalid JSON. That is a verdict on the request, not on the provider --
    and it used to leave the probe slot held forever."""
    from app import circuit_breaker

    monkeypatch.setenv("GROQ_API_KEY", "test-groq-key")
    _trip_then_expire(monkeypatch, "groq_gpt_oss")

    async def _run():
        with respx.mock:
            respx.post(GROQ_URL).mock(return_value=httpx.Response(status, json={"error": "bad request"}))
            return await call_llm(task="orchestrator", prompt="q", json_output=True)

    result = asyncio.run(_run())
    assert result.degraded is True
    assert result.failure_reason == f"http_{status}:groq_gpt_oss"
    circuit = circuit_breaker._circuits["groq_gpt_oss"]
    assert circuit.half_open_probe_in_flight is False
    assert circuit_breaker.is_available("groq_gpt_oss") is True


def test_5xx_on_a_half_open_probe_reopens_the_breaker(monkeypatch):
    from app import circuit_breaker

    monkeypatch.setenv("GROQ_API_KEY", "test-groq-key")
    _trip_then_expire(monkeypatch, "groq_gpt_oss")
    handler, _seen = _groq_model_router({
        "openai/gpt-oss-120b": httpx.Response(503, json={"error": "unavailable"}),
        "qwen/qwen3.8-27b": httpx.Response(
            200, json={"choices": [{"message": {"content": "ok"}}], "model": "qwen/qwen3.8-27b"}
        ),
    })

    async def _run():
        with respx.mock:
            respx.post(GROQ_URL).mock(side_effect=handler)
            return await call_llm(task="orchestrator", prompt="q")

    result = asyncio.run(_run())
    assert result.degraded is False
    circuit = circuit_breaker._circuits["groq_gpt_oss"]
    assert circuit.state.value == "open"
    assert circuit.half_open_probe_in_flight is False
    assert circuit_breaker.is_available("groq_gpt_oss") is False


def test_unexpected_exception_on_a_half_open_probe_releases_it(monkeypatch):
    from app import circuit_breaker

    monkeypatch.setenv("GROQ_API_KEY", "test-groq-key")
    _trip_then_expire(monkeypatch, "groq_gpt_oss")

    async def _boom(*args, **kwargs):
        raise RuntimeError("not a failure type call_llm classifies")

    monkeypatch.setattr(llm_router, "_send_one", _boom)
    with pytest.raises(RuntimeError):
        asyncio.run(call_llm(task="orchestrator", prompt="q"))
    assert circuit_breaker._circuits["groq_gpt_oss"].half_open_probe_in_flight is False


def test_no_cascade_delay_after_a_hop_that_never_sent_a_request(monkeypatch):
    """A missing key and a pre-flight token rejection send nothing, so there
    is nothing to space out -- sleeping only spends the caller's budget."""
    monkeypatch.setattr(llm_router, "LLM_CASCADE_DELAY_SECONDS", 30.0)
    sleeps = []

    async def _fake_sleep(seconds):
        sleeps.append(seconds)

    monkeypatch.setattr(llm_router.asyncio, "sleep", _fake_sleep)

    async def _run():
        with respx.mock:
            respx.post(OLLAMA_URL).mock(return_value=httpx.Response(200, json=OLLAMA_SUCCESS_BODY))
            return await call_llm(task="orchestrator", prompt="q")

    result = asyncio.run(_run())  # no GROQ_API_KEY: three Groq entries skipped pre-flight
    assert result.degraded is False
    assert sleeps == []


def test_cascade_delay_still_applies_after_a_real_failed_request(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "test-groq-key")
    monkeypatch.setattr(llm_router, "LLM_CASCADE_DELAY_SECONDS", 0.25)
    sleeps = []

    async def _fake_sleep(seconds):
        sleeps.append(seconds)

    monkeypatch.setattr(llm_router.asyncio, "sleep", _fake_sleep)
    handler, _seen = _groq_model_router({
        "openai/gpt-oss-120b": httpx.Response(500, json={"error": "internal"}),
        "qwen/qwen3.8-27b": httpx.Response(
            200, json={"choices": [{"message": {"content": "ok"}}], "model": "qwen/qwen3.8-27b"}
        ),
    })

    async def _run():
        with respx.mock:
            respx.post(GROQ_URL).mock(side_effect=handler)
            return await call_llm(task="orchestrator", prompt="q")

    assert asyncio.run(_run()).degraded is False
    assert sleeps == [0.25]


def test_reasoning_effort_is_per_entry():
    gpt_oss = _build_openai_compatible_request(PROVIDER_CONFIG["groq_gpt_oss"], "k", "p", "", False)
    qwen = _build_openai_compatible_request(PROVIDER_CONFIG["groq_qwen"], "k", "p", "", False)
    small = _build_openai_compatible_request(PROVIDER_CONFIG["groq_gpt_oss_20b"], "k", "p", "", False)
    assert gpt_oss["json"]["reasoning_effort"] == "low"
    assert small["json"]["reasoning_effort"] == "low"
    assert qwen["json"]["reasoning_effort"] == "none"
    assert qwen["json"]["model"] == "qwen/qwen3.8-27b"


def test_ollama_connect_phase_has_its_own_short_timeout(monkeypatch):
    captured = {}

    def _capture(request):
        captured["timeout"] = request.extensions["timeout"]
        return httpx.Response(200, json=OLLAMA_SUCCESS_BODY)

    async def _run():
        with respx.mock:
            respx.post(OLLAMA_URL).mock(side_effect=_capture)
            return await call_llm(task="orchestrator", prompt="q", timeout=10.0)

    assert asyncio.run(_run()).degraded is False  # no Groq key: falls through to Ollama
    assert captured["timeout"]["connect"] == llm_router.OLLAMA_CONNECT_TIMEOUT_SECONDS
    assert captured["timeout"]["read"] == 10.0
