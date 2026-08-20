---
phase: 02-foundation
plan: 05
subsystem: api
tags: [httpx, opa, opa-client, backend, deterministic-first, pytest]

# Dependency graph
requires:
  - phase: 02-foundation
    plan: "02"
    provides: "policies/gxp_rules.rego — package sentinel.gxp, all 10 rules serving over REST on the live OPA sidecar"
  - phase: 02-foundation
    plan: "03"
    provides: "backend/app/schemas.py (OPAViolation), backend/tests/conftest.py fixtures, backend/requirements.txt (httpx already pinned)"
provides:
  - "backend/app/opa_client.py — evaluate_opa_policy(payload) -> List[Dict[str, Any]], python_fallback_rules(payload) -> List[Dict[str, Any]], module-level OPA_URL"
  - "backend/tests/test_opa_client.py — 7 tests: live positive/negative/empty/whole-bundle, OPAViolation contract check, unreachable-host fallback, non-2xx fallback"
  - "backend/README.md — ## Bible deviations (backend tier) section, input to SENT-7-05"
affects: [phase-03-agents-a2-compliance, phase-03-c1-evidence-verifier, phase-05-audit-events-opa-rule-ids]

actuals:
  tokens: 4150
  tasks: 2
  commits: 2

tech-stack:
  added: []
  patterns: ["async httpx.AsyncClient POST with an environment-configurable endpoint, both httpx.RequestError and httpx.HTTPStatusError routed to the same degrade-not-crash fallback", "module-level logging.getLogger(__name__) instead of print() for operational diagnostics"]

key-files:
  created:
    - backend/app/opa_client.py
    - backend/tests/test_opa_client.py
  modified:
    - backend/README.md

key-decisions:
  - "Deviation 1: OPA_URL read from an environment variable (default http://127.0.0.1:8181/v1/data/sentinel/gxp/violation) instead of the Bible's hardcoded localhost URL — the only way to exercise the fallback branch without disrupting the shared OPA container."
  - "Deviation 2: httpx.HTTPStatusError caught alongside httpx.RequestError — the Bible's own raise_for_status() raises a class its own except clause would not catch, which would crash the calling agent on any non-2xx OPA response."
  - "Deviation 3: logging.getLogger(__name__).warning(...) replaces the Bible's print() — a server process's stdout is not a durable diagnostic channel."
  - "python_fallback_rules() stays a genuine empty-list stub, per the Bible's own 'omitted for brevity' note — no second, independently-drifting copy of the 10 Rego rules was hand-built in Python."
  - "Returned violations are raw dicts, not OPAViolation instances — Phase 3's C1 verifier is the component that types and scores them; this module only proves the dict shape matches via a dedicated contract test."

patterns-established:
  - "Backend-tier Bible deviations are recorded in backend/README.md under a dedicated ## Bible deviations (backend tier) heading, mirroring policies/BIBLE-DEVIATIONS.md's what-Bible-says/what-was-implemented/why format, all routed to SENT-7-05."

requirements-completed: [POL-02]

coverage:
  - id: D1
    description: "evaluate_opa_policy() POSTs to the real OPA REST endpoint on the live sidecar and returns the actual violation objects OPA produced, never a mock"
    requirement: "POL-02"
    verification:
      - kind: integration
        ref: "backend/tests/test_opa_client.py::test_live_single_document_positive_case_returns_annex11_s4_doc_001"
        status: pass
      - kind: integration
        ref: "backend/tests/test_opa_client.py::test_live_single_document_negative_case_returns_empty_list"
        status: pass
      - kind: integration
        ref: "backend/tests/test_opa_client.py::test_live_empty_payload_returns_empty_list_without_error"
        status: pass
    human_judgment: false
  - id: D2
    description: "A payload carrying all 10 seeded gap records returns all 10 rule IDs through the Python client, matching plan 02-02's Rego integration fixture"
    requirement: "POL-02"
    verification:
      - kind: integration
        ref: "backend/tests/test_opa_client.py::test_live_whole_bundle_all_10_seeded_gaps_produce_exactly_10_violations"
        status: pass
      - kind: unit
        ref: "backend/tests/test_opa_client.py::test_every_returned_violation_validates_as_opa_violation_model"
        status: pass
    human_judgment: false
  - id: D3
    description: "When OPA is unreachable or answers non-2xx, evaluate_opa_policy() returns python_fallback_rules() instead of raising, and logs a warning"
    requirement: "POL-02"
    verification:
      - kind: integration
        ref: "backend/tests/test_opa_client.py::test_unreachable_host_returns_empty_list_and_logs_warning"
        status: pass
      - kind: integration
        ref: "backend/tests/test_opa_client.py::test_non_2xx_status_returns_empty_list_and_logs_warning"
        status: pass
      - kind: manual
        ref: "docker compose stop opa; pytest -q — only the 3 live tests failed with clean assertion errors, the 2 fallback tests and the negative-case test stayed green; docker compose start opa; pytest -x -q — 15/15 passed"
        status: pass
    human_judgment: false
  - id: D4
    description: "No LLM participates in any part of this call path (Bible Section 1.3)"
    requirement: "POL-02"
    verification:
      - kind: manual
        ref: "backend/app/opa_client.py contains no model/LLM import or call — httpx and logging/os/typing only"
        status: pass
    human_judgment: false

