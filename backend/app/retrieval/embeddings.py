"""
Hosted embedding provider router extension (Phase 06.1, plan 06.1-01, D-03).

Ticket: n/a (roadmap phase 06.1) | Requirements: RAG-01, RAG-02
Source: AegisX-AI-Project-Bible-v6.md's Qdrant schema comment (line 1260,
"768 dimensions for text-embedding-004 equivalent, cosine distance") and
Bible Section 15's hybrid-retrieval spec, which the literal schema comment
predates.

This module mirrors `app.llm_router`'s structure (`PROVIDER_CONFIG` shape,
`_resolve_api_key()` reused verbatim -- imported, not re-implemented --
and the degrade-don't-raise caller contract) WITHOUT forking it: it is a
sibling module for the embedding request/response shape, not a copy of the
text-completion router. `app/llm_router.py` itself is untouched by this
plan; plan 06.1-03 owns that file.

Deviation 14: the Bible's text-embedding-004 (line 1260) is deprecated;
gemini-embedding-001 with output_dimensionality=768 preserves the Bible's
literal 768-dim/cosine requirement. [CITED: ai.google.dev/gemini-api/docs/
embeddings, per 06.1-RESEARCH.md Pitfall 7 -- this repo's Deviations
4/5/6/10/11/12 (backend/README.md, `app/llm_router.py`) each record a
trained-knowledge model id going stale by implementation time; this is the
same class of correction.]

Response shape handling: the Gemini `embedContent` endpoint has shipped
both a singular `{"embedding": {"values": [...]}}` shape and a
`{"embeddings": [{"values": [...]}]}` list shape across documented API
versions. `call_embedding()` reads the singular key first and falls back
to the list shape when the first is absent, so either live response shape
is handled without a second code path per caller.

`gemini-embedding-001` does not auto-normalise a truncated (non-default,
768-dim) output vector -- unlike the newer `gemini-embedding-2` model --
so every vector this module returns is L2-normalised with `numpy` before
being handed to the caller.

Never raises to its caller: every failure path (missing key, timeout,
non-2xx status, malformed response body) returns a degraded
`EmbeddingResponse` instead, matching `call_llm()`'s documented contract.
Never logs the API key, the full request body, or the embedded text --
only the task name, provider entry, and failure category.
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional

import httpx
import numpy as np
from pydantic import BaseModel

from app.llm_router import _resolve_api_key

logger = logging.getLogger(__name__)

EMBEDDING_DIMENSIONS: int = 768
EMBEDDING_BATCH_SIZE: int = 32

# Deviation 19 (backend/README.md, 2026-08-29): bounded retry-with-backoff
# specifically for HTTP 429 (rate limited), added after a real ~105-chunk
# document reliably tripped the hosted embedding API's rate limit and
# `index_document()`'s all-or-nothing write (correct-by-design, D-09 --
# never a partial/fabricated index) discarded every already-embedded chunk
# as a result. 429 is the one status this module already returns that is
# specifically "try again shortly," not "this request is wrong" -- every
# other status/error path is unchanged (no retry, degrade immediately).
# Three retries at 1s/2s/4s (respecting a `Retry-After` header when the
# provider sends one, which caps rather than replaces the backoff) keeps
# the common transient-burst case working without turning a genuinely
# exhausted quota into a long hang.
EMBEDDING_MAX_RETRIES: int = 3
EMBEDDING_RETRY_BASE_DELAY_SECONDS: float = 1.0


def _retry_delay_seconds(attempt: int, response: httpx.Response) -> float:
    """Delay before retry attempt `attempt` (1-indexed). A `Retry-After`
    header (seconds, per RFC 9110) is the provider's own authoritative
    instruction and is honored as-is when present and parseable as a
    non-negative float; our own exponential backoff (1s/2s/4s) is only a
    fallback for the common case where the provider sends none."""
    retry_after = response.headers.get("retry-after")
    if retry_after is not None:
        try:
            header_delay = float(retry_after)
            if header_delay >= 0:
                return header_delay
        except ValueError:
            pass
    return EMBEDDING_RETRY_BASE_DELAY_SECONDS * (2 ** (attempt - 1))

# Mirrors `llm_router.PROVIDER_CONFIG`'s key structure exactly (provider,
# model, base_url, api_key_env tuple, rpm_limit, use_for) so this module
# reads as an extension of the same pattern, not a new one.
EMBEDDING_PROVIDER_CONFIG: Dict[str, Dict[str, Any]] = {
    "google_gemini_embedding": {
        "provider": "google",
        "model": "gemini-embedding-001",
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
        "api_key_env": ("GEMINI_API_KEY", "GOOGLE_API_KEY"),
        "rpm_limit": 100,
        "use_for": ["embed_document", "embed_query"],
    }
}

# Maps the Google-specific `taskType` request-body value (this module's own
# `task_type` parameter) to the EMBEDDING_PROVIDER_CONFIG `use_for` task
# name `select_embedding_provider()` selects on -- these are two distinct
# vocabularies (Google's API enum vs. this router's own provider-selection
# key), kept separate exactly as `llm_router.py`'s `task` argument is
# separate from any per-provider request field.
_TASK_TYPE_TO_PROVIDER_TASK: Dict[str, str] = {
    "RETRIEVAL_DOCUMENT": "embed_document",
    "RETRIEVAL_QUERY": "embed_query",
}


class EmbeddingResponse(BaseModel):
    vector: List[float]
    model_id: str
    provider: str
    degraded: bool = False
    failure_reason: Optional[str] = None


def select_embedding_provider(task: str) -> str:
    """Return the single `EMBEDDING_PROVIDER_CONFIG` key whose `use_for`
    list contains `task`.

    Mirrors `llm_router.select_provider()`'s fail-loud `KeyError` for a
    direct caller of this function. `call_embedding()`/
    `call_embeddings_batch()` still catch that `KeyError` themselves and
    degrade rather than raise, per this module's own never-raise
    contract -- the loud failure here is for a caller of this selector
    function directly, not for the embedding entry points.
    """
    for key, entry in EMBEDDING_PROVIDER_CONFIG.items():
        if task in entry["use_for"]:
            return key
    raise KeyError(f"No EMBEDDING_PROVIDER_CONFIG entry has {task!r} in its use_for list")


def _degraded(reason: str) -> EmbeddingResponse:
    return EmbeddingResponse(vector=[], model_id="", provider="", degraded=True, failure_reason=reason)


def _l2_normalize(values: List[float]) -> List[float]:
    array = np.asarray(values, dtype=np.float64)
    norm = float(np.linalg.norm(array))
    if norm == 0.0:
        return array.tolist()
    return (array / norm).tolist()


def _resolve_entry(task_type: str) -> "tuple[Optional[str], Optional[Dict[str, Any]], Optional[EmbeddingResponse]]":
    """Shared entry-selection + key-resolution step for both the single
    and batch call paths. Returns `(entry_key, entry, None)` on success or
    `(None, None, degraded_response)` on any selection/key failure -- the
    caller returns the third element directly without raising."""
    provider_task = _TASK_TYPE_TO_PROVIDER_TASK.get(task_type, task_type)
    try:
        entry_key = select_embedding_provider(provider_task)
    except KeyError as exc:
        return None, None, _degraded(str(exc))

    entry = EMBEDDING_PROVIDER_CONFIG[entry_key]
    api_key = _resolve_api_key(entry)
    if api_key is None:
        return None, None, _degraded("no API key configured")
    return entry_key, entry, None


async def call_embedding(
    text: str, task_type: str = "RETRIEVAL_DOCUMENT", timeout: float = 10.0
) -> EmbeddingResponse:
    """Embed a single text via the configured hosted embedding provider.

    Never raises to its caller -- see module docstring. On success,
    returns a `degraded=False` response whose `vector` is L2-normalised
    and has exactly `EMBEDDING_DIMENSIONS` entries.

    A `429` response retries up to `EMBEDDING_MAX_RETRIES` times with
    backoff (Deviation 19) before degrading -- every other failure
    (timeout, non-429 status, transport error, malformed body) degrades
    on the first attempt, unchanged.
    """
    entry_key, entry, failure = _resolve_entry(task_type)
    if failure is not None:
        return failure
    assert entry_key is not None and entry is not None  # narrows for type checkers

    api_key = _resolve_api_key(entry)
    url = f"{entry['base_url']}/models/{entry['model']}:embedContent"
    body = {
        "taskType": task_type,
        "content": {"parts": [{"text": text}]},
        "output_dimensionality": EMBEDDING_DIMENSIONS,
    }

    attempt = 1
    try:
        while True:
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        url, params={"key": api_key}, json=body, timeout=timeout
                    )
                    response.raise_for_status()
                    data = response.json()
                break
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 429 and attempt <= EMBEDDING_MAX_RETRIES:
                    delay = _retry_delay_seconds(attempt, exc.response)
                    logger.warning(
                        "Embedding call rate-limited (provider=%s, attempt=%d/%d); "
                        "retrying in %.1fs.",
                        entry_key, attempt, EMBEDDING_MAX_RETRIES, delay,
                    )
                    await asyncio.sleep(delay)
                    attempt += 1
                    continue
                raise
    except httpx.TimeoutException:
        logger.warning("Embedding call timed out (provider=%s, task_type=%s).", entry_key, task_type)
        return _degraded(f"timeout:{entry_key}")
    except httpx.HTTPStatusError as exc:
        logger.warning(
            "Embedding call failed (provider=%s, status=%s).", entry_key, exc.response.status_code
        )
        return _degraded(f"http_{exc.response.status_code}:{entry_key}")
    except httpx.RequestError as exc:
        logger.warning("Embedding call failed (provider=%s): %s", entry_key, type(exc).__name__)
        return _degraded(f"request_error:{entry_key}")
    except ValueError:
        # response.json() raises json.JSONDecodeError (a ValueError
        # subclass) on a non-2xx-passing but non-JSON/empty body -- a
        # malformed response is exactly as unusable to the caller as a
        # transport failure, so it degrades the same way rather than
        # propagating (mirrors _call_batch_group's own ValueError guard).
        logger.warning("Embedding response was not valid JSON (provider=%s).", entry_key)
        return _degraded(f"invalid_json_response:{entry_key}")

    try:
        values = data["embedding"]["values"]
    except (KeyError, TypeError):
        try:
            values = data["embeddings"][0]["values"]
        except (KeyError, IndexError, TypeError):
            logger.warning("Embedding response missing expected shape (provider=%s).", entry_key)
            return _degraded(f"unexpected_response_shape:{entry_key}")

    return EmbeddingResponse(
        vector=_l2_normalize(values),
        model_id=entry["model"],
        provider=entry["provider"],
        degraded=False,
        failure_reason=None,
    )


async def _call_batch_group(
    texts: List[str], task_type: str, timeout: float
) -> List[EmbeddingResponse]:
    """Embed one group of at most `EMBEDDING_BATCH_SIZE` texts via a single
    `:batchEmbedContents` request. A `429` response retries up to
    `EMBEDDING_MAX_RETRIES` times with backoff (Deviation 19) before
    falling back. On any OTHER failure (transport, non-429 status, or a
    malformed/mismatched-length response), or on 429-retry exhaustion,
    falls back to sequential `call_embedding()` calls for this group --
    each of which gets its own independent 429-retry budget -- never
    raises."""
    entry_key, entry, failure = _resolve_entry(task_type)
    if failure is not None:
        return [failure for _ in texts]
    assert entry_key is not None and entry is not None

    api_key = _resolve_api_key(entry)
    url = f"{entry['base_url']}/models/{entry['model']}:batchEmbedContents"
    body = {
        "requests": [
            {
                "model": f"models/{entry['model']}",
                "content": {"parts": [{"text": text}]},
                "taskType": task_type,
                "output_dimensionality": EMBEDDING_DIMENSIONS,
            }
            for text in texts
        ]
    }

    try:
        attempt = 1
        while True:
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        url, params={"key": api_key}, json=body, timeout=timeout
                    )
                    response.raise_for_status()
                    data = response.json()
                break
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code == 429 and attempt <= EMBEDDING_MAX_RETRIES:
                    delay = _retry_delay_seconds(attempt, exc.response)
                    logger.warning(
                        "Batch embedding call rate-limited (provider=%s, attempt=%d/%d); "
                        "retrying in %.1fs.",
                        entry_key, attempt, EMBEDDING_MAX_RETRIES, delay,
                    )
                    await asyncio.sleep(delay)
                    attempt += 1
                    continue
                raise
        embeddings = data["embeddings"]
        if len(embeddings) != len(texts):
            raise ValueError("batch response length does not match request length")
        return [
            EmbeddingResponse(
                vector=_l2_normalize(item["values"]),
                model_id=entry["model"],
                provider=entry["provider"],
                degraded=False,
                failure_reason=None,
            )
            for item in embeddings
        ]
    except (
        httpx.TimeoutException,
        httpx.HTTPStatusError,
        httpx.RequestError,
        KeyError,
        ValueError,
        TypeError,
        IndexError,
    ) as exc:
        logger.warning(
            "Batch embedding call failed (provider=%s): %s. Falling back to %d sequential call(s).",
            entry_key,
            type(exc).__name__,
            len(texts),
        )
        return [await call_embedding(text, task_type=task_type, timeout=timeout) for text in texts]


async def call_embeddings_batch(
    texts: List[str], task_type: str = "RETRIEVAL_DOCUMENT", timeout: float = 30.0
) -> List[EmbeddingResponse]:
    """Embed `texts` in input order, chunking into `EMBEDDING_BATCH_SIZE`
    groups and issuing one `:batchEmbedContents` request per group (i.e.
    `ceil(len(texts) / EMBEDDING_BATCH_SIZE)` HTTP requests on the happy
    path, not one per text). Never raises -- see `_call_batch_group()`'s
    per-group fallback.
    """
    results: List[EmbeddingResponse] = []
    for start in range(0, len(texts), EMBEDDING_BATCH_SIZE):
        group = texts[start : start + EMBEDDING_BATCH_SIZE]
        results.extend(await _call_batch_group(group, task_type, timeout))
    return results
