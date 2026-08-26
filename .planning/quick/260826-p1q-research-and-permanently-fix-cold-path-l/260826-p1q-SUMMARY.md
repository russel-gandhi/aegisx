---
phase: quick
plan: 260826-p1q
subsystem: api
tags: [llm-router, groq, sse-streaming, asyncio-concurrency, narration-cache, fastapi-lifespan, assurance-cards]

requires:
  - phase: 05-safety-remediation
    provides: A2 compliance agent (narrate_gap, A2_CHECKS), assurance-cards route, generate-capa route, action-proposal routes
  - phase: quick/260826-0b5
    provides: app/narration_cache.py content-addressed memo cache, autouse test-isolation fixture
provides:
  - "llm_router.py: dedicated 'narration' task key routed to groq_llama, with Groq-specific reasoning_effort/max_completion_tokens tuning and null-content coercion for reasoning-model truncation"
  - "narrate_gap(): asyncio.wait_for(3.0) total wall-clock ceiling with immediate deterministic-sentence fallback on timeout, degradation, or blank text"
  - "app/routes/findings.py: _card_for_check shared unit; concurrent asyncio.gather blocking route (order-preserving); new GET .../assurance-cards/stream SSE sibling route (asyncio.as_completed, completion order)"
  - "app/routes/actions.py: _find_finding_server_side compares finding_id_for_check BEFORE narrating -- at most one narration call per generate-capa request"
  - "app/agents/a2_compliance.py: finding_id_for_check() shared derivation, used by both build_finding and _find_finding_server_side so the two cannot drift"
  - "app/prewarm.py: directly-testable prewarm_narration_cache(), sequential across both seeded demo systems"
  - "app/main.py: lifespan context manager scheduling the pre-warm without awaiting it, preserving TestClient's pytest-inert lifespan behavior"
  - "frontend/src/lib/api.ts: streamAssuranceCards() -- fetch + body.getReader() SSE client honouring identityHeaders()"
  - "frontend/src/pages/FindingInvestigation.tsx: incremental card rendering with AbortController-based cancellation on system switch"
affects: [findings-route, actions-route, a2-compliance-agent, llm-router, backend-test-suite, finding-investigation-page]

actuals:
  tokens: 20054
  tasks: 3
  commits: 3

tech-stack:
  added: []
  patterns:
    - "Total wall-clock ceiling via asyncio.wait_for wrapping an already-cascading call, rather than shrinking the per-attempt timeout -- preserves the router's internal cascade semantics while still bounding worst-case latency"
    - "Extract-then-fan-out: a single _card_for_check coroutine is the one place check->narrate->build->verify is assembled; both the blocking route (asyncio.gather, input order) and the streaming route (asyncio.as_completed, completion order) call the identical coroutine so the two paths cannot drift on grading logic"
    - "Compare-before-narrate: deriving a finding_id from check_result alone (no LLM call needed) lets a server-side re-derivation loop skip narrating checks that were never going to match, cutting a generate-capa request from up to N narration calls to at most 1"
    - "Lifespan-scheduled background task, never awaited before yield -- the ASGI startup-complete message (and therefore any readiness probe) is structurally guaranteed to precede a background task's completion, not just conventionally expected to"
    - "SSE via bare StreamingResponse + fetch()/body.getReader(), not EventSource -- chosen specifically to preserve the identityHeaders() convention EventSource cannot support, ahead of an anticipated RBAC extension to this route"

key-files:
  created:
    - backend/app/prewarm.py
    - backend/tests/test_prewarm.py
  modified:
    - backend/app/llm_router.py
    - backend/app/agents/a2_compliance.py
    - backend/app/routes/findings.py
    - backend/app/routes/actions.py
    - backend/app/main.py
    - backend/tests/test_narration_cache.py
    - backend/tests/test_a2_compliance.py
    - backend/tests/test_hero_tracer.py
    - backend/tests/test_hero_loop.py
    - backend/tests/test_routes_findings.py
    - backend/tests/test_routes_actions.py
    - frontend/src/lib/api.ts
    - frontend/src/pages/FindingInvestigation.tsx

