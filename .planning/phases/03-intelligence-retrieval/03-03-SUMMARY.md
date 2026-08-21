---
phase: 03-intelligence-retrieval
plan: 03
subsystem: api
tags: [langgraph, llm-router, gemini, deepseek, groq, openrouter, opa, asyncpg]

requires:
  - phase: 03-intelligence-retrieval (plan 03-02)
    provides: llm_router.call_llm(), app.db (asyncpg pool), the A2/C1 tracer pattern, RULE_EVIDENCE_TABLES/RULE_OPA_INPUT
provides:
  - "A0 orchestrator: real intent classification with a hard 2000ms asyncio.wait_for fallback to the full six-agent set"
  - "A1/A3/A4/A5/A6: genuinely-real-but-minimal specialists (one deterministic Postgres check + one router call + Bible-specified failure behavior each)"
  - "opa_client.evaluate_opa_policy() datetime-safety fix (_json_safe), unblocking any future evidence table with a TIMESTAMP column"
affects: [03-04, 03-05, 03-06, phase-04-evidence-impact]

actuals:
  tokens: 15848
  tasks: 2
  commits: 2

tech-stack:
  added: []
  patterns:
    - "Shared specialist driver (run_specialist + SPECIALIST_CONFIG) — one gap-check/narrate/fallback shape reused across A1/A3/A4/A5/A6, differing in data (SQL, rule id, sentence template) not code"
    - "_safe_call_llm() defensive wrapper — treats any unexpected exception from call_llm() (not just the httpx exception types it documents) identically to a degraded response"

key-files:
  created:
    - backend/app/agents/a0_orchestrator.py
    - backend/app/agents/minimal_specialists.py
    - backend/tests/test_a0_orchestrator.py
    - backend/tests/test_minimal_specialists.py
  modified:
    - backend/app/graph/state.py
    - backend/app/opa_client.py
    - backend/tests/test_hero_tracer.py
    - backend/tests/test_opa_client.py
    - backend/README.md

key-decisions:
  - "A0's classify_intent() validates active_agents against FULL_AGENT_SET and rejects empty lists before returning — an externally-produced classification can never introduce a node id route_specialists doesn't already own (T-03-12)"
  - "A1's ERR-A1 fallback is transcribed Bible-literally (empty {} alcoa_score, gemini-2.5-flash attribution even on failure) — deliberately NOT the ALCOAScore().model_dump()/deterministic-fallback shape every other agent's degraded finding uses"
  - "A3's downgrade-and-retry (DeepSeek -> gemini_flash_thinking) is explicit code in minimal_specialists.py, not relying on llm_router's own openrouter cascade, since the Bible names a specific downgrade target different from the router's generic fallback"
  - "opa_client.py Deviation 8: evaluate_opa_policy() now sanitizes datetime values before JSON-encoding — fixed at the one point a Postgres row's native Python types cross into an HTTP JSON body, not inside c1_verifier.py (out of scope for this plan)"

patterns-established:
  - "Pattern: gap-check-then-narrate — a deterministic Postgres check decides pass/fail; the LLM only narrates an already-computed gap into a claim sentence, with a deterministic template as the fallback. Now applied uniformly across A2 (03-02) and A1/A3/A4/A5/A6 (this plan)."

requirements-completed: [ORC-02]

coverage:
  - id: D1
    description: "A0 classifies a real query via the router and narrows active_agents to the classified subset, which route_specialists fans out to"
    requirement: "ORC-02"
    verification:
      - kind: unit
        ref: "backend/tests/test_a0_orchestrator.py::test_mocked_classification_narrows_active_agents"
        status: pass
    human_judgment: false
  - id: D2
    description: "A classification that has not returned within 2000ms is abandoned (cancelled, not raced) and active_agents reverts to the full six-agent set, proven by measured elapsed time"
    requirement: "ORC-02"
    verification:
      - kind: unit
        ref: "backend/tests/test_a0_orchestrator.py::test_timeout_over_2000ms_falls_back_to_full_set_within_2500ms"
        status: pass
    human_judgment: false
  - id: D3
    description: "Every one of A1, A3, A4, A5, A6 runs a real deterministic Postgres check and a real router call, and returns its Bible Section 2 failure behavior when that work cannot complete"
    verification:
      - kind: unit
        ref: "backend/tests/test_minimal_specialists.py::test_all_five_return_findings_list_and_none_are_unconditionally_empty"
        status: pass
      - kind: unit
        ref: "backend/tests/test_minimal_specialists.py::test_all_five_return_bible_fallback_with_postgres_unreachable"
        status: pass
    human_judgment: false
  - id: D4
    description: "The full six-agent fan-out completes with no provider key present"
    verification:
      - kind: unit
        ref: "backend/tests/test_minimal_specialists.py::test_all_five_complete_with_no_provider_key_present_and_postgres_reachable"
        status: pass
      - kind: integration
        ref: "backend/tests/test_hero_tracer.py::test_degraded_path_no_provider_key_same_finding_and_score"
        status: pass
    human_judgment: false

