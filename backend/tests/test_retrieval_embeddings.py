"""
Tests for `app.retrieval.embeddings` (Phase 06.1, plan 06.1-01).

Covers every `<behavior>` bullet in 06.1-01-PLAN.md Task 1 for the
embedding module: the live-key success path (wire shape + L2
normalization), the no-key degrade, the HTTP-failure degrade, and the
batch endpoint's request-count discipline.

Follows the established `asyncio.run()`-inside-a-plain-`def`-test
convention (`test_llm_router.py`); pytest-asyncio is deliberately absent.
No live provider key is used anywhere in this module -- every HTTP call is
respx-mocked, matching `test_llm_router.py`'s own no-live-key discipline.
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
    assert select_embedding_provider("embed_document") == "google_gemini_embedding"
    assert select_embedding_provider("embed_query") == "google_gemini_embedding"


def test_call_embedding_live_key_returns_768_unit_norm_vector(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    raw_vector = _unit_vector(EMBEDDING_DIMENSIONS)

    async def _run():
        with respx.mock:
            route = respx.post(
                "https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent"
            ).mock(return_value=httpx.Response(200, json={"embedding": {"values": raw_vector}}))
            result = await call_embedding("A URS extract about audit trails.")
            return result, route

    result, route = asyncio.run(_run())
    assert route.called
    assert result.degraded is False
    assert result.failure_reason is None
    assert len(result.vector) == EMBEDDING_DIMENSIONS == 768
    norm = math.sqrt(sum(v * v for v in result.vector))
    assert abs(norm - 1.0) < 1e-5

    sent_request = route.calls.last.request
    assert sent_request.url.params["key"] == "test-gemini-key"


def test_call_embedding_falls_back_to_list_shaped_response(monkeypatch):
    """The Gemini embedContent endpoint has shipped both a singular
    `{"embedding": {...}}` shape and a `{"embeddings": [{...}]}` list
    shape -- this asserts the fallback path."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    raw_vector = _unit_vector(EMBEDDING_DIMENSIONS, seed=2)

    async def _run():
        with respx.mock:
            respx.post(
                "https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent"
            ).mock(return_value=httpx.Response(200, json={"embeddings": [{"values": raw_vector}]}))
            return await call_embedding("Second shape.")

    result = asyncio.run(_run())
    assert result.degraded is False
    assert len(result.vector) == EMBEDDING_DIMENSIONS


