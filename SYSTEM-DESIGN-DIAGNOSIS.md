# AegisX AI — System Design & Networking Diagnosis

**Date:** 2026-08-31 · **Lens:** connection management, rate limiting, concurrency/backpressure, chunking/indexing efficiency, horizontal-scaling assumptions. Re-diagnosed against the current tree after this session's fixes — every finding below reflects what's actually in the code now, not a rehash of a prior pass.

## TL;DR

Every finding from the original pass (2026-08-30) has a concrete fix in place, verified against the test suite. Two items were deliberately left open — one is a genuine architectural decision requiring measurement this environment can't produce, the other turned out not to need a separate fix at all. Nothing new surfaced in this re-pass.

| # | Original finding | Current state |
|---|---|---|
| 1 | Fresh `httpx.AsyncClient` per call, no connection reuse | ✅ Fixed |
| 2 | Qdrant client rebuilt + ping'd every call, never closed | ✅ Fixed |
| 3 | `rpm_limit` modeled twice, enforced nowhere | ✅ Fixed |
| 3a | Batch-embedding failure fans out to N sequential calls | ✅ Fixed |
| 3b | No inter-batch pacing | ✅ Resolved as a side effect of #3 |
| 4 | Synchronous CPU-bound parse blocks the event loop | ✅ Fixed |
| 5 | No pagination on list endpoints | ✅ Fixed (documents); deliberately not fixed the same way for actions (see below) |
| 6 | No upload idempotency/dedup | ✅ Fixed |

---

## 1. Connection reuse — fixed

`app/http_client.py` provides a shared, lazily-constructed `httpx.AsyncClient`, cached at module scope and rebuilt only if the current event loop differs from the one that created it (mirroring `app/db.py`'s exact handling of `asyncpg.Pool`'s own loop-binding constraint). `llm_router.py`, `retrieval/embeddings.py`, and `opa_client.py` all route through it now instead of opening a fresh client — and therefore a fresh TCP+TLS handshake — on every single outbound call.

