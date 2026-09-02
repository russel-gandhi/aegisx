"""
Tests for `app.retrieval.embeddings` (Phase 06.1, plan 06.1-01).

2026-09-01: rewritten for the local-first routing change. `google_gemini_embedding`
no longer exists in `EMBEDDING_PROVIDER_CONFIG` -- `ollama_embedding` (local
`nomic-embed-text`, no API key, no batch-endpoint-shape ambiguity) replaces
it entirely. See `embeddings.py`'s own `EMBEDDING_PROVIDER_CONFIG` comment
for the live evidence behind the removal (a real 429 response body naming
the exact free-tier quota metric, inactive billing).

Covers every `<behavior>` bullet in 06.1-01-PLAN.md Task 1 for the
embedding module, retargeted to Ollama's wire shape: the success path
(wire shape + L2 normalization), the connection-failure degrade, the
HTTP-failure degrade, and the batch endpoint's request-count discipline.
The retry/backoff mechanism itself is provider-agnostic code -- testing it
against a mocked Ollama 429 (something the real local server never
actually returns) is exactly as valid as testing it against a hosted
mock, and keeps this suite from needing a live rate limit to exercise.

Follows the established `asyncio.run()`-inside-a-plain-`def`-test
convention (`test_llm_router.py`); pytest-asyncio is deliberately absent.
No live provider is used anywhere in this module -- every HTTP call is
respx-mocked.
"""

import asyncio
import math

import httpx
import respx

from app.retrieval.embeddings import (
    EMBEDDING_DIMENSIONS,
    EMBEDDING_MAX_RETRIES,
    EMBEDDING_PROVIDER_CONFIG,
    call_embedding,
    call_embeddings_batch,
    select_embedding_provider,
)


def _unit_vector(dimensions: int, seed: int = 1) -> list:
    """A deterministic, non-uniform, non-unit vector for a mocked response
    body -- exercises real L2 normalization inside `call_embedding()`
    rather than a vector that is trivially already unit-length."""
    return [((i * seed + 1) % 97) / 13.0 - 3.5 for i in range(dimensions)]


def test_select_embedding_provider_routes_document_and_query_tasks():
    assert select_embedding_provider("embed_document") == "ollama_embedding"
    assert select_embedding_provider("embed_query") == "ollama_embedding"


def test_call_embedding_returns_768_unit_norm_vector():
    """Ollama needs no API key -- this test deliberately configures none,
    proving `_resolve_entry`'s empty-`api_key_env` handling works end to
    end, not just that the route matches."""
    raw_vector = _unit_vector(EMBEDDING_DIMENSIONS)

    async def _run():
        with respx.mock:
            route = respx.post("http://127.0.0.1:11434/api/embed").mock(
                return_value=httpx.Response(200, json={"model": "nomic-embed-text", "embeddings": [raw_vector]})
            )
            result = await call_embedding("A URS extract about audit trails.")
            return result, route

    result, route = asyncio.run(_run())
    assert route.called
    assert result.degraded is False
    assert result.failure_reason is None
    assert result.provider == "ollama"
    assert len(result.vector) == EMBEDDING_DIMENSIONS == 768
    norm = math.sqrt(sum(v * v for v in result.vector))
    assert abs(norm - 1.0) < 1e-5

    import json as _json

    sent_body = _json.loads(route.calls.last.request.content)
    assert sent_body["model"] == "nomic-embed-text"
    assert sent_body["input"] == "A URS extract about audit trails."


def test_call_embedding_connection_error_degrades_without_raising(monkeypatch):
    """The realistic Ollama failure mode -- the local server isn't
    running -- degrades cleanly rather than propagating, exactly the same
    contract a hosted-provider outage has."""

    async def _run():
        with respx.mock:
            respx.post("http://127.0.0.1:11434/api/embed").mock(
                side_effect=httpx.ConnectError("connection refused")
            )
            return await call_embedding("Server is down.")

    result = asyncio.run(_run())
    assert result.degraded is True
    assert result.failure_reason is not None
    assert result.vector == []


