# Quick Task 260826-p1q: Cold-path latency of A2 narration - Research

**Researched:** 2026-08-26
**Domain:** FastAPI streaming responses, asyncio concurrency, multi-provider LLM routing
**Confidence:** HIGH (nearly every finding is a direct read of this repo's own source)

## Summary

The 18-50s cold path is four independent multipliers stacked: (1) `get_assurance_cards` runs
`A2_CHECKS` **sequentially** — 4 checks, so up to 4 serial LLM round trips; (2) each round trip
goes to `gemini_flash_fast` at ~2.8s and, on any failure, cascades to a *second* full-timeout
attempt at OpenRouter; (3) `call_llm`'s `timeout=10.0` means a hung provider costs 10s per
attempt (20s with cascade) before the deterministic fallback fires; (4) the whole thing is one
blocking JSON payload, so the browser shows nothing until the slowest card lands.

All four locked decisions are implementable with **zero new dependencies** and small, surgical
diffs. The transport recommendation is **SSE via Starlette's built-in `StreamingResponse`,
consumed with `fetch` + `body.getReader()` (not `EventSource`)** — the WebSocket route is the
wrong shape here (it is session-agnostic broadcast, not request-scoped), and `EventSource`
cannot send this codebase's `X-User-Id`/`X-User-Role` headers.

**Primary recommendation:** Add a sibling streaming route rather than converting the existing
one; run the per-check pipeline with `asyncio.as_completed` behind it; add a `"narration"` task
to `groq_llama["use_for"]`; drive the pre-warm from a `lifespan` context manager calling a
plain, directly-testable async function.

---

## User Constraints (from CONTEXT.md)

### Locked Decisions
- **Stream per-card.** Deterministic fields render per card as each narration completes; the
  page never blocks on the slowest finding. Transport (SSE vs. existing WebSocket) is Claude's
  discretion; the streaming *behavior* is locked.
- **Groq primary for A2 narration only.** A0 orchestration and A7 remediation keep Gemini/DeepSeek
  untouched. Cascade-on-failure must be preserved.
- **Startup background pre-warm** for `GXP-MFG-DEMO-01` and `BUS-IT-DEMO-02`, non-blocking,
  must not delay `/api/health`.
- **~3s per-attempt narration timeout** with immediate `_deterministic_gap_sentence` fallback,
  scoped to narration only if `call_llm`'s `timeout` is per-call.

### Claude's Discretion
- Transport mechanism (SSE vs. WebSocket reuse) — see Decision 1 below.

### Deferred Ideas (OUT OF SCOPE)
- The caching layer itself (`app/narration_cache.py`) — already merged, do not duplicate.
- Any change to `verify_finding()` semantics, `calculate_confidence()`, or deterministic
  compliance logic.

---

## Project Constraints (from CLAUDE.md)

- **Rule 6 / Critical review:** C1, C2, C3, hash-chain, Rego, Blast Radius, ALCOA+, evidence
  graph need unit + negative + edge + integration coverage. This task must not *modify* C1, but
  it does move `verify_finding()` calls onto concurrent tasks — that needs an explicit test that
  concurrent verification produces byte-identical grades to the sequential path.
- **Rule 7 / no scope expansion:** add a *sibling* streaming route; do not rewrite the blocking
  one out from under `test_routes_findings.py` and `test_routes_actions.py`, which call
  `client.get(".../assurance-cards")` at 11 separate sites [VERIFIED: grep over `backend/tests/`].
- **Rule 10 / no two agents on one critical file:** `a2_compliance.py`, `llm_router.py`,
  `findings.py`, `actions.py`, `main.py` — split across tasks by file, not within.
- **Deterministic-first (Bible 1.3):** narration speed must never change a `passed` boolean or a
  confidence grade. The fallback sentence is already the safety valve; tightening the timeout
  only changes *which text* decorates an already-decided fact.

---

## Decision 1 — Transport: SSE over `StreamingResponse`, read with `fetch`

### Why not the existing WebSocket

`app/ws/copilot.py` is a **session-agnostic broadcast bus**: `broadcast_json` iterates
`_active_connections` and sends every frame to *every* connected client regardless of
`session_id`, and the module docstring explicitly records this as a deliberate single-operator
boundary, not an oversight to "fix" [VERIFIED: backend/app/ws/copilot.py:30-40, 66-97]. Assurance
cards are **request-scoped and system-scoped** — a `GXP-MFG-DEMO-01` card stream must not land in
a client currently looking at `BUS-IT-DEMO-02`. Reusing that socket means either (a) adding the
per-session filtering the docstring says would be required, or (b) leaking cross-system cards.
Both are larger than this task. The socket also has no request/response correlation, so the
frontend would need a correlation-id scheme invented from scratch.

### Why SSE works here with zero new dependencies

- `sse-starlette` is **not** in `backend/requirements.txt` and **not** installed
  [VERIFIED: backend/requirements.txt — the full list is `fastapi==0.141.1, pydantic==2.13.4,
  uvicorn[standard]==0.52.4, httpx==0.28.1, langgraph==1.2.11, langchain-core==1.6.0,
  pytest==9.1.1, asyncpg==0.31.0, respx==0.23.1, python-dotenv==1.1.1, networkx==3.4.2`].
  It is not needed: `starlette.responses.StreamingResponse` with
  `media_type="text/event-stream"` over an async generator is sufficient.
- `uvicorn[standard]` is the server and there is no reverse proxy in local dev, so no
  response-buffering layer defeats the stream.

### Why `fetch` + `body.getReader()` and NOT `EventSource`

`frontend/src/lib/api.ts`'s `apiGet` sends `identityHeaders()` (`X-User-Id`, `X-User-Role`) on
**every** GET [VERIFIED: frontend/src/lib/api.ts:69-76, frontend/src/lib/identity.ts:98-103].
The browser `EventSource` API cannot set request headers at all. Today
`get_assurance_cards(system_id)` has **no** `Depends(require_identity)`
[VERIFIED: backend/app/routes/findings.py:79-96], so `EventSource` would *appear* to work — and
would silently become unfixable the moment C2 RBAC is extended to this route. Reading the SSE
body with `fetch` keeps the header convention intact and keeps `ApiError` status handling.

### Recommended wire contract

Mirror `lib/ws.ts`'s discriminated-union-on-`event` convention exactly — it already exists and
the docstring explains why a union beats a loose record [VERIFIED: frontend/src/lib/ws.ts:10-39]:

```
GET /api/systems/{system_id}/assurance-cards/stream   ->  text/event-stream

data: {"event":"card","card":{...AssuranceCard...}}\n\n
data: {"event":"done","system_id":"GXP-MFG-DEMO-01","count":2}\n\n
```

Errors that today are `HTTPException` (503 pool, 404 unknown system) must still be raised
**before** the generator is returned — once `StreamingResponse` starts, the status line is
already committed and a later raise produces a torn response, not a 404.

**Pitfall:** a bare `raise HTTPException` inside the async generator body will not become a 404.
Do the `acquire_pool_or_none()` and `_system_exists()` guards in the route function, above the
generator, exactly as the blocking route does now.

---

## Decision 2 — Groq routing for narration

### The model name is confirmed and suitable

`PROVIDER_CONFIG["groq_llama"]["model"]` is `"openai/gpt-oss-120b"`, base_url
`https://api.groq.com/openai/v1`, `rpm_limit: 300`, `use_for: ["incident", "access",
"high_volume"]` [VERIFIED: backend/app/llm_router.py:94-102 — quoted verbatim:
`"model": "openai/gpt-oss-120b"`, `"use_for": ["incident", "access", "high_volume"]`]. It is a
currently-served Groq production model: 131,072-token context, ~500 tokens/sec, 1K RPM on the
developer plan [CITED: https://console.groq.com/docs/models]. For a one-sentence narration this
is comfortably the fastest option available in this config.

**Latency caveat worth acting on:** gpt-oss-120b is a *reasoning* model. Groq exposes
`reasoning_effort` with values `low` / `medium` / `high` for gpt-oss models, and `low` minimizes
reasoning tokens; `reasoning_format` is **not** supported for gpt-oss
[CITED: https://console.groq.com/docs/reasoning]. `_build_openai_compatible_request` currently
sends only `{"model", "messages"}` — no `max_tokens`, no `reasoning_effort`
[VERIFIED: backend/app/llm_router.py:168-177]. For a one-sentence output, default reasoning
effort is pure latency. Adding `reasoning_effort: "low"` and a small `max_completion_tokens` cap
for Groq is the single highest-leverage per-call change available.
**Caution:** OpenRouter (the cascade target) is also OpenAI-compatible and shares
`_build_openai_compatible_request`. Gate any Groq-specific field on `entry["provider"] ==
"groq"`, or OpenRouter's `openrouter/auto` may 400 on an unknown field.

### How to route without breaking anyone else

`select_provider(task)` linearly scans `PROVIDER_CONFIG` and returns the first entry whose
`use_for` contains `task`, raising `KeyError` otherwise [VERIFIED: backend/app/llm_router.py:124-135].
The clean, minimal change is:

1. Add `"narration"` to `groq_llama["use_for"]` → `["incident", "access", "high_volume", "narration"]`.
2. Change `narrate_gap`'s call from `task="compliance"` to `task="narration"`
   [VERIFIED: backend/app/agents/a2_compliance.py:315-320].

`"compliance"` stays on `gemini_flash_fast` and every other task mapping is untouched, so
`test_llm_router.py::test_select_provider_routes_by_task` (which asserts
`select_provider("compliance") == "gemini_flash_fast"`) still passes
[VERIFIED: backend/tests/test_llm_router.py:36-39]. Cascade is untouched — `call_llm` cascades
from *whatever* `entry_key` was selected to `openrouter_fallback` on missing key / timeout / 429 /
5xx [VERIFIED: backend/app/llm_router.py:257-303]. No special-casing, no bypass.

**Do not** create a new `PROVIDER_CONFIG` entry for narration. `select_provider` returns the
*first* matching entry by dict insertion order, so a duplicate-task entry becomes a silent
ordering dependency.

### Test blast radius (this is the biggest hidden cost of Decision 2)

Every existing narration test mocks the **Gemini** endpoint with respx. Switching narration to
Groq makes each of these fall through to a real network call or an `AllMockedAssertionError`:

| File | Gemini mock sites for narration |
|---|---|
| `backend/tests/test_narration_cache.py` | lines 171, 189, 211, 249, 294, 335, 375 (`GEMINI_ENDPOINT`) |
| `backend/tests/test_a2_compliance.py` | lines 256, 276, 317 (`GEMINI_ENDPOINT`) |
| `backend/tests/test_hero_tracer.py` | lines 146, 230 |
| `backend/tests/test_hero_loop.py` | line 313 (line 164 is the multi-provider helper) |

[VERIFIED: grep over `backend/tests/`]

Good news: `test_hero_loop.py` already defines `GROQ_URL =
"https://api.groq.com/openai/v1/chat/completions"` and mocks it with a working OpenAI-shaped
response body [VERIFIED: backend/tests/test_hero_loop.py:100, 170] — copy that response shape
rather than inventing one. The router parses Groq responses via
`_parse_openai_compatible_response`, which reads `data["choices"][0]["message"]["content"]` and
prefers `data.get("model")` over the config's model string for `model_id`
[VERIFIED: backend/app/llm_router.py:185-188] — so a mock that omits `"model"` will attribute the
card to `openai/gpt-oss-120b`, and one that includes it will attribute to whatever the mock says.

---

## Decision 3 — Startup pre-warm

### Mechanism: `lifespan` context manager + `asyncio.create_task`

`app/main.py` today constructs `FastAPI(...)` with no `lifespan=` and has no `on_event`
handler anywhere [VERIFIED: backend/app/main.py:49-78]. Use an
`@asynccontextmanager async def lifespan(app)` passed as `FastAPI(lifespan=lifespan)`, which
inside does `asyncio.create_task(prewarm_narration_cache())` and yields immediately. That
satisfies "must not delay `/api/health`" structurally: `yield` is reached without awaiting the
task, so the ASGI `lifespan.startup.complete` message is sent before any LLM call resolves.

Three concrete requirements:
- **Hold a reference** to the task (`app.state._prewarm_task = asyncio.create_task(...)`).
  A bare `create_task` result that nothing references can be garbage-collected mid-flight.
- **Swallow everything** inside the pre-warm coroutine. Postgres down at boot, OPA down, no
  `GROQ_API_KEY` — all must log and return, never propagate. An unhandled exception in a
  fire-and-forget task surfaces as a "Task exception was never retrieved" warning at shutdown
  and nothing else.
- **Cancel on shutdown** after the `yield`, so `pytest`/`uvicorn --reload` don't leak it.

### The pre-warm body should reuse `narrate_gap`, not reimplement it

Loop `A2_CHECKS` for `["GXP-MFG-DEMO-01", "BUS-IT-DEMO-02"]` and call `narrate_gap` on each
failing check. That is exactly the prompt string `get_assurance_cards` will later build, so the
`narration_cache` key matches by construction — the cache is keyed on a sha256 of the finished
prompt [VERIFIED: backend/app/narration_cache.py:86-93]. Any hand-rolled prompt in the pre-warm
would produce a different digest and warm nothing. Both system ids are real seeded rows
[VERIFIED: infra/postgres/seed/001_seed.sql:33 `VALUES ('GXP-MFG-DEMO-01', ...)` and
infra/postgres/seed/001_seed.sql:94 `VALUES ('BUS-IT-DEMO-02', ...)`].

### Tests will NOT run the lifespan — this is both a safety property and a testability constraint

`conftest.py`'s `client` fixture returns a bare `TestClient(app)` and tests call `client.get(...)`
directly without `with client:` [VERIFIED: backend/tests/conftest.py:77-79;
backend/tests/test_routes_actions.py:34 `client = TestClient(app)` at module level]. Starlette
runs the lifespan **only** inside `TestClient.__enter__` (`self.task =
portal.start_task_soon(self.lifespan); portal.call(self.wait_startup)`)
[VERIFIED: backend/.venv/Lib/site-packages/starlette/testclient.py:679-698]. So the pre-warm will
never fire during an ordinary `pytest` run — which is exactly right given the already-logged
finding that `load_dotenv()` picks up a live `GEMINI_API_KEY` and makes real provider calls in
tests (`deferred-items.md`, quick task 260826-0b5). **Therefore:** the pre-warm must be a plain
module-level `async def prewarm_narration_cache()` that a test can `asyncio.run()` directly under
respx, not logic buried inside the lifespan closure.

---

## Decision 4 — Timeout is already per-call; no global side effect

`call_llm(task, prompt, system_instruction="", timeout=10.0, json_output=False)` takes `timeout`
as a plain per-call parameter and threads it into `_send_one` → `client.post(..., timeout=timeout)`
[VERIFIED: backend/app/llm_router.py:233-239, 212-215]. `narrate_gap` already passes an explicit
`timeout=10.0` [VERIFIED: backend/app/agents/a2_compliance.py:315-320]. Changing that single
literal to `3.0` is a strictly local change — A0 (`test_a0_orchestrator.py`) and A7 pass their own
values or take the default and are structurally unaffected.

**Non-obvious consequence to plan for:** the same `timeout` value is reused for the
`openrouter_fallback` attempt [VERIFIED: backend/app/llm_router.py:289]. So a 3s narration
timeout means a worst-case of **~6s** (3s Groq + 3s OpenRouter), not 3s, before
`response.degraded` is True and `_deterministic_gap_sentence` fires. If the locked "~3s per
attempt" is meant as a wall-clock ceiling rather than a per-attempt one, the planner should
either use ~1.5s per attempt or wrap `narrate_gap`'s `call_llm` in `asyncio.wait_for(..., 3.0)`
— the latter is cleaner and does not touch the router's cascade semantics at all. Recommend
`asyncio.wait_for` around the call with `except asyncio.TimeoutError` → the same
`_deterministic_gap_sentence` branch the `degraded` check already uses.

---

## Also Investigated

### `asyncio.gather` is still needed — streaming alone does not fix it

Yes, keep it. Streaming changes *when the client renders*; it does not change *when the work
finishes*. `get_assurance_cards` loops `A2_CHECKS` and `await`s each check → narrate → verify
strictly in order [VERIFIED: backend/app/routes/findings.py:98-106], so with a sequential loop the
4th card still arrives at t = sum of all four narrations even over SSE. Fan the per-check
pipeline out with `asyncio.as_completed` (or `gather` + a queue) so cards stream in **completion
order** and total wall clock is max(), not sum().

Concurrency safety, checked concretely:
- `A2_CHECKS` has **4** entries: `verify_urs_approved`, `verify_periodic_eval_current`,
  `verify_test_traceability`, `verify_no_stale_documents`
  [VERIFIED: backend/app/agents/a2_compliance.py:243-248] — so worst case 4 concurrent tasks, not
  an unbounded fan-out.
- **asyncpg pool `max_size=5`** [VERIFIED: backend/app/db.py:95-100 — `min_size=1, max_size=5,
  timeout=5.0, command_timeout=10.0`]. 4 concurrent coroutines each holding at most one
  connection at a time fits, with 1 spare. But a concurrent pre-warm run plus a concurrent user
  request could exceed it and start blocking on the 5.0s acquire timeout. Bound the fan-out with
  an `asyncio.Semaphore` sized ≤ 4, or accept that the pre-warm should stay sequential.
- `narration_cache` has **no in-flight de-duplication** and this is a documented, deliberate
  decision (a module-level `asyncio.Lock` would bind to a dead event loop under this suite's
  `asyncio.run()`-per-test convention) [VERIFIED: backend/app/narration_cache.py:53-62]. Under
  `gather`, four *distinct* checks build four *distinct* prompts → four distinct keys → no
  collision. Do **not** add a lock to fix a problem that does not exist here.

### `_find_finding_server_side` needs a different fix, not streaming

It loops `A2_CHECKS`, narrates **every** failing check, and only then compares
`finding["finding_id"] == finding_id` [VERIFIED: backend/app/routes/actions.py:109-124]. That is
up to 4 LLM calls to answer a question that needs 1. It is a POST that returns one object — there
is nothing to stream.

The correct fix is to move the id comparison *before* the narration:
`build_finding` computes `finding_id` as `f"A2-{rule_id}-{record_id}"`, or
`f"A2-{rule_id}-NO-RECORD"` when `record is None` — and neither form depends on the claim text
[VERIFIED: backend/app/agents/a2_compliance.py:329-360]. So the route can derive the candidate id
from `check_result` alone, `continue` on a mismatch, and narrate only the match.

**Preserve first-match-wins ordering.** `verify_urs_approved` and `verify_no_stale_documents`
both carry `rule_id = "ANNEX11-S4-DOC-001"` [VERIFIED: backend/app/agents/a2_compliance.py:124,
186], so two different checks can collide on a `finding_id` when their record ids match. Today's
loop returns the first; the rewrite must iterate `A2_CHECKS` in the same order and return on the
first match, not gather.

### C1's `verify_finding()` is not the bottleneck and stays synchronous per finding

`verify_finding` does one `fetchrow`, then (only if a record exists) 1-2 `fetch` calls and exactly
one `evaluate_opa_policy()` POST [VERIFIED: backend/app/agents/c1_verifier.py:227-259]. That POST
goes to the local OPA sidecar with a **2.0-second** ceiling
[VERIFIED: backend/app/opa_client.py:111-115]; against `127.0.0.1:8181` it is single-digit
milliseconds in practice — three orders of magnitude below a 2.8s LLM call. It is not on the
critical path in any meaningful sense, and the four locked decisions correctly leave it alone.

It is also **safe to run concurrently**: every statement in `c1_verifier.py` is a `SELECT`, it
holds no module-level mutable state, and `evaluate_opa_policy` opens its own
`httpx.AsyncClient` per call [VERIFIED: backend/app/opa_client.py:111]. Moving four
`verify_finding` calls onto four concurrent tasks does not change any grade — but per CLAUDE.md
Rule 6 that claim must be *proven* by a test asserting the streaming route's per-card
`confidence` / `db_record_found` / `opa_corroborated` are byte-identical to the blocking route's
for the same system, not merely asserted in a docstring.

Keep `verify_finding` awaited **inside** each per-check task, so a card is only emitted once its
deterministic grade exists. Never emit a card with a placeholder confidence to be patched later —
that would put unverified content on screen, which is precisely the thesis violation
CLAUDE.md forbids.

---

## Test-Suite Conventions to Respect

- **`asyncio.run()` per test inside a plain `def test_*`** — no pytest-asyncio. Never create a
  module-level asyncio primitive [VERIFIED: backend/tests/conftest.py:16-25].
- **Windows selector event-loop policy is set at collection time** in `conftest.py` before any
  loop exists [VERIFIED: backend/tests/conftest.py:69-70]. Anything new must not create a loop
  at import.
- **`respx.route(host="127.0.0.1", port=8181).pass_through()` is mandatory** in any test whose
  body reaches C1, because respx defaults to `assert_all_mocked=True` and will otherwise
  intercept the real OPA sidecar call [VERIFIED: backend/tests/test_narration_cache.py:210, 327;
  backend/tests/test_hero_tracer.py:145; documented in 260826-0b5-SUMMARY.md's auto-fix #1].
- **The autouse `_clear_narration_cache` fixture clears the cache before and after every test**
  [VERIFIED: backend/tests/conftest.py:138-148]. A pre-warm test therefore starts clean for free,
  but a test asserting "second request is a hit" must do both requests inside one test body.
- **Testing the SSE route:** Starlette's `TestClient` is httpx-based, so
  `with client.stream("GET", url) as r: for line in r.iter_lines()` works without a new
  dependency. Note the `client` fixture is **session-scoped** and not entered as a context
  manager — a streaming test should build its own `TestClient` if it needs the lifespan.

---

## Suggested Task Decomposition (for the planner)

| # | Scope | Files (Rule 10: disjoint) |
|---|---|---|
| 1 | Groq narration routing + `reasoning_effort`/token cap + `asyncio.wait_for` 3s fallback + repoint existing Gemini narration mocks to Groq | `app/llm_router.py`, `app/agents/a2_compliance.py`, `tests/test_llm_router.py`, `tests/test_a2_compliance.py`, `tests/test_narration_cache.py`, `tests/test_hero_*.py` |
| 2 | SSE streaming sibling route with `as_completed` fan-out (blocking route kept intact) + `_find_finding_server_side` narrate-only-the-match fix + frontend `fetch`-reader consumption | `app/routes/findings.py`, `app/routes/actions.py`, `frontend/src/lib/api.ts`, `frontend/src/pages/FindingInvestigation.tsx`, `tests/test_routes_findings.py` |
| 3 | `lifespan` pre-warm calling a directly-testable `prewarm_narration_cache()` | `app/main.py`, new `app/prewarm.py`, new `tests/test_prewarm.py` |

Task 1 must land before Task 3 (the pre-warm should warm the Groq-authored text, not Gemini's,
or the `model_attribution` on a warmed card will disagree with a cold one).

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|---|---|---|
| A1 | The demo runs single-worker uvicorn, so an in-process pre-warm reaches the same process that serves requests | Decision 3 | Under `--workers N` only one worker warms; others stay cold. `ws/copilot.py`'s docstring already records single-worker as this project's operating assumption, so risk is low. |
| A2 | ~500 tok/s and a short narration prompt put Groq's real latency in the 0.5-1.5s range | Decision 2 | If Groq's actual p95 exceeds 3s, the tightened timeout makes narration *always* fall back to the template. Mitigation: benchmark once before locking `3.0`, and log the observed latency. |
| A3 | No reverse proxy / response buffering sits between uvicorn and the browser in the demo environment | Decision 1 | A buffering proxy would collapse SSE back into a single blocking payload. Local dev is direct `127.0.0.1:8000`, so this holds today. |

## Sources

### Primary (HIGH confidence)
- Direct `Read` of: `backend/app/routes/findings.py`, `backend/app/agents/a2_compliance.py`,
  `backend/app/llm_router.py`, `backend/app/narration_cache.py`, `backend/app/agents/c1_verifier.py`,
  `backend/app/main.py`, `backend/app/ws/copilot.py`, `backend/tests/conftest.py`,
  `frontend/src/lib/api.ts`, `frontend/src/lib/ws.ts`, `frontend/src/lib/identity.ts`,
  `frontend/src/pages/FindingInvestigation.tsx`, `backend/requirements.txt`,
  `infra/postgres/seed/001_seed.sql`, `backend/.venv/.../starlette/testclient.py`
- `.planning/quick/260826-0b5-.../260826-0b5-SUMMARY.md` (prior narration quick task)

### Secondary (MEDIUM confidence)
- https://console.groq.com/docs/models — `openai/gpt-oss-120b` production status, 131k context,
  ~500 tok/s, 1K RPM
- https://console.groq.com/docs/reasoning — `reasoning_effort` low/medium/high;
  `reasoning_format` unsupported for gpt-oss

## Metadata

**Confidence breakdown:**
- Transport recommendation: HIGH — grounded in this repo's own WebSocket docstring and header conventions
- Groq routing mechanism: HIGH — `select_provider` read line by line; test blast radius enumerated by grep
- Pre-warm mechanism: HIGH — TestClient lifespan behavior verified in installed starlette source
- Timeout scoping: HIGH — `call_llm` signature and cascade path read directly
- Groq real-world latency: MEDIUM — vendor-published throughput, not measured in this session

**Research date:** 2026-08-26
**Valid until:** ~2026-09-25 (Groq model catalog moves fast; re-verify the model id if this sits)