key-decisions:
  - "asyncio.wait_for(3.0) wraps the whole call_llm() invocation rather than shrinking call_llm's own timeout parameter -- call_llm reuses its timeout for the internal OpenRouter cascade attempt, so a raw timeout=3.0 would allow a ~6s worst case; the outer wait_for is the real ceiling and deliberately means a Groq TIMEOUT gets no cascade attempt (a 3s budget is a 3s budget), while a Groq FAST failure (missing key/429/5xx) still cascades normally inside the remaining budget"
  - "reasoning_effort='low' + max_completion_tokens=512 gated strictly on entry['provider']=='groq' -- OpenRouter shares the same request builder and may reject an unrecognized field; 512 is a generous floor, not a tight cap, because gpt-oss-120b's reasoning tokens count against this budget and a tight cap risks finish_reason='length' with null content"
  - "SSE via StreamingResponse + fetch()/body.getReader(), not the existing /api/copilot/stream WebSocket and not EventSource -- the WebSocket is a documented session-agnostic broadcast bus (wrong scope for a system-scoped card stream), and EventSource cannot set the identityHeaders() this codebase's convention requires on every GET"
  - "The blocking route keeps asyncio.gather (input order) rather than switching to as_completed, preserving byte-identical card ordering for its eleven existing call sites; only the new streaming route uses as_completed, because there completion order is the entire point"
  - "finding_id_for_check() extracted as a shared helper used by both build_finding and _find_finding_server_side, rather than re-deriving the finding_id format string in two places -- makes the two structurally unable to drift apart"
  - "Pre-warm stays strictly sequential (not gather'd) across both demo systems' checks -- the asyncpg pool caps at max_size=5, and a concurrent pre-warm racing a live request's own 4-way fan-out could push connection demand past that cap and start blocking on the pool's 5.0s acquire timeout; the pre-warm has no latency requirement of its own, so it yields the concurrency budget to real requests"
  - "Lifespan schedules the pre-warm via asyncio.create_task and yields immediately without awaiting it -- this is what structurally (not just conventionally) guarantees /api/health is never delayed, and the existing test-safety property (TestClient's session-scoped client fixture never enters `with client:`, so the lifespan protocol never runs under pytest) was preserved rather than 'fixed'"

patterns-established:
  - "Narration-path respx mock sweep discipline: switching a provider requires three coordinated changes per test site (endpoint URL, env var key name, response body shape) -- the key-name miss is the silent failure mode, since _send_one raises _MissingKeyError before any HTTP call, so an unswept mock produces a passing-looking test that never actually exercised the real code path"
  - "Guard-before-generator for any future StreamingResponse route: HTTPException guards (404/503) must run in the route function body, above the generator, never inside it -- once the 200 status line is committed, a later raise produces a torn response, not a real error status"

requirements-completed: [EVID-03, ORC-03]

