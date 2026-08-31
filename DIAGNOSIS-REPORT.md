# AegisX AI — Diagnosis Report

**Date:** 2026-08-31 · **Commit base:** `aef6329` + this session's fixes (uncommitted) · **Scope:** multi-LLM routing, document chunking/indexing, API endpoint surface — the three areas originally flagged, re-diagnosed against the current tree after remediation.

## TL;DR

| Area | Status |
|---|---|
| Multi-LLM routing | **Sound.** One real bug (test-suite billed-call leak) found and fixed; one cascade-timeout bug found, fixed, and re-verified; proactive rate limiting added where none existed. |
| Document chunking/indexing (RAG) | **Built and live-verified end-to-end** (2026-08-29, independently of this session). Ingestion hardened this session: idempotent, paginated, no longer blocks the server process. One architectural decision on embedding-provider resilience remains genuinely open. |
| API endpoint surface | **8 of the Bible's 11 endpoints now implemented** (3 added this session). 1 remains genuinely blocked by a missing native dependency; 2 were never scheduled to any phase, now resolved or explicitly triaged. |

---

## 1. Multi-LLM routing

`backend/app/llm_router.py` implements a 4-provider cascade (Gemini → DeepSeek → Groq → OpenRouter) with per-hop timeouts, an inter-hop delay, and degrade-don't-raise semantics. As of this session:

- **Connection reuse**: every call now goes through a shared, pooled `httpx.AsyncClient` (`app/http_client.py`) instead of opening a fresh TCP+TLS connection per request. This applies uniformly to the LLM router, the embedding provider, and the OPA client — one fix, three beneficiaries.
- **Proactive rate limiting**: `app/rate_limiter.py` now enforces the `rpm_limit` each provider entry already declared but that nothing previously read. It sits inside `_send_one()`, the single call site every task routes through, so every caller — including `routes/findings.py`'s concurrent multi-check fan-out — is protected without having been touched individually.
- **Test isolation fixed**: `backend/tests/conftest.py` now has an autouse fixture (`_isolate_llm_provider_keys`) stripping all 5 provider API keys before every test, plus a matching fixture zeroing the rate limiter's history between tests. Running the suite no longer risks firing real, billed provider calls — this was an open, self-acknowledged gap as of the last audit; it's closed now.
- **Stale docstring fixed**: `a2_compliance.py` previously hardcoded "13.0s" in prose describing `NARRATION_CEILING_SECONDS`, which had since been changed to 17.0 in code. The prose now references the constant by name instead of restating its value, so it can't drift out of sync again.

No further issues found in the routing/cascade logic itself. The one still-open item from this area — whether to build a local-embedding fallback behind a provider-abstraction layer mirroring this router's own pattern — is a product decision requiring real measurement, not a code defect; see the companion remediation plan.

---

## 2. Document chunking / indexing (RAG)

This was the most significant correction from the original diagnosis: an earlier pass through this repo found no retrieval pipeline at all. That was accurate for the commit examined at the time, but the tree has since grown a complete implementation (`backend/app/retrieval/`: `embeddings.py`, `hybrid_search.py`, `ingest.py`, `lexical.py`, `qdrant_store.py`, `evaluation.py`), and — more importantly — it has been **live-verified**, not just unit-tested: `.planning/phases/06.1-advanced-retrieval-real-copilot/06.1-VERIFICATION.md` (2026-08-29) recorded a real document upload, real Qdrant vectors, a real grounded answer with populated reranker scores, and — critically — a correctly honest `insufficient_evidence: true` response to an off-topic question, with zero fabrication.

This session hardened the ingestion path further:

- **Event-loop blocking fixed**: PDF/DOCX parsing (genuinely CPU-bound work) now runs via `asyncio.to_thread` instead of executing synchronously inside the `async def` upload handler. Previously, one large upload would stall the entire single-worker process — every other concurrent request, including the WebSocket and health checks — for the duration of that parse.
- **Embedding rate-limit handling improved**: the existing bounded retry-with-backoff for HTTP 429s is now backed by the same proactive rate limiter described above, and a failed embedding batch retries the whole batch once before falling back to per-chunk calls (previously it fanned out to N individual requests on any failure, amplifying load at exactly the moment a provider had already signaled trouble).
- **Upload idempotency added**: a content-hash check (new column + migration, `infra/postgres/initdb/005_documents_content_hash.sql`) means a double-submit or client retry now returns the existing document instead of re-running the full parse→chunk→embed→index pipeline and paying for it twice.
- **Pagination added** to `GET /api/documents`, which previously had no ceiling on result-set size.

**What remains genuinely open, not fixed:** the embedding provider's 429 handling is still a bounded retry, not a circuit breaker or a local fallback — a provider that stays rate-limited past the retry window still fails the affected chunk(s). Building a local-embedding fallback (mirroring the LLM router's own multi-provider pattern) is the natural next step, but it introduces a real design constraint — different embedding models produce incompatible vector spaces, so a fallback needs either a matching-dimension model or per-source Qdrant collections — that needs a deliberate decision, not a quick patch. This is left open in the companion remediation plan rather than guessed at here.