def test_call_embedding_http_500_degrades_without_raising():
    async def _run():
        with respx.mock:
            respx.post("http://127.0.0.1:11434/api/embed").mock(
                return_value=httpx.Response(500, json={"error": "internal"})
            )
            return await call_embedding("Trigger a 500.")

    result = asyncio.run(_run())
    assert result.degraded is True
    assert result.failure_reason is not None
    assert result.vector == []


def test_call_embedding_timeout_degrades_without_raising():
    async def _run():
        with respx.mock:
            respx.post("http://127.0.0.1:11434/api/embed").mock(
                side_effect=httpx.TimeoutException("timed out")
            )
            return await call_embedding("Trigger a timeout.")

    result = asyncio.run(_run())
    assert result.degraded is True
    assert result.failure_reason is not None
    assert result.vector == []


def _no_sleep(monkeypatch):
    """Patch `asyncio.sleep` inside `app.retrieval.embeddings` to a no-op
    so retry-backoff tests run instantly rather than actually waiting the
    real 1s/2s/4s delays."""
    async def _instant(_seconds):
        return None

    monkeypatch.setattr("app.retrieval.embeddings.asyncio.sleep", _instant)


def test_call_embedding_retries_429_then_succeeds(monkeypatch):
    """Deviation 19: a single 429 is transient, not terminal -- the second
    attempt succeeding must return a real (non-degraded) result. The real
    Ollama server has no rate limit to trigger this from, but the retry
    logic itself is provider-agnostic and this proves it still fires
    correctly for any 429 the wire happens to return."""
    _no_sleep(monkeypatch)
    raw_vector = _unit_vector(EMBEDDING_DIMENSIONS, seed=3)

    async def _run():
        with respx.mock:
            route = respx.post("http://127.0.0.1:11434/api/embed").mock(
                side_effect=[
                    httpx.Response(429, json={"error": "rate limited"}),
                    httpx.Response(200, json={"model": "nomic-embed-text", "embeddings": [raw_vector]}),
                ]
            )
            result = await call_embedding("Retries once then succeeds.")
            return result, route

    result, route = asyncio.run(_run())
    assert route.call_count == 2
    assert result.degraded is False
    assert len(result.vector) == EMBEDDING_DIMENSIONS


def test_call_embedding_exhausts_429_retries_then_degrades(monkeypatch):
    """A sustained rate limit -- every attempt 429s -- must still degrade
    rather than retry forever; exactly `EMBEDDING_MAX_RETRIES` + 1 total
    attempts (the original plus every retry) are made."""
    _no_sleep(monkeypatch)

    async def _run():
        with respx.mock:
            route = respx.post("http://127.0.0.1:11434/api/embed").mock(
                return_value=httpx.Response(429, json={"error": "rate limited"})
            )
            result = await call_embedding("Always rate limited.")
            return result, route

    result, route = asyncio.run(_run())
    assert route.call_count == EMBEDDING_MAX_RETRIES + 1
    assert result.degraded is True
    assert result.failure_reason == "http_429:ollama_embedding"
    assert result.vector == []


def test_call_embedding_honors_retry_after_header(monkeypatch):
    """A provider-sent `Retry-After` header is authoritative over our own
    exponential backoff -- asserted by checking the actual sleep delay
    passed, not just that a retry happened."""
    observed_delays = []

    async def _capture_sleep(seconds):
        observed_delays.append(seconds)

    monkeypatch.setattr("app.retrieval.embeddings.asyncio.sleep", _capture_sleep)
    raw_vector = _unit_vector(EMBEDDING_DIMENSIONS, seed=4)

    async def _run():
        with respx.mock:
            respx.post("http://127.0.0.1:11434/api/embed").mock(
                side_effect=[
                    httpx.Response(429, headers={"Retry-After": "7"}, json={"error": "rate limited"}),
                    httpx.Response(200, json={"model": "nomic-embed-text", "embeddings": [raw_vector]}),
                ]
            )
            return await call_embedding("Retry-After is honored.")

    result = asyncio.run(_run())
    assert result.degraded is False
    assert observed_delays == [7.0]