duration: 35min
completed: 2026-08-21
status: complete
---

# Phase 2 Plan 5: OPA Backend Client (SENT-1-04) Summary

**`evaluate_opa_policy()` POSTs to the live OPA sidecar over `httpx.AsyncClient` and returns OPA's real violations for all 10 seeded gap records, degrading to a documented `python_fallback_rules()` stub on both connection failure and non-2xx status rather than crashing the calling agent.**

## Performance

- **Duration:** ~35 min
- **Tasks:** 2 completed
- **Files modified:** 3 (2 created, 1 extended)

## Accomplishments

- `backend/app/opa_client.py` — `async evaluate_opa_policy(payload)` POSTs `{"input": payload}` to `OPA_URL` with a 2.0-second timeout, returns `response.json().get("result", [])` on success
- Both `httpx.RequestError` (unreachable) and `httpx.HTTPStatusError` (non-2xx) degrade to `python_fallback_rules(payload)` — an intentional empty-list stub, documented as deliberately not mirroring the 10 Rego rules in Python
- `backend/tests/test_opa_client.py` — 7 tests: live single-document positive (`ANNEX11-S4-DOC-001` against `DOC-2026-OM-99`), negative, empty payload, whole-bundle (all 10 seeded gaps → all 10 rule IDs), `OPAViolation` contract check, and two failure-path tests each asserting an empty return, no raised exception, and a captured `caplog` warning
- `backend/README.md` extended with `## Bible deviations (backend tier)`, recording the configurable `OPA_URL`, the added `HTTPStatusError` branch, and logging-in-place-of-`print`, all routed to `SENT-7-05`

## Task Commits

Each task was committed atomically:

1. **Task 1: Implement `evaluate_opa_policy()` and `python_fallback_rules()`** — `d9faa89` (feat)
2. **Task 2: Integration and failure-path test suite, plus deviation record** — `83866fb` (test)

## Files Created/Modified

- `backend/app/opa_client.py` — the OPA REST client and its documented fallback stub
- `backend/tests/test_opa_client.py` — POL-02 coverage (live + failure-path)
- `backend/README.md` — extended with `## Bible deviations (backend tier)`

## Decisions Made

- All three Bible deviations from Task 1's plan text were implemented and verified live (grep-checked for exact acceptance-criteria counts): configurable `OPA_URL`, `httpx.HTTPStatusError` caught alongside `httpx.RequestError`, and `logging.getLogger(__name__).warning(...)` in place of `print()`.
- Kept the module docstring and function docstrings free of the literal strings `raise_for_status` / `timeout=2.0` outside the one line of actual code each appears on, so the plan's `grep -c` acceptance criteria (exactly 1 each) hold precisely rather than being inflated by prose references.
- Built the whole-bundle test payload from the exact literal seed values in `.planning/phases/02-foundation/02-01-PLAN.md` Task 2 (all historical dates, years in the past relative to the current run date), so the date-sensitive rules remain overdue under the real wall clock without needing to pin `time.now_ns()` the way plan 02-02's Rego suite does. This proves a genuinely different claim than `opa test`: the same 10 rules fire over HTTP, through Python, against the running server, under the real clock.
- Chose `http://127.0.0.1:9/...` (a closed port) for the unreachable-host test and `http://127.0.0.1:8181/nonexistent-route` (the live host, a 404 path) for the non-2xx test — verified live via `node -e "require('net').connect(...)"` and `node -e "fetch(...)"` before writing the assertions, rather than assuming the responses.
- `python_fallback_rules()` remains a genuine empty-list stub per the plan's explicit instruction — no second, hand-built copy of the 10 Rego rules exists in Python, since a second independently-drifting copy of the compliance logic is a worse failure mode than no copy (Bible Section 1.3 rationale, carried into the module docstring).