**What remains unverified in this session specifically:** whether the full pipeline still behaves correctly end-to-end after this session's changes. Every change here was verified against the mocked unit/integration test suite (zero regressions against a captured baseline), but this sandbox has no Docker running, so re-running the 2026-08-29 live verification against a real Postgres/Qdrant/Gemini stack was not possible here. The code changes are conservative (connection lifecycle and retry-shape changes, not logic changes to the retrieval algorithm itself), but "the tests still pass" is not the same claim as "re-verified live," and this report says which one it's making.

---

## 3. API endpoint surface

Diffing the Bible's Section 12 API table against what's actually registered (confirmed via the live OpenAPI schema, not just reading route files):

| Method | Path | Status |
|---|---|---|
| GET | `/api/health` | ✅ |
| GET | `/api/systems` | ✅ **added this session** |
| GET | `/api/systems/{id}/readiness` | ✅ **added this session** |
| GET | `/api/systems/{id}/evidence-graph` | ✅ |
| POST | `/api/copilot/query` | ✅ |
| WS | `/api/copilot/stream/{session_id}` | ✅ |
| POST | `/api/actions/{id}/approve` | ✅ |
| GET | `/api/audit/verify` | ✅ |
| POST | `/api/audit/demonstrate-tamper` | ✅ |
| POST | `/api/reports/evidence-pack` | ❌ genuinely blocked (see below) |
| GET | `/api/opa/evaluate` | ✅ **added this session, as `POST`** (documented Bible deviation — a body-carrying `GET` is non-standard HTTP; every other Bible-literalism correction in this codebase follows the same pattern) |

Plus several endpoints the Bible never specified but the product has since grown: `/api/documents` (list + upload), `/api/copilot/investigate`, `/api/systems/{id}/blast-radius`, `/api/systems/{id}/assurance-cards` (+ SSE stream), `/api/systems/{id}/access-supplier-signals`, `/api/actions` (list + reject).

**`GET /api/systems/{id}/readiness`'s honest limitation**: its `score` field reads the `gxp_systems.readiness_score` column directly — the value the Bible's own seed data hardcodes (61 / 94), not a live-recomputed aggregate. The Bible defines `SystemReadinessScore` as `{system_id, score, breakdown}` with no scoring formula anywhere, and inventing one here would be exactly the kind of silently-authored metric this codebase's own conventions warn against elsewhere (Rule 7, "no silent scope expansion"). What IS live-computed is `breakdown["open_findings"]`, a real count from the existing assurance-cards endpoint — genuine signal, not a guess. If a real formula is ever specified, this is where it belongs.

**`POST /api/reports/evidence-pack` — why it's still missing**: the Bible specifies WeasyPrint for PDF generation. WeasyPrint requires native GTK/Pango/Cairo libraries. On this Windows development machine, `pip install weasyprint` succeeds but `import weasyprint` fails outright (`cannot load library 'libgobject-2.0-0'`) — there is no pip-installable path to these libraries on Windows. More importantly, **no backend Dockerfile exists anywhere in this repository** — the backend currently runs via bare `uvicorn`, with docker-compose managing only Postgres/Qdrant/OPA. So there is no environment in this project, dev or otherwise, where this dependency has ever been provisioned or verified to work. Implementing the endpoint's logic (reusing the `AssuranceCard` data contract, per the companion remediation plan) is straightforward; the blocker is infrastructure that doesn't exist yet, not application code.

---

## Bonus: planning-document accuracy (self-reported gap, now closed)

The 2026-08-29 verification report for Phase 06.1 explicitly flagged that `.planning/REQUIREMENTS.md`'s checkboxes and traceability table were never updated for the 9 requirement IDs (`RAG-01`–`RAG-07`, `AGT-01`, `HARD-04`) it had just confirmed satisfied. This was fixed this session: 4 checkboxes corrected, 9 traceability rows added, and the v1 requirement count corrected from 29 to the actual 38. A separate phase-counter inconsistency flagged in an earlier pass through this repo (`.planning/STATE.md` appearing to roll back to "Phase 1" after completing Phase 5) has since resolved itself — the file now correctly tracks Phase `06.1`, 10 total phases, with no intervention needed.

---

## What this report does not claim

This report reflects a codebase with real, applied fixes and a real, re-run test suite (396 passing / 180 failing — every failure attributable to the absence of a live Postgres/Qdrant/OPA stack in this sandbox, not to any change made) and a clean frontend suite (247/247). It does not claim live re-verification of the RAG golden path or the browser-rendered frontend after this session's changes, because no Docker environment was available here to perform that verification. That gap is explicit in the companion remediation plan, not glossed over here.