duration: 95min
completed: 2026-08-21
status: complete
---

# Phase 3 Plan 3: A0 Orchestrator + Minimal-But-Real A1/A3-A6 Specialists Summary

**A0 became a real Gemini-backed intent classifier with a hard, measured 2000ms `asyncio.wait_for` fallback to the full six-agent set, and the five remaining specialist stubs (A1, A3, A4, A5, A6) became genuinely-real-but-minimal agents — each running one real deterministic Postgres check and one real `llm_router.call_llm()` call, and returning its exact Bible Section 2 failure behavior when either can't complete — closing the ROADMAP phase gate that no node may return an unconditional empty finding list.**

## Performance

- **Duration:** 95 min
- **Started:** 2026-08-21T15:47:00Z (approx, worktree creation)
- **Completed:** 2026-08-21
- **Tasks:** 2
- **Files modified:** 9

## Accomplishments

- `backend/app/agents/a0_orchestrator.py`: `classify_intent()` calls the router (`task="orchestrator"` → Gemini 2.5 Flash thinking-on, JSON output requested), validates the parsed `OrchestratorOutput` against `FULL_AGENT_SET` (rejecting empty or unknown-id classifications); `run_a0()` wraps it in `asyncio.wait_for(A0_TIMEOUT_SECONDS)`, cancelling the in-flight coroutine on timeout and falling back to the Bible-ordered full six-agent set on every failure mode.
- `backend/app/agents/minimal_specialists.py`: one shared `run_specialist(agent_id, state)` driver over a `SPECIALIST_CONFIG` table — A1 validates `system_id` exists (Bible-verbatim `ERR-A1` abstain otherwise); A3 flags a risk assessment overdue its ICH Q9(R1) 12-month cycle, downgrading DeepSeek → `gemini_flash_thinking` on failure and retrying once before a deterministic sentence; A4 flags a `CLOSED` change with an `OPEN` linked action from direct metadata only (no graph traversal — Phase 4 territory); A5 flags a P1 incident open >7 days without RCA; A6 flags an overdue access review and an orphaned privileged (departed-user) account as two independently-verifiable findings, relying on the router's own OpenRouter cascade.
- `backend/app/graph/state.py`: `orchestrator_a0`, `system_knowledge_a1`, `risk_a3`, `change_a4`, `incident_a5`, `access_a6` all now delegate to real implementations. `route_specialists`, both `TypedDict`s, and the graph-assembly block are byte-identical to Phase 2 — the eleven-node topology is unchanged, verified by `test_graph_topology.py`.
- `backend/app/opa_client.py` (Deviation 8): fixed a latent `TypeError` — asyncpg returns native `datetime.datetime` for `TIMESTAMP` columns (e.g. `changes.qa_approval_date`), which httpx's `json=` encoder cannot serialize and which `evaluate_opa_policy()`'s existing `except` clause does not catch (`TypeError` is neither `httpx.RequestError` nor `httpx.HTTPStatusError`). Unexercised since Phase 2 because A2's only evidence table has no timestamp column; first hit once A4 (this plan) cites `changes`. Fixed with a new `_json_safe()` recursive sanitizer at the one point a Postgres row's native types cross into an HTTP JSON body — not inside `c1_verifier.py`, which `<critical_findings>` places out of scope for this plan.
- Full backend suite: **72/72 passing** (`pytest -q` from `backend/`, live Postgres + OPA required).

## Task Commits

Each task was committed atomically:

1. **Task 1: A0 Orchestrator** - `52810a3` (feat)
2. **Task 2: Minimal-but-real A1/A3/A4/A5/A6** - `2a6e95f` (feat)

**Plan metadata:** `9e73e28` (docs: complete plan)

## Files Created/Modified