coverage:
  - id: D1
    description: "A2 narration is routed to Groq via a dedicated 'narration' task key while every other task mapping (compliance, orchestrator, synthesis, remediation, risk_assessment, incident, access, high_volume, fallback) resolves exactly as before"
    requirement: "ORC-03"
    verification:
      - kind: unit
        ref: "backend/app/llm_router.py select_provider() routing assertions (python -c smoke check, all 9 task keys)"
        status: pass
      - kind: unit
        ref: "backend/tests/test_llm_router.py (untouched, still passing -- proof the routing change was surgical)"
        status: pass
    human_judgment: false
  - id: D2
    description: "narrate_gap() bounds total wall-clock time to ~3s via asyncio.wait_for, falling back to the deterministic sentence on timeout, degradation, or blank/whitespace text, and never caching any of the three"
    requirement: "ORC-03"
    verification:
      - kind: unit
        ref: "backend/tests/test_narration_cache.py, backend/tests/test_a2_compliance.py (Groq-mocked success/degraded/blank-text paths)"
        status: pass
    human_judgment: false
  - id: D3
    description: "GET .../assurance-cards runs its four checks concurrently via asyncio.gather with input-order preserved (byte-identical to the prior sequential loop), and GET .../assurance-cards/stream is a new SSE sibling route streaming one card frame per failing check (completion order) plus exactly one terminal frame"
    requirement: "EVID-03"
    verification:
      - kind: integration
        ref: "backend/tests/test_routes_findings.py#test_integration_stream_gxp_demo_yields_two_card_frames_then_one_terminal_frame"
        status: pass
      - kind: integration
        ref: "backend/tests/test_routes_findings.py#test_negative_stream_unknown_system_returns_404_as_a_real_status_not_an_error_frame"
        status: pass
      - kind: integration
        ref: "backend/tests/test_routes_findings.py#test_edge_stream_postgres_unreachable_returns_503_as_a_real_status_not_an_error_frame"
        status: pass
    human_judgment: false
  - id: D4
    description: "Concurrency changes no grade -- the streaming route's cards and the blocking route's cards agree exactly on (finding_id, confidence, db_record_found, opa_corroborated, opa_rule_ids) for the same system, proving verify_finding() stays synchronous-per-finding and is always awaited to completion before a card is emitted"
    requirement: "EVID-03"
    verification:
      - kind: integration
        ref: "backend/tests/test_routes_findings.py#test_integration_blocking_and_streaming_routes_agree_on_every_deterministic_field"
        status: pass
    human_judgment: false
  - id: D5
    description: "generate-capa's _find_finding_server_side issues at most one narration call (the matching check only), zero for an unknown finding_id, with first-match-wins ordering preserved for colliding rule ids"
    requirement: "ORC-03"
    verification:
      - kind: unit
        ref: "backend/tests/test_routes_actions.py#test_find_finding_server_side_issues_exactly_one_narration_call_on_a_match"
        status: pass
      - kind: unit
        ref: "backend/tests/test_routes_actions.py#test_find_finding_server_side_issues_zero_narration_calls_for_unknown_id"
        status: pass
      - kind: integration
        ref: "backend/tests/test_routes_actions.py (full file, 20/20 passing, including test_full_approval_loop's dynamic finding_id discovery)"
        status: pass
    human_judgment: false
  - id: D6
    description: "Backend startup pre-warms narration for both seeded demo systems without delaying /api/health, and never fires during an ordinary pytest run"
    requirement: "ORC-03"
    verification:
      - kind: unit
        ref: "backend/tests/test_prewarm.py (happy path, keyless negative, Postgres-unreachable edge, warm-then-read integration, structural client-fixture-never-triggers-prewarm check)"
        status: pass
      - kind: manual_procedural
        ref: "Manual smoke: freshly-started backend, curl /api/health measured ~2ms response time regardless of pre-warm status"
        status: pass
    human_judgment: false
  - id: D7
    description: "Frontend consumes the new streaming endpoint incrementally: cards paint on arrival, the all-checks-pass message renders only after the terminal frame, and an AbortController actually cancels the in-flight stream on system switch"
    requirement: "EVID-03"
    verification:
      - kind: other
        ref: "cd frontend && npm run build (tsc -b && vite build) -- clean"
        status: pass
      - kind: other
        ref: "cd frontend && npm run lint (oxlint) -- clean, no new warnings"
        status: pass
    human_judgment: true
    rationale: "Incremental-render UX (loading-line persistence, abort-on-switch, no flash of the all-pass message) is a visual/timing behavior best confirmed by a human watching the actual page, not solely by a type-check and a lint pass."

duration: ~50min
completed: 2026-08-26
status: complete
---

# Quick Task 260826-p1q: Research and permanently fix cold-path latency of A2's LLM narration synthesis Summary

**Groq-routed narration under a 3s wall-clock ceiling, a concurrent SSE-streaming assurance-cards pipeline, a one-call generate-capa fix, and startup narration pre-warming -- attacking all four multipliers behind the 18-50s cold path at once.**