def test_call_embedding_no_api_key_degrades_without_raising(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    result = asyncio.run(call_embedding("No key configured."))

    assert result.degraded is True
    assert result.failure_reason == "no API key configured"
    assert result.vector == []


def test_call_embedding_http_500_degrades_without_raising(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")

    async def _run():
        with respx.mock:
            respx.post(
                "https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent"
            ).mock(return_value=httpx.Response(500, json={"error": "internal"}))
            return await call_embedding("Trigger a 500.")

    result = asyncio.run(_run())
    assert result.degraded is True
    assert result.failure_reason is not None
    assert result.vector == []


def test_call_embedding_timeout_degrades_without_raising(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")

    async def _run():
        with respx.mock:
            respx.post(
                "https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent"
            ).mock(side_effect=httpx.TimeoutException("timed out"))
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
    attempt succeeding must return a real (non-degraded) result, not the
    old immediate-degrade behavior."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    _no_sleep(monkeypatch)
    raw_vector = _unit_vector(EMBEDDING_DIMENSIONS, seed=3)

    async def _run():
        with respx.mock:
            route = respx.post(
                "https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent"
            ).mock(
                side_effect=[
                    httpx.Response(429, json={"error": "rate limited"}),
                    httpx.Response(200, json={"embedding": {"values": raw_vector}}),
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
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    _no_sleep(monkeypatch)

    async def _run():
        with respx.mock:
            route = respx.post(
                "https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent"
            ).mock(return_value=httpx.Response(429, json={"error": "rate limited"}))
            result = await call_embedding("Always rate limited.")
            return result, route

    result, route = asyncio.run(_run())
    assert route.call_count == EMBEDDING_MAX_RETRIES + 1
    assert result.degraded is True
    assert result.failure_reason == "http_429:google_gemini_embedding"
    assert result.vector == []


def test_call_embedding_honors_retry_after_header(monkeypatch):
    """A provider-sent `Retry-After` header is authoritative over our own
    exponential backoff -- asserted by checking the actual sleep delay
    passed, not just that a retry happened."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    observed_delays = []

    async def _capture_sleep(seconds):
        observed_delays.append(seconds)

    monkeypatch.setattr("app.retrieval.embeddings.asyncio.sleep", _capture_sleep)
    raw_vector = _unit_vector(EMBEDDING_DIMENSIONS, seed=4)

    async def _run():
        with respx.mock:
            respx.post(
                "https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent"
            ).mock(
                side_effect=[
                    httpx.Response(429, headers={"Retry-After": "7"}, json={"error": "rate limited"}),
                    httpx.Response(200, json={"embedding": {"values": raw_vector}}),
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
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    _no_sleep(monkeypatch)
    vectors = [_unit_vector(EMBEDDING_DIMENSIONS, seed=i) for i in range(3)]

    async def _run():
        with respx.mock:
            batch_route = respx.post(
                "https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:batchEmbedContents"
            ).mock(
                side_effect=[
                    httpx.Response(429, json={"error": "rate limited"}),
                    httpx.Response(200, json={"embeddings": [{"values": v} for v in vectors]}),
                ]
            )
            sequential_route = respx.post(
                "https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent"
            )
            results = await call_embeddings_batch(["a", "b", "c"])
            return results, batch_route, sequential_route

    results, batch_route, sequential_route = asyncio.run(_run())
    assert batch_route.call_count == 2
    assert not sequential_route.called
    assert all(not r.degraded for r in results)
    assert len(results) == 3


def test_call_embeddings_batch_returns_in_order_with_one_http_request(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    vectors = {
        "a": _unit_vector(EMBEDDING_DIMENSIONS, seed=3),
        "b": _unit_vector(EMBEDDING_DIMENSIONS, seed=5),
        "c": _unit_vector(EMBEDDING_DIMENSIONS, seed=7),
    }

    async def _run():
        with respx.mock:
            route = respx.post(
                "https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:batchEmbedContents"
            ).mock(
                return_value=httpx.Response(
                    200,
                    json={"embeddings": [{"values": vectors["a"]}, {"values": vectors["b"]}, {"values": vectors["c"]}]},
                )
            )
            results = await call_embeddings_batch(["a", "b", "c"])
            return results, route

    results, route = asyncio.run(_run())
    assert route.call_count == 1  # ceil(3/32) == 1, never one call per text
    assert len(results) == 3
    assert all(r.degraded is False for r in results)
    assert all(len(r.vector) == EMBEDDING_DIMENSIONS for r in results)


def test_call_embeddings_batch_falls_back_to_sequential_on_batch_endpoint_failure(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    single_vector = _unit_vector(EMBEDDING_DIMENSIONS, seed=11)

    async def _run():
        with respx.mock:
            respx.post(
                "https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:batchEmbedContents"
            ).mock(return_value=httpx.Response(500, json={"error": "internal"}))
            sequential_route = respx.post(
                "https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent"
            ).mock(return_value=httpx.Response(200, json={"embedding": {"values": single_vector}}))
            results = await call_embeddings_batch(["x", "y"])
            return results, sequential_route

    results, sequential_route = asyncio.run(_run())
    assert sequential_route.call_count == 2  # one embedContent call per text in the failed group
    assert len(results) == 2
    assert all(r.degraded is False for r in results)


def test_embedding_provider_config_pins_model_and_dimensions():
    entry = EMBEDDING_PROVIDER_CONFIG["google_gemini_embedding"]
    assert entry["model"] == "gemini-embedding-001"
    assert EMBEDDING_DIMENSIONS == 768
