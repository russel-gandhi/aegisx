"""
Shared, pooled `httpx.AsyncClient` for every outbound HTTPS call this
backend makes (LLM providers, embedding providers, OPA).

## Why this exists

`llm_router.py`, `retrieval/embeddings.py`, and `opa_client.py` each
previously did `async with httpx.AsyncClient() as client: ...` inside
their per-call send function -- a brand-new client, constructed and torn
down, for every single outbound request (SYSTEM-DESIGN-DIAGNOSIS.md #1).
`httpx.AsyncClient` is explicitly designed to be constructed once and
reused: it owns a connection pool that keeps TCP+TLS state warm across
requests. Discarding it after one call means every call -- including
every hop of `call_llm`'s multi-provider cascade and every group of
`call_embeddings_batch`'s batch loop -- pays a fresh TCP handshake plus a
TLS handshake before a single byte of the real request goes out. That
cost is invisible hitting a provider once; it's a real, avoidable latency
tax on exactly the retry/cascade/batch paths that are already tight on
time budget.

## Why the caching pattern mirrors `app.db.get_pool()`

An `httpx.AsyncClient`'s underlying connection pool holds asyncio
primitives (locks, semaphores) bound to the event loop it was created on,
the same coupling `app.db.get_pool()` already documents at length for
`asyncpg.Pool`. This codebase's test convention runs every test in its
own `asyncio.run()` (a fresh loop per test) -- a client cached across a
loop boundary would either raise or silently misbehave. This module
copies `get_pool()`'s exact fix: track which loop owns the cached client,
discard and rebuild if the current loop doesn't match, never `aclose()` a
client whose owning loop is no longer running (that await would itself
raise on a foreign/closed loop).

## What callers get

`get_shared_client()` returns the same `httpx.AsyncClient` instance for
every call on the same running event loop -- callers pass their own
`timeout=` per request (httpx supports a per-request timeout override
even on a client with no default timeout configured) exactly as they did
with the old per-call client. No calling code's request-building logic
changes; only the client's lifecycle does.

`aclose_shared_client()` is called once from `main.py`'s lifespan
shutdown, mirroring the narration-cache prewarm task's own
lifespan-scoped cleanup -- so a live process doesn't leak the pooled
connections on shutdown, and so `pytest` runs (which never enter the ASGI
lifespan per `main.py`'s own docstring) never need to call it at all.
"""

import asyncio
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

_client: Optional[httpx.AsyncClient] = None
_client_loop: Optional[asyncio.AbstractEventLoop] = None


def get_shared_client() -> httpx.AsyncClient:
    """Lazily create and return the module-level singleton
    `httpx.AsyncClient`, rebuilding it if the current running event loop
    differs from the one that created the cached instance (see module
    docstring)."""
    global _client, _client_loop
    current_loop = asyncio.get_running_loop()
    if _client is not None and _client_loop is not current_loop:
        # Never await aclose() here: the loop that owns this client may
        # already be closed (the exact case get_pool() guards against for
        # asyncpg) -- awaiting anything on it would raise instead of
        # cleanly discarding a reference we're replacing anyway.
        _client = None
        _client_loop = None
    if _client is None:
        _client = httpx.AsyncClient()
        _client_loop = current_loop
    return _client


async def aclose_shared_client() -> None:
    """Close the cached client, if one exists on the current loop.

    Safe to call when no client has ever been created (module-level
    default is `None`) and safe to call more than once."""
    global _client, _client_loop
    if _client is not None:
        await _client.aclose()
        _client = None
        _client_loop = None
