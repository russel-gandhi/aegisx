# AegisX AI — Remediation Plan

**Companion to:** [DIAGNOSIS-REPORT.md](DIAGNOSIS-REPORT.md) and [SYSTEM-DESIGN-DIAGNOSIS.md](SYSTEM-DESIGN-DIAGNOSIS.md) · **Date:** 2026-08-31

Most of the concretely-scoped work from the original version of this plan is done and test-verified. This version drops the item-by-item "here's my proposal" framing for those and records them as closed, so this document stays useful as a plan rather than becoming a diary. What's left is genuinely open — either an architectural decision this document can't make unilaterally, or work blocked on infrastructure/environment that doesn't exist yet.

## Closed this session

| Item | What shipped |
|---|---|
| LLM-router / embedding connection reuse | `app/http_client.py` — shared, pooled `httpx.AsyncClient`, loop-aware caching, closed on shutdown |
| Qdrant client lifecycle | `qdrant_store.get_qdrant_client()` now caches instead of reconstructing per call, mirroring `db.py`'s pool pattern |
| Proactive rate limiting | `app/rate_limiter.py`, enforcing the `rpm_limit` field that existed but was never read |
| Batch-embedding failure amplification | One whole-batch retry before falling back to per-chunk calls, instead of fanning out immediately |
| Event-loop blocking on document upload | `asyncio.to_thread` around the CPU-bound parse/chunk steps |
| Upload idempotency | Content-hash dedup, new migration, `duplicate: true` response field |
| `GET /api/documents` pagination | `limit`/`offset`/`total_count`, single-query via `COUNT(*) OVER()` |
| Stale `NARRATION_CEILING_SECONDS` docstring | Now references the constant, never restates its value |
| `GET /api/systems`, `GET /api/systems/{id}/readiness` | Both implemented; readiness score is the Bible's stored/seeded value, not an invented formula (see below) |
| `POST /api/opa/evaluate` | Implemented as `POST` (documented Bible deviation), gated the same way `list_actions` is |
| `.planning/REQUIREMENTS.md` staleness | 4 checkboxes and 9 traceability rows corrected |

Full detail and reasoning for each is in the two diagnosis reports; this document doesn't repeat it.

---

## Open: the embedding-provider architecture decision

**Status:** genuinely undecided, not merely unbuilt.

The proactive rate limiter and the batch-retry fix both reduce *how often* the hosted embedding provider's rate limit gets hit. Neither changes what happens when it's hit for longer than the retry budget (~7 seconds) allows — that failure mode is still real, and the underlying decision the original diagnosis raised is still open:

- **A. Hosted-only, harder retry/backoff.** Cheapest, but doesn't remove the ceiling — a sufficiently long outage still fails chunks.
- **B. Local embedding fallback**, mirroring `llm_router.py`'s own proven cascade pattern. The real design constraint: a local model's output is a *different vector space* than the hosted one. Two chunks embedded by different models are not comparable by cosine similarity even at the same dimensionality unless the model is bit-for-bit compatible. Fixing this requires either (a) a local model chosen specifically to match the hosted model's dimensionality *and* be usable as a genuine drop-in (rare in practice), or (b) routing to a separate Qdrant collection per embedding source, with `document_chunks` rows tagged by which one embedded them, so retrieval always queries the collection matching a chunk's actual provenance. Option (b) is the safer default if this path is taken.
- **C. Both, behind a provider-abstraction layer** analogous to `PROVIDER_CONFIG`.

**Recommendation:** don't build B or C speculatively. Instrument how often the current retry budget is actually insufficient in real usage first (a log-based count of "batch exhausted all retries and fell back to sequential, which also exhausted its retries" would answer this directly — that log line already exists via `EMBEDDING_BATCH_RETRY_ATTEMPTS`/`EMBEDDING_MAX_RETRIES`'s warning logs), then decide. A local fallback built before that data exists is solving an unmeasured problem with a nontrivial (dual-vector-space) cost.

---

## Open: `POST /api/reports/evidence-pack` — blocked on infrastructure, not code

WeasyPrint requires native GTK/Pango/Cairo libraries. They don't install via `pip` on Windows (confirmed: `pip install weasyprint` succeeds, `import weasyprint` fails with a missing-library error), and **no backend Dockerfile exists anywhere in this repository** to provision them in a Linux container either — the backend currently runs via bare `uvicorn`, with `docker-compose.yml` managing only Postgres/Qdrant/OPA.