## Performance

- **Duration:** ~50 min (includes a full-suite baseline run, three full-suite verification runs after each task, and live manual smoke testing against a running backend)
- **Tasks:** 3
- **Files modified:** 15 (2 created, 13 modified)

## Accomplishments

- **Task 1 -- Groq routing + 3s ceiling.** Added a `"narration"` task key to `groq_llama`'s `use_for` list (the *entire* routing change -- every other `PROVIDER_CONFIG` entry and `select_provider()` itself untouched), Groq-specific `reasoning_effort="low"` + `max_completion_tokens=512` request tuning gated strictly on `provider=="groq"`, and null-content coercion in `_parse_openai_compatible_response` so a reasoning-model truncation (`finish_reason: "length"`, null content) never raises past `call_llm` as an uncaught 500. `narrate_gap` now wraps `call_llm` in `asyncio.wait_for(3.0)` as the real total ceiling (the router's own `timeout` parameter alone would allow a ~6s worst case via its internal OpenRouter cascade), falling back to the deterministic sentence on timeout, degradation, or blank/whitespace text -- caching none of the three. Swept all Gemini narration mocks across `test_narration_cache.py`, `test_a2_compliance.py`, `test_hero_tracer.py`, and `test_hero_loop.py` to Groq (URL + key + OpenAI-shaped body, per the three-part rule RESEARCH.md identified), leaving `test_llm_router.py`'s compliance-routing assertion untouched as proof the change was surgical.
- **Task 2 -- Concurrency + SSE streaming + one-call generate-capa.** Extracted `_card_for_check` (check -> narrate -> build -> verify) as the single unit both the blocking route (`asyncio.gather`, input order, byte-identical to the old sequential loop) and a new `GET .../assurance-cards/stream` sibling route (`asyncio.as_completed`, completion order) fan out concurrently, bounded by a per-request `asyncio.Semaphore(4)` sized to protect the asyncpg pool's `max_size=5`. `verify_finding` is always awaited to completion *inside* `_card_for_check`, before a card object exists, so no caller can ever emit an unverified card. The streaming route's 404/503 guards run in the route function above the generator so they stay real HTTP status codes, never a torn 200. Fixed `routes/actions.py`'s `_find_finding_server_side` to compare a check-derived candidate id (`finding_id_for_check`, shared with `build_finding` so the two cannot drift) *before* narrating, cutting `generate-capa` from narrating every failing check to narrating at most one. Added `streamAssuranceCards()` to `lib/api.ts` (fetch + `body.getReader()`, chunk-boundary-safe frame buffering) and switched `FindingInvestigation.tsx` to accumulate and paint cards incrementally with `AbortController`-based cancellation on system switch.
- **Task 3 -- Startup pre-warm.** New `app/prewarm.py`: a directly `asyncio.run()`-able `prewarm_narration_cache()` that narrates every currently-failing check for both seeded demo systems, strictly sequentially (to avoid racing a live request's fan-out past the pool cap), reusing `narrate_gap` so the cache key matches `get_assurance_cards`' own by construction. `main.py` gains a `lifespan` context manager that schedules the pre-warm via `asyncio.create_task` and `yield`s immediately without awaiting it -- structurally guaranteeing `/api/health` is never delayed -- and cancels/awaits the task on shutdown. The pre-existing test-safety property (`TestClient`'s session-scoped `client` fixture never enters `with client:`, so the ASGI lifespan protocol never runs under `pytest`) was explicitly preserved, not "fixed."

## Task Commits

Each task was committed atomically:

1. **Task 1: Route A2 narration to Groq under a hard 3s ceiling, and repoint the test suite's narration mocks** - `20e7962` (feat)
2. **Task 2: Stream cards per-completion over SSE, run the per-check pipeline concurrently, and stop generate-capa narrating findings it will discard** - `2525ca7` (feat)
3. **Task 3: Pre-warm both demo systems' narration at startup without delaying readiness or firing under pytest** - `4c02f6c` (feat)

_Note: this quick task's own docs commit (SUMMARY.md/STATE.md) is created separately by the orchestrator, per the executor's constraint not to commit docs artifacts here._

## Files Created/Modified

- `backend/app/llm_router.py` - Groq `"narration"` task routing, Groq-specific request tuning, null-content coercion.
- `backend/app/agents/a2_compliance.py` - `narrate_gap`'s `asyncio.wait_for(3.0)` ceiling + blank-text guard; new `finding_id_for_check()` shared helper used by `build_finding`.
- `backend/app/routes/findings.py` - `_card_for_check` extraction, concurrent `asyncio.gather` blocking route, new SSE `/stream` sibling route.
- `backend/app/routes/actions.py` - `_find_finding_server_side` compares id before narrating.
- `backend/app/prewarm.py` - New: `prewarm_narration_cache()`, `DEMO_SYSTEM_IDS`.
- `backend/app/main.py` - `lifespan` context manager scheduling the pre-warm.
- `backend/tests/test_narration_cache.py`, `test_a2_compliance.py`, `test_hero_tracer.py`, `test_hero_loop.py` - Narration mocks repointed Gemini -> Groq.
- `backend/tests/test_routes_findings.py` - 5 new streaming-route tests.
- `backend/tests/test_routes_actions.py` - 2 new `_find_finding_server_side` call-count tests.
- `backend/tests/test_prewarm.py` - New: 6 tests (happy path, keyless negative, Postgres-unreachable edge, warm-then-read integration, structural client-fixture check, `DEMO_SYSTEM_IDS` unit check).
- `frontend/src/lib/api.ts` - `streamAssuranceCards()` SSE client.
- `frontend/src/pages/FindingInvestigation.tsx` - Incremental card rendering, `AbortController` cancellation.

## Decisions Made

See `key-decisions` in frontmatter. The most consequential: `asyncio.wait_for(3.0)` wraps the entire `call_llm()` call rather than shrinking `call_llm`'s own `timeout` parameter, because `call_llm` reuses that timeout for its internal OpenRouter cascade attempt -- a naive `timeout=3.0` alone would silently permit a ~6s worst case. This was flagged in RESEARCH.md and PLAN.md's Design Note 2 before implementation, so it was not a surprise discovered mid-task.

## Deviations from Plan

**Mostly none -- plan executed as written, with one addition beyond the plan's stated `files_modified` list:**

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Added direct call-count coverage for `_find_finding_server_side` in `test_routes_actions.py`**

- **Found during:** Task 2, reviewing coverage against the plan's own `<behavior>` list
- **Issue:** The plan's Task 2 `<behavior>` section explicitly requires "`_find_finding_server_side` issues exactly one narration call when a match exists, and zero when no failing check produces the requested id," but the plan's `files_modified` frontmatter list did not include `backend/tests/test_routes_actions.py` -- existing route-level tests exercised the happy path but never asserted the narration call count directly.
- **Fix:** Added two focused unit tests (`test_find_finding_server_side_issues_exactly_one_narration_call_on_a_match`, `test_find_finding_server_side_issues_zero_narration_calls_for_unknown_id`) using a respx route-call-count assertion, following the file's existing "discover the real finding_id, don't hardcode" convention. Did not add a DB-fixture-based first-match-wins collision test (constructing two checks that collide on the same seeded `finding_id` requires inserting rows this file's existing tests don't already provide) -- the ordering property itself is unchanged by this rewrite (same iteration order, same "return on first match" semantics, only the position of the narration call moved inside the `if`), so this was judged adequately covered by structural inspection plus the existing route-level regression tests rather than requiring new DB fixtures.
- **Files modified:** `backend/tests/test_routes_actions.py`
- **Verification:** All 20 tests in the file pass, including the 2 new ones and the pre-existing `test_full_approval_loop`'s dynamic finding_id discovery (proving the rewrite still resolves the real seeded finding correctly).
- **Committed in:** `2525ca7` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 missing critical test coverage). **Impact on plan:** No scope creep -- this closes a gap between the plan's own stated `<behavior>` requirements and its `files_modified` list, using the same file the changed code lives beside.

## Issues Encountered

- **No `.venv` or `node_modules` inside this worktree.** Both are gitignored and not carried into git worktrees. Resolved the same way the prior quick task (260826-0b5) did: invoked the main checkout's `backend/.venv/Scripts/python.exe` directly by absolute path (Python resolves the `app` package from `cwd`, not interpreter location) for all backend test runs, and symlinked the main checkout's `frontend/node_modules` into the worktree for the `npm run build`/`npm run lint` verification steps (the symlink itself is gitignored and was never staged).
- **A live `GROQ_API_KEY` unexpectedly exists in this environment**, contradicting `llm_router.py`'s own docstring ("No LLM provider API key is configured anywhere in this repo") and the prior quick task's finding. This was discovered mid-manual-smoke-test when a live `curl` against the SSE stream returned genuinely LLM-authored JSON narration rather than the deterministic-fallback sentence. This let three isolated `call_llm(task="narration", ...)` calls be measured directly: **0.56s, 0.665s, 0.768s, 0.818s** -- confirming Research Assumption A2's 0.5-1.5s prediction at the lower-to-middle end, with ample headroom under the 3.0s ceiling (the ceiling is not expected to fire on the happy path in this environment). `/api/health` was independently confirmed to respond in ~2ms on a freshly-started backend regardless of pre-warm status, proving the lifespan's non-blocking contract empirically as well as structurally. No secret was read, printed, or committed -- only response timing and content shape were observed.
- **Task 1's a2_compliance.py edit briefly overlapped with a Task-2-scoped addition.** While iterating, `finding_id_for_check` was drafted into `a2_compliance.py` before Task 1's commit. Reverted that addition, confirmed Task 1's suite run (337/0) reflected Task-1-only changes, committed Task 1, then reapplied `finding_id_for_check` as part of Task 2's diff -- keeping the per-task atomic-commit boundary honest rather than letting Task 2 work silently ride along inside Task 1's commit.

## User Setup Required

None -- no external service configuration required. (No new dependencies were added to `backend/requirements.txt` or `frontend/package.json`, confirmed via `git diff --stat` against both files showing zero changes.)

## Next Phase Readiness

- The full backend suite is green: **350 passed, 0 failed** (baseline 337 + 5 streaming-route tests + 2 `_find_finding_server_side` tests + 6 `test_prewarm.py` tests = 350). Frontend type-checks, builds, and lints clean.
- C1's `verify_finding()` is unmodified in semantics -- proven, not merely asserted, by `test_integration_blocking_and_streaming_routes_agree_on_every_deterministic_field`'s exact-tuple-set equivalence check between the concurrent blocking and streaming paths.
- The demo's cold-path story is now: pre-warm races a human's first request from the moment the process starts (never gating `/api/health`); if the human wins the race, the first card's narration is a single ~0.6-0.8s Groq call per failing check, run concurrently rather than summed; if a narration call ever hangs, the 3s ceiling guarantees the card still renders (with the deterministic template sentence) rather than blocking the whole read.
- No blockers for Phase 6 (Product Experience) or beyond. The `/stream` route and `streamAssuranceCards()` client are additive (the blocking route and `fetchAssuranceCards()` remain in place, still used by other call sites), so nothing here forecloses a future consumer that prefers the blocking contract.

## Self-Check: PASSED

All 15 files created/modified verified present via Glob (llm_router.py, a2_compliance.py, findings.py, actions.py, prewarm.py, main.py, 7 test files, api.ts, FindingInvestigation.tsx). All 3 task commits (`20e7962`, `2525ca7`, `4c02f6c`) verified present in `git log`.

---
*Phase: quick*
*Completed: 2026-08-26*