## Deviations from Plan

None beyond the three Bible deviations the plan itself pre-authorized and required (Task 1's action text), which are documented above and in `backend/README.md`. Plan executed as written.

### TDD Gate Compliance

Both tasks carry `tdd="true"`, but the plan's own task structure does not follow a strict per-task RED→GREEN split: Task 1's declared `<files>` is `backend/app/opa_client.py` only (an inline one-liner `<verify>`, not a persisted failing test), and Task 2 is the task that creates the persisted `test_opa_client.py` test file, after the implementation already exists. This matches the plan text exactly — Task 1 was committed as a single `feat` commit (verified via the plan's own inline verify command before committing), Task 2 as a single `test` commit adding the full pytest suite plus the README deviation record. No RED-before-implementation commit was structurally possible given how the plan allocated files across the two tasks; this is a plan-structure characteristic, not an execution shortcut, and every behavior in Task 1's `<behavior>` list is covered by a passing test in Task 2.

## Issues Encountered

- **Missing `.env`:** this worktree had no `.env` (gitignored, per environment note). Copied `.env.example` to `.env` before `docker compose` commands would resolve; not committed.
- **No project-local `backend/.venv` in this worktree:** plan 02-03's venv was created in a different worktree and is gitignored, so it did not carry over. Recreated it here (`python -m venv backend/.venv` + `pip install -r backend/requirements.txt`) per `backend/README.md`'s own setup instructions before running any verification.
- **`policies/opa-gate.sh`'s `opa test` leg showed a false failure** (`OCI runtime exec failed: ... "C:/Program Files/Git/opa": stat ... no such file`) — confirmed this is the documented Git Bash path-mangling artifact from the environment note, not a real test failure: `MSYS_NO_PATHCONV=1 docker compose exec opa opa test /policies -v` passed 42/42, and the gate script's own live-REST-probe leg passed. No action needed.
- **`docker compose ps` initially errored** with `POSTGRES_PASSWORD is unset` until `.env` was copied in — resolved by the `.env` copy above; not a code issue.

## User Setup Required

None — no external service configuration required. Docker Desktop's CLI (`docker`, `docker compose`) needed the PATH addition noted in the environment note to be reachable from Git Bash in this session; already documented, not project-persistent.

## Next Phase Readiness

- `backend/app/opa_client.py`'s `evaluate_opa_policy()` is the exact seam Phase 3's A2 Compliance agent calls for real evaluations, and its returned dicts are the exact shape Phase 3's C1 `calculate_confidence()` (SENT-2-12) consumes as one of its two independent evidence sources.
- `OPA_URL`'s default is correct for host-side backend processes calling the Compose-published OPA container; no `.env.example` change was needed or made.
- No blockers for Phase 3.

## Self-Check: PASSED

- `backend/app/opa_client.py` — FOUND
- `backend/tests/test_opa_client.py` — FOUND
- `backend/README.md` — FOUND, contains `## Bible deviations (backend tier)`, `SENT-7-05`, `OPA_URL`
- Commit `d9faa89` — FOUND in `git log`
- Commit `83866fb` — FOUND in `git log`
- Full backend suite (`pytest -x -q` from `backend/`): 15/15 passed with OPA running
- OPA-stopped run: only the 3 live tests failed (clean `AssertionError`, not an unhandled traceback); the negative-case, empty-payload, and both failure-path tests stayed green
- OPA restarted; `infra/health-check.sh opa` → GREEN; full suite re-ran 15/15 green

---
*Phase: 02-foundation*
*Completed: 2026-08-21*
