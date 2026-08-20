---
phase: 02-foundation
plan: 03
subsystem: api
tags: [fastapi, pydantic, pytest, uvicorn, backend-scaffold]

# Dependency graph
requires:
  - phase: 01-environment
    provides: repo scaffold (backend/ tier README), gitignore rules for .venv/__pycache__/.pytest_cache
provides:
  - "backend/.venv — project-local, pinned Stage 1 dependency set (fastapi, pydantic, uvicorn[standard], httpx, langgraph, langchain-core, pytest)"
  - "backend/app/schemas.py — all 12 Bible Section 4.3 Pydantic application-layer models, importable and validating"
  - "backend/app/main.py — FastAPI() app object with a live GET /api/health returning 200 {\"status\": \"ok\"}"
  - "backend/pytest.ini + backend/tests/conftest.py — shared pytest harness (client, opa_base_url, pinned_now_ns fixtures) for wave-2 plans to extend"
affects: [02-05-opa-client, 02-06-langgraph-stategraph, 02-07-websocket, 02-08-ci, phase-03-agents]

actuals:
  tokens: 4200
  tasks: 3
  commits: 5

tech-stack:
  added: [fastapi==0.141.1, pydantic==2.13.4, "uvicorn[standard]==0.52.4", httpx==0.28.1, langgraph==1.2.11, langchain-core==1.6.0, pytest==9.1.1]
  patterns: ["project-local venv (never the machine's global Anaconda pip)", "TDD RED/GREEN per auto task carrying tdd=\"true\"", "application-layer BaseModel schemas kept structurally separate from forthcoming TypedDict graph-state schemas"]

key-files:
  created:
    - backend/requirements.txt
    - backend/pytest.ini
    - backend/app/__init__.py
    - backend/app/main.py
    - backend/app/schemas.py
    - backend/tests/__init__.py
    - backend/tests/conftest.py
    - backend/tests/test_health.py
    - backend/tests/test_schemas.py
  modified:
    - backend/README.md

key-decisions:
  - "Pinned pytest to 9.1.1, resolved live via `pip index versions pytest` at execution time rather than using a remembered number — the Bible/research left it unpinned by design."
  - "Replaced the Bible's `Field(default_factory=datetime.utcnow)` on AgentMessage.timestamp with `datetime.now(timezone.utc).replace(tzinfo=None)` — byte-identical naive-UTC value, no DeprecationWarning under Python 3.13.9, and stays comparable to the Bible's other naive datetime fields."
  - "Installed all seven pinned dependencies now (wave 1) even though langgraph/langchain-core/httpx aren't consumed until waves 2's 02-05/02-06 plans, per BRANCHING.md §4 file-ownership allocation — avoids three wave-2 plans all needing to edit requirements.txt."

patterns-established:
  - "Application-layer Pydantic models (app/schemas.py) vs. graph-state TypedDicts (future app/graph/state.py) are deliberately separate types with the same field names; conversion happens explicitly at the API boundary, never by cross-importing."
  - "conftest.py fixtures (client, opa_base_url, pinned_now_ns) are additive-only — later backend test files import them via pytest's fixture injection, they don't redefine them."

requirements-completed: [ENV-04]

coverage:
  - id: D1
    description: "Project-local backend/.venv with all seven Stage 1 dependencies pinned and installed, verified clean by pip check and confirmed outside the global Anaconda environment"
    requirement: "ENV-04"
    verification:
      - kind: unit
        ref: "backend/.venv/Scripts/python -m pip check"
        status: pass
      - kind: unit
        ref: "backend/.venv/Scripts/python -c \"import fastapi, pydantic, uvicorn, httpx, langgraph, langchain_core, pytest\""
        status: pass
    human_judgment: false
  - id: D2
    description: "All 12 Bible Section 4.3 Pydantic models importable from app.schemas, validating a good instance and rejecting a bad one"
    requirement: "ENV-04"
    verification:
      - kind: unit
        ref: "tests/test_schemas.py#test_all_twelve_models_importable"
        status: pass
      - kind: unit
        ref: "tests/test_schemas.py#test_agent_finding_valid_instance_round_trips_through_model_dump"
        status: pass
      - kind: unit
        ref: "tests/test_schemas.py#test_agent_finding_missing_claim_raises_validation_error"
        status: pass
      - kind: unit
        ref: "tests/test_schemas.py#test_alcoa_score_defaults_field_by_field"
        status: pass
    human_judgment: false
  - id: D3
    description: "GET /api/health returns HTTP 200 with the exact body {\"status\": \"ok\"}, both through the in-process TestClient and against a live uvicorn process on port 8000; GET / returns 404"
    requirement: "ENV-04"
    verification:
      - kind: unit
        ref: "tests/test_health.py#test_health_returns_200_with_exact_body"
        status: pass
      - kind: unit
        ref: "tests/test_health.py#test_root_returns_404"
        status: pass
      - kind: integration
        ref: "node -e \"fetch('http://127.0.0.1:8000/api/health')...\" against live uvicorn — printed 200 {\"status\":\"ok\"}"
        status: pass
    human_judgment: false
  - id: D4
    description: "pytest runs green from backend/ with the shared fixture harness (client, opa_base_url, pinned_now_ns) in place for wave-2 plans"
    requirement: "ENV-04"
    verification:
      - kind: unit
        ref: "backend/.venv/Scripts/python -m pytest -x -q (8 passed)"
        status: pass
    human_judgment: false

duration: 15min
completed: 2026-08-20
status: complete
---