- `backend/app/agents/a0_orchestrator.py` - `FULL_AGENT_SET`, `A0_TIMEOUT_SECONDS`, `A0_SYSTEM_PROMPT`, `classify_intent()`, `run_a0()`
- `backend/app/agents/minimal_specialists.py` - `SPECIALIST_CONFIG`, `run_specialist()`, `run_a1()`/`run_a3()`/`run_a4()`/`run_a5()`/`run_a6()`
- `backend/app/graph/state.py` - six node bodies now delegate; module docstring updated
- `backend/app/opa_client.py` - `_json_safe()` datetime sanitizer (Deviation 8)
- `backend/tests/test_a0_orchestrator.py` - 11 tests (9 required behaviors, some split into multiple assertions)
- `backend/tests/test_minimal_specialists.py` - 10 tests, one per required behavior
- `backend/tests/test_opa_client.py` - regression test for the datetime fix
- `backend/tests/test_hero_tracer.py` - `_one_finding()` and the `verification_results` key-set assertion updated to tolerate the now-real full six-agent fan-out (see Deviations)
- `backend/README.md` - Deviation 8 entry, routed to SENT-7-05

## Decisions Made

- A1's `ERR-A1` fallback is transcribed exactly as the Bible states it (`alcoa_score: {}`, `model_attribution: "gemini-2.5-flash"`), a deliberately different shape from every other agent's degraded finding (`ALCOAScore().model_dump()`, `model_attribution: "deterministic-fallback"`) — the Bible's own literal text for this one agent, not a stray inconsistency.
- A3's DeepSeek-timeout downgrade is hand-written retry logic in `minimal_specialists.py` (try `task="risk_assessment"`, then `task="orchestrator"`), not a reliance on `llm_router`'s generic OpenRouter cascade — the Bible names a specific downgrade target (`gemini_flash_thinking`) distinct from the router's universal fallback.
- `_safe_call_llm()` wraps every `call_llm()` invocation in `minimal_specialists.py` in a broad exception guard. `call_llm()`'s own docstring promises it never raises, but its `except` clauses only name `_MissingKeyError`/`httpx.TimeoutException`/`httpx.HTTPStatusError` — under this repo's live-key environment (`.env` now has real Gemini/DeepSeek/Groq/OpenRouter keys, per the 03-CONTEXT.md follow-up), a request to a host no test explicitly mocks raises respx's own `AllMockedAssertionError`, which is none of those types and would otherwise crash the node.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `opa_client.evaluate_opa_policy()` crashed on a `datetime` value from a live Postgres row**
- **Found during:** Task 2, running `pytest tests/test_hero_tracer.py` after wiring A4 (the first specialist whose evidence table, `changes`, has a `TIMESTAMP` column)
- **Issue:** `TypeError: Object of type datetime is not JSON serializable`, uncaught by `evaluate_opa_policy()`'s existing `except (httpx.RequestError, httpx.HTTPStatusError)` clause, crashing C1's verification of A4's real finding
- **Fix:** Added `_json_safe()` (recursive `datetime`→ISO-string conversion) applied to the payload before `client.post(json=...)`
- **Files modified:** `backend/app/opa_client.py`, `backend/tests/test_opa_client.py`, `backend/README.md` (Deviation 8)
- **Verification:** `test_payload_containing_datetime_value_does_not_raise_typeerror` (new); full `test_opa_client.py` suite (8/8) and `test_hero_tracer.py` (3/3) pass
- **Committed in:** `2a6e95f` (Task 2 commit)
- **Boundary note:** `c1_verifier.py` and `a2_compliance.py` — the two files `<critical_findings>` places out of scope for this plan — were **not** touched. The fix lives entirely in `opa_client.py`, the one place a Postgres row's native Python types cross into an HTTP JSON body, regardless of which caller's evidence table supplied the row.

**2. [Rule 1 - Bug] `test_hero_tracer.py`'s "exactly one finding" assertions were invalidated by this plan's own required behavior**
- **Found during:** Task 2, running the plan's own cross-suite verify step (`pytest tests/test_graph_topology.py tests/test_hero_tracer.py tests/test_a0_orchestrator.py`)
- **Issue:** `test_hero_tracer.py` (written in plan 03-02, when A0/A1/A3-A6 were all still stubs or literal-empty-finding stubs) asserted the graph produces exactly one finding. Once A0 became real (Task 1) it correctly falls back to the full agent set against this test's prose (non-JSON) mocked Gemini response — proven independently and correctly by `test_a0_orchestrator.py`. Once A1/A3-A6 became real (Task 2), they find their own real gaps against the *same* live seeded Postgres this tracer test already uses (`RSK-2024-11`, `CR-2026-089`/`CA-2026-089-1`, `INC-849201`, `AR-2026-05`, `ACC-2026-99`) — this is exactly Task 2's own required behavior ("with the seeded database present, A3, A4, A5, and A6 each produce at least one finding"), not a bug in the new code. The two requirements (hero_tracer stays green; A3-A6 must produce real findings against real seeded gaps) are only simultaneously satisfiable by loosening hero_tracer's finding-count assertion.
- **Fix:** `_one_finding()` now locates A2's finding by `finding_id` among the full result set instead of asserting the set has exactly one member; the `verification_results` key-set assertion changed from `== {EXPECTED_FINDING_ID}` to `EXPECTED_FINDING_ID in verification`. Every original assertion about A2's own finding content and its C1 verification result (`MEDIUM`, `db_record_found`, `opa_corroborated`) is unchanged.
- **Files modified:** `backend/tests/test_hero_tracer.py`
- **Verification:** All 3 hero_tracer tests pass; full suite 72/72
- **Committed in:** `2a6e95f` (Task 2 commit)
- **Boundary note:** `test_hero_tracer.py` is not in this plan's `files_modified` list, but the plan's own acceptance criteria require it to stay green after Task 2 — this was the only way to satisfy both that requirement and Task 2's explicit behavior list without touching `c1_verifier.py`/`a2_compliance.py`.

