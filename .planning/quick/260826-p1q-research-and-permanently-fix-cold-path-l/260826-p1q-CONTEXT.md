# Quick Task 260826-p1q: Research and permanently fix cold-path latency of A2's LLM narration synthesis - Context

**Gathered:** 2026-08-26
**Status:** Ready for planning

<domain>
## Task Boundary

Research and permanently fix the cold-path latency of A2's LLM narration synthesis (`narrate_gap()` in `backend/app/agents/a2_compliance.py`, called from `get_assurance_cards()` in `backend/app/routes/findings.py`, plus its other call sites in `run_a2` and `routes/actions.py::_find_finding_server_side`).

This is explicitly NOT about the caching layer (`backend/app/narration_cache.py`, already merged) — that correctly handles repeat requests for an unchanged finding. This is about what happens the FIRST time a finding needs narration: today that's 18-50s wall-clock for 2-3 findings because of a sequential loop plus a two-hop provider cascade.

Must NOT touch C1's `verify_finding()` semantics, confidence grading, or any deterministic compliance logic. LLM narration remains decoration on top of an already-established deterministic fact — never a source of truth — and its speed must never change a confidence grade or pass/fail outcome.

</domain>

<decisions>
## Implementation Decisions

### Blocking vs. streaming UX
- Stream per-card: deterministic fields (confidence, pass/fail, evidence, citations) render immediately per card as each one's narration completes; the page must never block on the slowest finding. Requires a streaming transport (SSE or reuse the existing `/api/copilot/stream/{session_id}` WebSocket pattern) instead of the current single blocking JSON response. Research should evaluate SSE vs. reusing the existing WebSocket infrastructure and recommend whichever fits this codebase's conventions best — this is Claude's discretion on the transport mechanism specifically, the streaming-per-card *behavior* itself is locked.

### Provider/model choice for narration
- Switch A2 narration specifically to Groq as the primary provider (confirmed ~1-2s response time this session, no quota issues observed, still genuine LLM-authored prose — not a downgrade in explainability). A0 orchestration and A7 remediation keep their existing Gemini/DeepSeek providers unchanged — this is a narration-only routing change.
- The existing cascade-on-failure behavior must be preserved: if Groq fails/times out/errors, fall back through the existing chain (or an equivalent), never crash or block indefinitely.
- Research should confirm Groq's `openai/gpt-oss-120b` (or whichever current Groq model this session's earlier LLM-router fix landed on) is suitable for this narration prompt shape before locking it in, and should check `llm_router.py`'s `PROVIDER_CONFIG`/`select_provider()` design to determine the cleanest way to give A2 narration its own provider preference without disrupting A0/A7's existing task-based routing.

### Pre-computation / background warming
- On backend startup, fire off a background task that narrates every currently-failing check for both seeded demo systems (GXP-MFG-DEMO-01, BUS-IT-DEMO-02), populating `narration_cache` before any human loads the page. A real user's first request should then almost always be a cache hit.
- This must be a genuine background task (non-blocking startup, e.g. FastAPI `BackgroundTasks` or a spawned asyncio task on the `startup` event) — it must NOT delay `/api/health` or make the server slow to become ready.
- Research should determine the right FastAPI-idiomatic mechanism given this project's existing app startup wiring in `backend/app/main.py`.

### Latency budget / timeout policy
- Tighten the per-attempt narration timeout to roughly 3 seconds (down from the current 10s default in `call_llm()`), and fall back to the deterministic template sentence (`_deterministic_gap_sentence`) immediately if exceeded, rather than waiting out a slow/hanging provider.
- This timeout change should be scoped to the narration call specifically if `call_llm()`'s `timeout` parameter is already per-call-configurable (confirm this in research) — do not silently shrink A0/A7's timeouts as a side effect unless research finds a reason all three should share the same tighter budget.

</decisions>

<specifics>
## Specific Ideas

- Live numbers gathered this session, for research to use as a baseline: direct Gemini `gemini-3.6-flash` call ~2.8s; direct OpenRouter/DeepSeek fallback call ~3s; Groq `openai/gpt-oss-120b` call succeeded quickly in this session's earlier testing (exact timing not captured, worth re-benchmarking).
- `llm_router.py`'s `PROVIDER_CONFIG` currently keys providers by task name (`"compliance"` maps to `gemini_flash_fast`) via `select_provider(task)`, which raises `KeyError` on an unmapped task rather than silently defaulting — any provider reassignment for narration should go through this same mechanism, not a special-cased bypass.
- The existing caching work (`.planning/quick/260826-0b5-.../260826-0b5-PLAN.md` and its SUMMARY) already mapped all 3 call sites of `narrate_gap()` and the pitfalls of module-global state in tests (autouse fixture pattern) — the executor for this task should read that PLAN/SUMMARY before touching the same files again, to avoid re-deriving what's already documented.

</specifics>

<canonical_refs>
## Canonical References

No external specs — requirements fully captured in decisions above. Internal reference: `.planning/quick/260826-0b5-cache-a2-s-llm-narration-output-for-assu/260826-0b5-PLAN.md` and its `-SUMMARY.md` (prior quick task, same narration path, caching layer).

</canonical_refs>