# Phase 2 Plan 3: FastAPI Application Skeleton Summary

**Project-local pinned FastAPI backend (7 dependencies) with all 12 Bible Section 4.3 Pydantic models and a live `/api/health` returning `{"status": "ok"}`, backed by a shared pytest fixture harness for the two remaining wave-2 backend plans.**

## Performance

- **Duration:** ~15 min
- **Tasks:** 3 completed
- **Files modified:** 10 (9 created, 1 extended)

## Accomplishments
- `backend/.venv` created and populated with all seven pinned Stage 1 dependencies (`fastapi`, `pydantic`, `uvicorn[standard]`, `httpx`, `langgraph`, `langchain-core`, `pytest`), `pip check` clean, confirmed resolving outside the machine's global Anaconda environment
- All 12 Bible Section 4.3 Pydantic models (`EvidenceRef` through `AgentExecutionTrace`) transcribed verbatim into `app/schemas.py`, importable and validating both a good instance and a malformed one
- `GET /api/health` live on a real `uvicorn` process at port 8000, returning exactly `{"status": "ok"}`; `GET /` confirmed 404 (no unintended catch-all route)
- Shared `pytest` harness (`pytest.ini`, `tests/conftest.py` with `client`/`opa_base_url`/`pinned_now_ns` fixtures) in place for plans 02-05, 02-06, 02-07 to extend without redefining

## Task Commits

Each task was committed atomically (Tasks 2 and 3 used `tdd="true"` RED/GREEN commits):

1. **Task 1: Project-local virtualenv and the pinned Stage 1 dependency set** - `5b8f712` (feat)
2. **Task 2: Transcribe the Bible Section 4.3 Pydantic models** - `a3b3c13` (test, RED) → `e24e931` (feat, GREEN)
3. **Task 3: FastAPI entrypoint with a live /api/health** - `fe7d13a` (test, RED) → `646b219` (feat, GREEN)

_No refactor commit was needed for either TDD task — both GREEN implementations were minimal and clean on first pass._

## Files Created/Modified
- `backend/requirements.txt` - 7 exactly-pinned Stage 1 dependencies
- `backend/pytest.ini` - `testpaths = tests`, `pythonpath = .`
- `backend/app/__init__.py` - package marker
- `backend/app/main.py` - `FastAPI()` app object, `GET /api/health` route only
- `backend/app/schemas.py` - all 12 Bible Section 4.3 Pydantic models
- `backend/tests/__init__.py` - package marker
- `backend/tests/conftest.py` - `client`, `opa_base_url`, `pinned_now_ns` fixtures
- `backend/tests/test_health.py` - `/api/health` and `/` behavior tests
- `backend/tests/test_schemas.py` - 12-model import, round-trip, failure-path, defaults, timestamp tests
- `backend/README.md` - extended with `## Local setup (Stage 1)` (venv, run, test, health-check, host-side rationale)

## Decisions Made
- Resolved `pytest`'s pin live via `pip index versions pytest` (returned 9.1.1) rather than using a training-data-recalled version number, per the plan's explicit instruction.
- Kept `AgentFinding.confidence_score` as a plain `str` (not an enum) per the plan's warning that an enum would change the type Phase 3's C1 verifier emits against.
- Substituted `datetime.utcnow()` (deprecated on Python 3.13.9) with `datetime.now(timezone.utc).replace(tzinfo=None)` on `AgentMessage.timestamp`'s default factory — documented inline as a mechanical, non-semantic deviation per the plan's own instruction.
- Installed all seven dependencies in wave 1 (not split across waves) so `requirements.txt` stays a single-plan-owned file, avoiding a BRANCHING.md §4 collision across the three wave-2 backend plans.

## Deviations from Plan

None beyond the plan's own explicitly pre-authorized mechanical substitution (the `datetime.utcnow()` replacement, called out in the plan text itself and documented above, not a Rule 1-4 auto-fix). Plan executed as written.

## Issues Encountered
- `starlette.testclient` emits a `StarletteDeprecationWarning` recommending `httpx2` in place of `httpx` for `TestClient`. This is upstream Starlette/httpx ecosystem churn, not a failure — the pinned `httpx==0.28.1` (required by plan 02-05's `evaluate_opa_policy()`) is unaffected in behavior, and the warning does not fail any test or the `-W error::DeprecationWarning` check the plan actually gates on (that check targets `AgentMessage.timestamp`, not `TestClient`). No action taken; noted here for visibility if a future plan considers adopting `httpx2`.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- `backend/requirements.txt`, `backend/pytest.ini`, and `backend/tests/conftest.py` are now owned and stable — plans 02-05 (OPA client), 02-06 (LangGraph StateGraph), and 02-07 (WebSocket route) each add only their own new files against this shared base, per the plan's Rule-10 file-ownership design.
- `backend/app/main.py`'s `app` object is the exact attachment point plan 02-07 needs for the `/api/copilot/stream/{session_id}` WebSocket route.
- No blockers. The backend runs host-side (not a Compose service) for this phase per 02-RESEARCH.md Open Question 1 — `docker-compose.yml` was correctly left untouched by this plan.

## Self-Check: PASSED

All 10 files created/modified by this plan verified present on disk; all 5 task commits (`5b8f712`, `a3b3c13`, `e24e931`, `fe7d13a`, `646b219`) plus the SUMMARY commit (`e4ba4de`) verified present in `git log`.

---
*Phase: 02-foundation*
*Completed: 2026-08-20*