---

**Total deviations:** 2 auto-fixed (2 Rule 1 bug fixes)
**Impact on plan:** Both fixes were necessary to make Task 2's explicitly-required behavior (real specialists finding real gaps) observable through the existing test suite without crossing the `c1_verifier.py`/`a2_compliance.py` file boundary. No scope creep — no new subsystem, no schema change, no architecture change.

## Issues Encountered

- This worktree had no `backend/.venv/` and no root `.env` file of its own (both gitignored, not copied into the worktree checkout). Created a fresh venv (`python -m venv backend/.venv` + `pip install -r requirements.txt`) per `backend/README.md`'s documented setup. `python-dotenv`'s `load_dotenv()` (called with no path in `llm_router.py`/`db.py`/`opa_client.py`) walks up from each module's own file location and correctly resolves the main repo's root `.env` several directories up (`.claude/worktrees/<id>/backend/app/` → … → `Sentinel_AI/.env`), so real provider keys were available without copying the file.
- `infra/apply-seed.sh` reported `ERROR: schema not found` in this sandboxed shell — not a real problem: this shell has no `docker` CLI on `PATH` (confirmed: `command -v docker` finds nothing), the same environmental gap 03-02's SUMMARY documented, so the script's `docker compose exec` probe silently fails before ever reaching Postgres. Postgres and OPA were independently confirmed live and reachable directly (`socket.connect` to 127.0.0.1:5432/8181, both open) and already correctly seeded — proven positively by every test in this plan reading real values back out of `RSK-2024-11`, `CR-2026-089`, `INC-849201`, `AR-2026-05`, and `ACC-2026-99`, none of which are fixtures.
- A real `OPENROUTER_API_KEY` (and `DEEPSEEK_API_KEY`/`GROQ_API_KEY`) being present in the root `.env` meant several of this plan's own tests initially failed with `respx.models.AllMockedAssertionError` (a real key means `call_llm()`'s internal cascade attempts a genuine, unmocked HTTP request instead of short-circuiting on a missing key) — resolved by explicitly deleting the provider keys each test doesn't intend to exercise, mirroring the convention `test_a0_orchestrator.py`/`test_llm_router.py` already established.

## User Setup Required

None - no external service configuration required beyond the already-documented `GEMINI_API_KEY`/`DEEPSEEK_API_KEY`/`GROQ_API_KEY`/`OPENROUTER_API_KEY` follow-up from plans 03-01/03-02 (live-quality classification/narration still cannot be verified without a human reviewing real model output against real queries).

## Next Phase Readiness

- The eleven-node graph now has eight real nodes (C2 stub aside: A0, A1, A2, A3, A4, A5, A6, C1) and three deliberately-deferred stubs (A7, C2, C3 — all Phase 5 territory). Phase 3's remaining plans (03-04 URS fixture/remaining A2 checks, 03-05 C1 Critical-review suite, 03-06 full hero-loop integration test) build on a graph whose fan-out reaches genuinely real agents end to end.
- `opa_client.py`'s Deviation 8 fix (datetime-safe OPA payloads) removes a landmine that would otherwise have surfaced again the first time any future plan's evidence table (e.g. `documents.created_date`/`effective_date`, `access_reviews`, `test_results.execution_date_ns` is BIGINT not TIMESTAMP so unaffected) reached `evaluate_opa_policy()`.
- No blockers. `route_specialists` and the graph topology remain exactly as Phase 2 built them — 03-04/03-05/03-06 can proceed without any topology-level coordination.

---
*Phase: 03-intelligence-retrieval*
*Completed: 2026-08-21*

## Self-Check: PASSED

All 10 claimed files found on disk; both task commits (`52810a3`, `2a6e95f`) confirmed in `git log`.
