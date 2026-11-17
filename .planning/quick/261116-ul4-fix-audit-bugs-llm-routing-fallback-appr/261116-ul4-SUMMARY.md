---
quick_id: 261116-ul4
slug: fix-audit-bugs-llm-routing-fallback-appr
status: complete
date: 2026-11-17
branch: bugFix
---

# Quick Task 261116-ul4 — Summary

Fixes for the bugs found by the 2026-11-16 audit. Planned and executed inline
in one session (no planner/executor subagents), with the plan in
`261116-ul4-PLAN.md`.

## What was wrong, and what changed

### LLM routing ("everything falls back to deterministic-fallback")

| Cause | Fix | Where |
|---|---|---|
| A HALF_OPEN circuit-breaker probe that was cancelled, got a 4xx/5xx, a missing key or an unusable body was never resolved; the provider stayed skipped until restart | Every outcome resolves the probe (`release_probe`, `record_probe_failure`); cancellation releases it; an abandoned probe is reclaimed after 90s | `circuit_breaker.py`, `llm_router.py` |
| A low live "remaining tokens" reading was trusted for 120s and its reset time never consulted | The reading expires at the provider's reset and refills linearly toward `tpm_limit` before it | `rate_limiter.py` |
| A 429's cooldown used `x-ratelimit-reset-tokens` (time to a full bucket, 59s) instead of `Retry-After` (3s) | `Retry-After` wins; the shorter reset header is the fallback | `llm_router.py` |
| Ollama was first hop for seven tasks; A0's 2000ms budget could not be met | Hosted-first. Tasks split over three Groq models with independent 8,000 tokens/min buckets; Ollama is a later hop; OpenRouter last | `llm_router.py` |
| The cascade skipped by provider, so three Groq entries would have counted as one | Skips by entry key; skips a provider only on a missing key or 401/402/403 | `llm_router.py` |
| A0 inherited a 10s per-hop timeout inside a 2s ceiling | 1.5s per hop | `a0_orchestrator.py` |
| A non-JSON 2xx body raised out of `call_llm`; an empty completion was returned as a successful blank answer | Both are cascadable failures | `llm_router.py` |
| Only A2 cached narrations; every assurance-card read re-narrated A3-A6 | A3-A6 memoized through `narration_cache`; the startup pre-warm covers them (`AEGISX_PREWARM_NARRATION=0` disables it) | `minimal_specialists.py`, `prewarm.py` |
| `GET /api/systems/{id}/readiness` ran the whole narrating fan-out to count findings | Counts from the deterministic checks only | `routes/findings.py`, `routes/systems.py` |
| The Copilot evidence path accepted a blank answer | Rejected, falls back honestly | `routes/copilot_query.py` |

### Deterministic-path and security defects

| Defect | Fix | Where |
|---|---|---|
| Approve/reject was check-then-act, and its audit write was a separate transaction | One conditional `UPDATE ... WHERE status = 'PENDING_APPROVAL'` in the same transaction as the audit event | `routes/actions.py`, `audit_trail.py` |
| C2 missed the most common jailbreak wording (one word off the Bible literal) and similar variants; flagged ordinary URLs as high-entropy | Bible pattern kept first, four narrow patterns added; URL tokens entropy-checked per segment | `agents/c2_gateway.py` |
| A `FAILED` upload blocked re-uploading the same bytes forever | Re-ingested in place; a racing duplicate INSERT returns 409 | `routes/documents.py` |
| Assurance-card routes and the evidence-pack export had no identity; an Auditor could read A3-A6 findings | Identity required, card sources filtered through `PERMISSION_MATRIX` | `routes/findings.py`, `routes/reports.py` |
| `db.py` logged the full DSN including the password | `redact_dsn` | `db.py` |

### Frontend

`tsc -b` exited 2 on four stale test fixtures; fixed. `CommandCentre.test.tsx`
left `fetchSystems` unmocked, so its percentages depended on whether a dev
backend was running; now mocked.

## Verification

- Backend, full `pytest` against live Postgres/Qdrant/OPA: 827 passed, 0
  failed (baseline before this task: 719 passed, 3 failed — the 3 were the
  uncached A3-A6 narration bug). 108 tests added.
- `opa test /policies`: 42/42.
- Frontend: `tsc -b` exit 0; vitest 242/242.
- Live, real providers (Groq key from `.env`, no Ollama, no OpenRouter key):
  - Before: four back-to-back fan-outs; A0 timed out at 2.00s on the first;
    the fourth had 3 of 6 narrations and the answer on `deterministic-fallback`.
  - After: seven back-to-back fan-outs in ~16s, 0 of 42 narrations fell back,
    every answer from a model; A0 classified every time (0.3-1.1s).
  - `POST /api/copilot/investigate` end to end (real Postgres, OPA, Groq):
    six requests, 0 fallback findings, 0.4-3.6s each.

## Deviations recorded

`backend/README.md` Deviation 16 (hosted-first, three Groq models) and
Deviation 17 (C2 patterns). Bible Sections 8.1/8.2 and 2 (C2) are NOT edited
to match — routed to SENT-7-05.

## Not done / still open

- Bible reconciliation for the two deviations above.
- `.env.example` was not updated (it could not be read in this session):
  it should document `AEGISX_PREWARM_NARRATION`.
- Embeddings still require local Ollama (`nomic-embed-text`); without it,
  retrieval and document indexing fail. Not changed here.
- Groq's free tier also caps requests per day (1,000 per model) and output
  tokens per minute on `qwen/qwen3.8-27b` (1,000). The limiter pre-checks
  neither; both surface as real 429s and are handled by the cascade.
- LLM narrations can add detail the deterministic check did not establish
  (one live answer said a record was "lacking a required signature"). The
  claim text is decoration over a verified fact, but it is shown to users.
- Not re-reviewed in this task: ingestion/chunking, suppliers, trust centre,
  most frontend components.