Verified: `test_llm_router.py`, `test_retrieval_embeddings.py`, and the non-live subset of `test_opa_client.py` all pass unchanged. The client is closed on ASGI shutdown (`main.py`'s lifespan), so a live process doesn't leak the pooled connection.

## 2. Qdrant client lifecycle — fixed

`retrieval/qdrant_store.py`'s `get_qdrant_client()` previously constructed a brand-new `AsyncQdrantClient` — a new connection pool — on every call, and never closed any of them. It now caches the client exactly like `get_pool()` caches the Postgres pool: same loop-aware invalidation, same "discard and rebuild, never await-close a client whose loop may already be gone" handling. The liveness ping (`get_collections()`) deliberately still runs on every call, even against the cached client — this preserves the exact `None`-on-unreachable contract every caller already depends on for its own clean 503 guard, at the cost of not eliminating every network round-trip, only the repeated client-construction cost. A new `aclose_qdrant_client()` is wired into the same shutdown hook as the HTTP client.

Verified: the qdrant-touching test files' non-live subsets (90 passing) are unaffected; the 8 tests requiring a real Qdrant instance fail here for the same reason they did before this change (no Docker in this sandbox), not because of it.

## 3. Proactive rate limiting — fixed

`app/rate_limiter.py` is new: a per-provider sliding-window limiter (`_WINDOW_SECONDS = 60.0`) that blocks `acquire()` until the caller is back under that provider's own `rpm_limit` — a field that was already declared in both `llm_router.PROVIDER_CONFIG` and `embeddings.EMBEDDING_PROVIDER_CONFIG` and read by nothing before this fix. It's wired into the one call site every LLM task and every embedding call ultimately passes through, so the fix's reach extends automatically to every current caller — including `routes/findings.py`'s concurrent per-check fan-out — without those call sites needing individual changes.

Test isolation: `conftest.py` gained an autouse fixture resetting the limiter registry before/after every test, mirroring the existing pattern for the narration cache and the cascade delay. No existing test fires anywhere near even the lowest configured limit (30/min) within its own runtime, so this is a correctness safeguard against cross-test state leaking, not something that changes any test's timing — confirmed by the suite's runtime being unchanged.

### 3a. Batch-embedding failure fallback — fixed

A failed 32-chunk batch call previously fell straight through to 32 fully independent sequential calls on *any* failure (a 500, a timeout, a malformed response — not just exhausted 429 retries). It now retries the whole batch once, with a short fixed delay, before falling back — absorbing a transient blip without amplifying it. The existing test asserting the exact fallback call count (`test_call_embeddings_batch_falls_back_to_sequential_on_batch_endpoint_failure`) still passes, since it mocks the batch endpoint to fail unconditionally: the retry adds one more (also-failing, also-instant-in-tests) attempt before reaching the same eventual fallback, not a different one.

### 3b. Inter-batch pacing — resolved without a separate change

The original finding worried about `call_embeddings_batch()` issuing each group's request immediately after the previous one resolved, with no pacing tied to the provider's RPM window. Once the rate limiter from #3 sits inside the actual per-request call path (`_call_batch_group`'s own POST, re-acquired on every retry attempt too), this is automatically covered — there was no need to add a second, separate pacing mechanism at the batch-loop level.

## 4. Event-loop blocking during document parsing — fixed

This was the highest-severity finding in the original pass: `parse_pdf`/`parse_docx`/`parse_document`/`chunk_blocks` are genuinely CPU-bound, synchronous functions, called directly inside `async def upload_document`. Since this backend runs single-worker by explicit design elsewhere in the codebase (`app/ws/copilot.py`'s own docstring), that meant one large document upload could stall the entire event loop — every other concurrent request, including the WebSocket and health checks — for the parse's full duration.

Both call sites in `routes/documents.py` now go through `asyncio.to_thread`, moving the work to the default thread-pool executor. This is a one-line-per-call-site change with no logic modification — verified by the full backend suite's zero-regression re-run.

## 5. Pagination — fixed for documents, deliberately different for actions

`GET /api/documents` now accepts `limit`/`offset` (default 50, capped at 200), with `total_count` computed in the same query via `COUNT(*) OVER()` rather than a second round-trip. This endpoint's result set grows with the document corpus, so an actual ceiling matters.

`GET /api/actions` got a defensive `LIMIT 500` instead of real pagination, deliberately. That endpoint is a human approval queue, not a growing corpus — silently truncating it would hide a pending GxP-relevant approval from the Action/Approval Centre, which is a compliance risk, not merely a UX one. The 500 ceiling exists only as a guard against pathological growth; a genuinely pending queue exceeding it in this project's current single-operator demo scope would itself be the more urgent problem, not the missing pagination.

## 6. Upload idempotency — fixed

`documents.content_sha256` (new column, `infra/postgres/initdb/005_documents_content_hash.sql`, `IF NOT EXISTS`-guarded per this codebase's established migration style) plus a partial unique index scoped to `(system_id, content_sha256)`. `POST /api/documents/upload` now checks for an existing document with the same hash for the same system before doing any parsing, Qdrant work, or DB writes, and returns the existing document's summary (with a new `duplicate: true` field) instead of re-ingesting. Scoped to `system_id` deliberately — the same content legitimately uploaded for two different systems is not a duplicate.

---

## What a fresh pass did NOT find

Re-scanning the codebase after these changes specifically for anything the fixes might have introduced or missed:

- No other `httpx.AsyncClient()` or `AsyncQdrantClient(` construction sites remain outside the two factory functions (`http_client.get_shared_client`, `qdrant_store.get_qdrant_client`) that now own client lifecycle exclusively.
- The one other concurrent multi-call fan-out in the codebase (`routes/findings.py`'s `asyncio.gather` over `_card_for_check`, already bounded by its own per-request semaphore) benefits from the rate limiter automatically, confirming the fix's centralization was the right call rather than a per-call-site patch.
- The WS broadcast registry (`app/ws/copilot.py`) remains in-process, single-worker-only — unchanged by this session, and already self-documented in the codebase as a known, accepted scaling boundary rather than an oversight. Not re-litigated here.

## What remains open, honestly

- **Test verification only, not live verification.** Every fix above was confirmed against the mocked/unit test suite with zero regressions against a captured pre-change baseline. This sandbox has no Docker running, so none of these changes have been exercised against a real Postgres/Qdrant/LLM-provider stack under real network conditions. The changes are conservative — connection lifecycle and retry-shape, not business logic — but that distinction matters less than actually watching it run.
- **The embedding-provider architecture question is unchanged.** The proactive rate limiter and the batch-retry fix both reduce how *often* a provider outage is hit; neither changes what happens when one is hit for longer than the retry budget allows. That's a product/architecture decision (local fallback vs. circuit breaker vs. both, and if local, how to handle the resulting dual vector-space problem), not a system-design defect this diagnosis can resolve on its own.