def test_call_embeddings_batch_retries_429_at_batch_level_before_falling_back(monkeypatch):
    """A 429 on the batch endpoint itself must retry before falling back
    to N sequential calls -- the fallback path exists for non-retryable
    failures, not as the first response to a transient rate limit."""
    _no_sleep(monkeypatch)
    vectors = [_unit_vector(EMBEDDING_DIMENSIONS, seed=i) for i in range(3)]

    async def _run():
        with respx.mock:
            batch_route = respx.post("http://127.0.0.1:11434/api/embed").mock(
                side_effect=[
                    httpx.Response(429, json={"error": "rate limited"}),
                    httpx.Response(200, json={"model": "nomic-embed-text", "embeddings": vectors}),
                ]
            )
            results = await call_embeddings_batch(["a", "b", "c"])
            return results, batch_route

    results, batch_route = asyncio.run(_run())
    assert batch_route.call_count == 2
    assert all(not r.degraded for r in results)
    assert len(results) == 3


def test_call_embeddings_batch_returns_in_order_with_one_http_request():
    vectors = [
        _unit_vector(EMBEDDING_DIMENSIONS, seed=3),
        _unit_vector(EMBEDDING_DIMENSIONS, seed=5),
        _unit_vector(EMBEDDING_DIMENSIONS, seed=7),
    ]

    async def _run():
        with respx.mock:
            route = respx.post("http://127.0.0.1:11434/api/embed").mock(
                return_value=httpx.Response(200, json={"model": "nomic-embed-text", "embeddings": vectors})
            )
            results = await call_embeddings_batch(["a", "b", "c"])
            return results, route

    results, route = asyncio.run(_run())
    assert route.call_count == 1  # ceil(3/32) == 1, never one call per text
    assert len(results) == 3
    assert all(r.degraded is False for r in results)
    assert all(len(r.vector) == EMBEDDING_DIMENSIONS for r in results)


def test_call_embeddings_batch_falls_back_to_sequential_on_batch_endpoint_failure():
    single_vector = _unit_vector(EMBEDDING_DIMENSIONS, seed=11)

    async def _run():
        with respx.mock:
            # Both the batch call and each per-text fallback call hit the
            # same /api/embed route -- Ollama has one endpoint for both
            # shapes (list input for batch, single string for one text),
            # unlike Gemini's two distinctly-named endpoints. The mock
            # must therefore fail exactly once (the batch attempt) and
            # succeed on every subsequent call (the sequential fallback).
            route = respx.post("http://127.0.0.1:11434/api/embed").mock(
                side_effect=[
                    httpx.Response(500, json={"error": "internal"}),
                    httpx.Response(500, json={"error": "internal"}),
                    httpx.Response(200, json={"model": "nomic-embed-text", "embeddings": [single_vector]}),
                    httpx.Response(200, json={"model": "nomic-embed-text", "embeddings": [single_vector]}),
                ]
            )
            results = await call_embeddings_batch(["x", "y"])
            return results, route

    results, route = asyncio.run(_run())
    # 2 batch attempts (EMBEDDING_BATCH_RETRY_ATTEMPTS) + 2 sequential
    # fallback calls (one per text) = 4 total requests.
    assert route.call_count == 4
    assert len(results) == 2
    assert all(r.degraded is False for r in results)


def test_embedding_provider_config_pins_model_and_dimensions():
    entry = EMBEDDING_PROVIDER_CONFIG["ollama_embedding"]
    assert entry["model"] == "nomic-embed-text"
    assert entry["api_key_env"] == ()
    assert EMBEDDING_DIMENSIONS == 768