**What actually needs to happen, in order:**
1. A backend Dockerfile (doesn't exist yet, needed regardless of this endpoint for any real deployment).
2. WeasyPrint's system packages added to it (`libpango-1.0-0`, `libpangocairo-1.0-0`, `libgdk-pixbuf2.0-0`, `libffi-dev` on Debian-family images — the exact list is in WeasyPrint's own install docs).
3. Only then does implementing the route's logic make sense. That logic itself is straightforward once the dependency exists: reuse the `AssuranceCard` component's exact CLAIM/EVIDENCE/RULE/CONFIDENCE data contract, render it into an HTML template server-side, hand it to WeasyPrint — not a second, independently-drifting report template.

Writing the route's Python now, without a way to run or test it, would mean shipping code with an unverified import at its center. That's worse than not having the route.

---

## Open: golden-path live verification + a real regression guard for it

**Status:** blocked in this environment (no Docker running here), not skipped.

The RAG golden path was live-verified once, on 2026-08-29, before this session's changes. This session's changes to the retrieval/ingestion path (connection lifecycle, retry shape, idempotency, pagination) were deliberately conservative — no change to the retrieval algorithm, ranking, or grounding logic itself — and are covered by the existing mocked test suite with zero regressions. That is not the same claim as "still works end-to-end against a real stack," and this plan doesn't pretend otherwise.

**Two separate things need to happen, and they're not the same task:**
1. **One-time re-verification**: run the same live checks `06.1-VERIFICATION.md` already ran (real upload, real grounded answer, the honest-refusal negative case, the injection-block case) against this session's changes, the first time a Docker environment is available.
2. **A standing regression guard**, since three separate frontend implementers independently skipped the same `<human-check>` step in the same phase — that's a process signal, not three coincidences. A small Playwright (or Cypress) smoke suite covering exactly three flows (document upload UX, Copilot chat rendering, the auto-navigate/deep-link flow), run in CI against a docker-compose'd stack, converts "did a human remember to look" into "did CI actually load a browser and click it." This doesn't need to be a full E2E suite — three flows, not exhaustive coverage.

Neither can be done from this environment. Both are cheap once Docker is available; item 2 in particular is worth doing before more frontend surface gets added, not after.

---

## Open: Copilot navigation-intent verification

**Status:** deliberately not built speculatively, pending the test above.

An imperative command like "show me the blast radius of X" may not score well in retrieval the way a factual question does — there's no document text that *is* the answer to a command. Whether this is an actual gap or already handled depends entirely on a live test that needs the same blocked environment as above: ask the running Copilot that exact phrasing and check whether `navigation_target` comes back populated.

**If the live test finds a real gap**, the fix should be a deterministic, regex-based pre-router ahead of the full retrieval pipeline — pattern-match navigation-imperative phrasing plus a resolvable entity reference, and short-circuit directly to a `NavigationTarget` without an LLM call at all. This isn't a new architectural idea for this codebase: it's the same principle already enforced for C2 (RBAC and injection detection are zero-LLM by design) applied to a UI-navigation decision, which is a routing decision, not a judgment call that needs grounding.

**If the live test finds no gap**, the pre-router becomes a latency/cost optimization, not a correctness fix, and can be prioritized accordingly (i.e., lower).

Building this before running that test risks solving a problem that may not exist, at the cost of new regex-matching logic that itself needs to be gotten right.

---

## Deliberately not done: a document-ingestion state machine

Raised in the original diagnosis, and deliberately left alone. Ingestion is still fully synchronous — one HTTP request does upload through indexing before responding — so there is no window in which a durable `PROCESSING` state would ever be observed by anything. Building `UPLOADED → PROCESSING → PARTIALLY_INDEXED → READY/FAILED` now would be state nothing reads, which is the exact shape of premature abstraction this project's own conventions warn against elsewhere. The trigger condition to revisit this is explicit: the day ingestion moves off the request thread (a size threshold, or the local-embedding fallback above turning out to be slow enough to need it) is the day this needs designing — not before.

---

## Suggested order for what's left

1. Instrument the embedding retry-exhaustion rate (cheap, informs the architecture decision with real data instead of a guess).
2. Stand up a backend Dockerfile — needed for evidence-pack, and for any real deployment regardless of that endpoint.
3. Once Docker is available: re-run the 2026-08-29 live verification against this session's changes, then build the 3-flow Playwright smoke suite before adding more frontend surface.
4. Run the one specific Copilot-navigation live test; let its result decide whether the deterministic pre-router is urgent or a later optimization.
5. Decide the embedding-provider architecture (A/B/C above) once step 1's data exists.
6. Implement `POST /api/reports/evidence-pack` once step 2's Dockerfile exists.
