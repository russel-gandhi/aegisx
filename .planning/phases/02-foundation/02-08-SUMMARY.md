---
phase: 02-foundation
plan: 08
subsystem: ci
tags: [github-actions, docker-compose, opa, pytest, vitest, ci]

requires:
  - phase: 02-foundation
    provides: "infra/health-check.sh, infra/verify-schema.sh, infra/apply-seed.sh, infra/verify-seed.sh (plan 02-01) — the data-tier gates this workflow invokes verbatim"
  - phase: 02-foundation
    provides: "policies/opa-gate.sh (plan 02-02) — the policy gate, invoked via its container-exec fallback route"
  - phase: 02-foundation
    provides: "backend/requirements.txt, backend/pytest.ini (plan 02-03) — the pinned dependency set and pytest rootdir the backend job installs and runs against"
  - phase: 02-foundation
    provides: "frontend/package.json build/test scripts (plan 02-04) — npm ci / npm run build / npm test, the exact commands the frontend job runs"
  - phase: 02-foundation
    provides: "backend/app/ws/copilot.py + frontend live WebSocket contract (plan 02-07) — the echo round trip the backend job's live probe exercises"
provides:
  - ".github/workflows/ci.yml — two-job GitHub Actions workflow (backend-and-policy, frontend) running every gate this phase produced on pull_request and push to main"
affects: [phase-03-onward-every-pr, "SENT-6-01 (end-to-end flow tests)", "SENT-6-06 (demo-state reset)"]

actuals:
  tokens: 2100
  tasks: 2
  commits: 2

tech-stack:
  added: []
  patterns:
    - "CI invokes the same developer-facing gate scripts (infra/*.sh, policies/opa-gate.sh) rather than re-implementing their assertions in YAML — a single definition of 'passing', not two that can drift apart"
    - "actions/ first-party references pinned to the current major tag, resolved live via `git ls-remote --tags` against the upstream repos (GitHub REST API was rate-limited from this network) rather than recalled from training data"

key-files:
  created:
    - .github/workflows/ci.yml
  modified: []

key-decisions:
  - "Resolved actions/checkout, actions/setup-python, actions/setup-node major tags live via `git ls-remote --tags` (v7, v6, v7 respectively) rather than the GitHub REST API, which returned 'rate limit exceeded' for unauthenticated requests from this network — confirmed each tag is a real, fetchable ref by pulling action.yml from raw.githubusercontent.com at that tag before using it."
  - "Python pinned to '3.13' (matching this machine's local 3.13.9) and Node to '24' (matching local v24.18.0) in setup-python/setup-node, so a CI failure specific to interpreter version is distinguishable from a genuine regression."
  - "CI creates .env by copying the committed .env.example and sed-replacing only the POSTGRES_PASSWORD line, rather than writing an independent env block — a drifted .env.example fails CI the same way it would fail a new developer's Quickstart."
  - "No backend/.venv equivalent created in CI — python -m pip install runs directly against the runner's own Python, since a GitHub-hosted runner is already the disposable, isolated environment the local .venv exists to simulate."

patterns-established:
  - "Deliberate-break proof pattern for CI gates (Task 2): break one thing, confirm the gate names it and exits non-zero, restore, confirm green again, verify git status is byte-identical to before the break — repeated once per gate family (schema, Rego, backend test, frontend test)."

requirements-completed: [ENV-02, ENV-03, ENV-04, POL-01, POL-02, ORC-01, UI-01]

coverage:
  - id: D1
    description: ".github/workflows/ci.yml exists, is valid YAML, and references all five gate scripts by path"
    requirement: "POL-01, POL-02, ORC-01"
    verification:
      - kind: unit
        ref: "node -e \"...missing check against infra/health-check.sh, infra/verify-schema.sh, infra/apply-seed.sh, infra/verify-seed.sh, policies/opa-gate.sh, backend/requirements.txt, npm ci, npm run build, pull_request\" -> 'workflow references all gates'"
        status: pass
      - kind: unit
        ref: "python -c \"import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))\" -> parsed OK, jobs: ['backend-and-policy', 'frontend']"
        status: pass
    human_judgment: false
  - id: D2
    description: "The full backend-and-policy step sequence, replayed locally from a genuinely destroyed state (docker compose down -v --remove-orphans), passes every gate in the documented order"
    requirement: "ENV-02, ENV-03"
    verification:
      - kind: integration
        ref: "docker compose down -v --remove-orphans && docker compose up -d --wait -> all 3 services Healthy; bash infra/health-check.sh -> ALL HEALTHY; bash infra/verify-schema.sh -> SCHEMA OK (27 tables, 21 FKs, 8 _ns columns); bash infra/apply-seed.sh -> SEED APPLIED; bash infra/verify-seed.sh -> SEED OK"
        status: pass
      - kind: integration
        ref: "docker compose restart opa && bash infra/health-check.sh opa -> GREEN; MSYS_NO_PATHCONV=1 bash policies/opa-gate.sh -> 42/42 opa tests PASS, live REST probe PASS, OPA GATE OK"
        status: pass
      - kind: unit
        ref: "backend/.venv/Scripts/python -m pytest -x -q (backend/) -> 32 passed"
        status: pass
    human_judgment: false
  - id: D3
    description: "The two live end-to-end checks (the phase gate's only server-required clauses) pass against a real uvicorn process, not only a TestClient"
    requirement: "ENV-04, UI-01"
    verification:
      - kind: integration
        ref: "live uvicorn on 127.0.0.1:8000; node -e \"fetch('http://127.0.0.1:8000/api/health')...\" -> 200 {\"status\":\"ok\"}"
        status: pass
      - kind: integration
        ref: "live uvicorn; node WebSocket client to ws://127.0.0.1:8000/api/copilot/stream/local-gate, connect->send->echo round trip -> WS ECHO OK"
        status: pass
    human_judgment: false
  - id: D4
    description: "The frontend job's commands (npm ci, npm run build, npm test) pass locally against the committed lockfile"
    requirement: "UI-01"
    verification:
      - kind: unit
        ref: "frontend/: npm ci -> 155 packages installed, 0 vulnerabilities; npm run build -> built in 724ms; npm test (vitest run) -> 26 passed"
        status: pass
    human_judgment: false
  - id: D5
    description: "Every gate family this workflow protects (schema, Rego policy, backend test, frontend test) has been observed turning red for a deliberate, named cause, then restored to green, with git status byte-identical to before the break"
    requirement: "POL-01, POL-02"
    verification:
      - kind: integration
        ref: "Schema break: commented out CREATE TABLE sessions -> cold restart -> bash infra/verify-schema.sh exits 1, table count == 27 FAIL (got: 26), table exists: sessions FAIL (missing); restored -> SCHEMA OK"
        status: pass
      - kind: integration
        ref: "Rego break: ANNEX11-S12-ACC-001 threshold 30 -> 300 in policies/gxp_rules.rego -> docker compose restart opa -> MSYS_NO_PATHCONV=1 bash policies/opa-gate.sh exits 1, PASS: 39/42, naming test_rule2_pending_review_98_days_overdue_violates and test_whole_bundle_all_10_seeded_gaps_produce_exactly_10_violations as FAIL; restored -> PASS: 42/42"
        status: pass
      - kind: integration
        ref: "Backend break: backend/tests/test_health.py expected body changed to {\"status\":\"definitely-not-ok\"} -> pytest -x -q exits 1, FAILED tests/test_health.py::test_health_returns_200_with_exact_body; restored -> 32 passed"
        status: pass
      - kind: integration
        ref: "Frontend break: CommandCentre.tsx h1 changed to 'Definitely Not Command Centre' -> npm test exits 1, getByRole('heading', ...) throws TestingLibraryElementError naming the missing heading; restored -> 26 passed"
        status: pass
      - kind: manual_procedural
        ref: "git status --porcelain empty after all four break/restore cycles; git check-attr text -- infra/health-check.sh -> text: set (LF normalisation still in effect)"
        status: pass
    human_judgment: false
  - id: D6
    description: "The first real GitHub Actions run on the actual PR, exercising the runner image, resolved action versions, and Docker-in-Actions behaviour"
    requirement: "POL-01, POL-02, ORC-01, UI-01"
    verification:
      - kind: manual_procedural
        ref: "Deferred per workflow.human_verify_mode: end-of-phase and the plan's own <human-check> — GitHub Actions cannot be triggered from this machine (no configured remote/push target for CI in this execution context)."
        status: deferred
    human_judgment: true
    rationale: "GitHub Actions execution is server-side and requires a real push to a GitHub-hosted remote with Actions enabled; this executor has no such remote configured. The local replay (D2-D5) proves the step sequence, the gate scripts, and the failure-path behavior byte-for-byte identical to what CI will run, but only the first real Actions run can prove the runner image, the resolved action versions at execution time, and the Actions engine's own YAML interpretation. A human must watch the first PR's Actions run to completion per the plan's <human-check>."

duration: 55min
completed: 2026-08-21
status: complete
---

# Phase 2 Plan 08: GitHub Actions CI Workflow Summary

**A two-job GitHub Actions workflow (`backend-and-policy`, `frontend`) that stands up the real Compose stack and runs every gate this phase produced — schema, seed, Rego, backend pytest, live `/api/health` and WebSocket probes, frontend build/test — via the exact same scripts developers already run locally, proven from a genuinely cold `docker compose down -v` state and proven capable of turning red for each of the four gate families it protects.**

## Performance

- **Duration:** ~55 min
- **Tasks:** 2 completed
- **Files modified:** 1 created (`.github/workflows/ci.yml`); 4 files temporarily broken and restored during Task 2's proof (net zero diff, confirmed via `git status --porcelain`)

## Accomplishments

- `.github/workflows/ci.yml`: `backend-and-policy` job brings up all three Compose services (not only the two Stage 1 strictly needs), runs the ENV-01 health gate, the schema/seed gates in the order that isolates each failure's cause, the Rego policy gate via `opa-gate.sh`'s container-exec route, the full backend pytest suite, and both live end-to-end probes (`/api/health`, WebSocket echo) against a real backgrounded `uvicorn` process with a bounded retry wait rather than a fixed sleep. `frontend` job runs in parallel with no Docker dependency: `npm ci`, `npm run build`, `npm test`.
- Triggers on `pull_request` (any branch) and `push` to `main`, with a `ref`-keyed `concurrency` group and `cancel-in-progress: true`.
- Every `uses:` reference is a first-party `actions/` action, pinned to a major tag resolved live via `git ls-remote --tags` (the GitHub REST API returned a rate-limit error from this network) and confirmed fetchable by pulling `action.yml` from that tag: `actions/checkout@v7`, `actions/setup-python@v6`, `actions/setup-node@v7`.
- No deploy, publish, release, or coverage-reporting step — the workflow's only job is running the gates this phase already defined.
- Local replay of the entire `backend-and-policy` sequence from a genuinely destroyed state (`docker compose down -v --remove-orphans`, confirmed zero volumes) passed every step in order, first try.
- All four gate families (schema, Rego policy, backend test, frontend test) were deliberately broken, confirmed to turn their gate red naming the specific cause, and restored — `git status --porcelain` empty afterward, proving the break/restore cycle left no residue.

## Task Commits

1. **Task 1: Author the CI workflow around the existing gate scripts** — `b57ab77` (feat)
2. **Task 2: Prove the pipeline locally, then prove it can go red** — no additional commit; every break performed during this task was restored to byte-identical content before completion (`git status --porcelain` confirmed empty), so its evidence lives in this SUMMARY rather than in a diff.

## Files Created/Modified

- `.github/workflows/ci.yml` — the only file left modified by this plan.

## Local Replay Evidence (Task 2)

Run from a genuinely cold state (`docker compose down -v --remove-orphans`, confirmed zero volumes before `up`):

| Step | Command | Result |
|---|---|---|
| 1 | `docker compose down -v --remove-orphans` | Containers, volumes, network removed |
| 2 | `docker compose up -d --wait` | All 3 services `Healthy` on first attempt |
| 3 | `bash infra/health-check.sh` | `postgres GREEN / qdrant GREEN / opa GREEN` — `ALL HEALTHY`, exit 0 |
| 4 | `bash infra/verify-schema.sh` | 27 tables, 21 FKs, 8 `_ns` BIGINT columns — `SCHEMA OK`, exit 0 |
| 5 | `bash infra/apply-seed.sh` | 13 `INSERT` statements — `SEED APPLIED`, exit 0 |
| 6 | `bash infra/verify-seed.sh` | Both demo systems + all 10 gap records + nanosecond-magnitude guard — `SEED OK`, exit 0 |
| 7 | `docker compose restart opa && bash infra/health-check.sh opa` | `opa GREEN` after restart |
| 8 | `bash policies/opa-gate.sh` | 42/42 `opa test` PASS, live REST probe PASS — `OPA GATE OK`, exit 0 |
| 9 | `backend/.venv/Scripts/python -m pytest -x -q` (from `backend/`) | 32 passed |
| 10 | Backgrounded `uvicorn`; `node -e "fetch('http://127.0.0.1:8000/api/health')..."` | `200 {"status":"ok"}` |
| 11 | Node native `WebSocket` client, connect→send→echo round trip | `WS ECHO OK` |
| 12 | `npm ci` (from `frontend/`) | 155 packages, 0 vulnerabilities |
| 13 | `npm run build` | Built in 724ms, `dist/` produced |
| 14 | `npm test` (`vitest run`) | 26 passed |

## Deliberate Breaks (Task 2)

Each break was applied, confirmed to turn its gate red naming the cause, then restored to byte-identical content and re-verified green.

| # | Gate | Break | Command | Result before restore | Restore verification |
|---|---|---|---|---|---|
| 1 | Schema | Commented out `CREATE TABLE sessions` in `infra/postgres/initdb/001_schema.sql`, cold-restarted the stack | `bash infra/verify-schema.sh` | Exit 1. `table count == 27 FAIL (got: 26)`, `foreign key count == 21 FAIL (got: 20)`, `table exists: sessions FAIL (missing)` | Restored table, cold-restarted again — `SCHEMA OK`, all 27 tables PASS |
| 2 | Rego policy | Changed `ANNEX11-S12-ACC-001`'s overdue threshold from `> 30` to `> 300` days in `policies/gxp_rules.rego`, restarted `opa` | `MSYS_NO_PATHCONV=1 bash policies/opa-gate.sh` | Exit 1. `PASS: 39/42`, naming `test_rule2_fraction_past_30_days_overdue_violates`, `test_rule2_pending_review_98_days_overdue_violates`, and `test_whole_bundle_all_10_seeded_gaps_produce_exactly_10_violations` as FAIL | Restored `> 30`, restarted `opa` — `PASS: 42/42`, `OPA GATE OK` |
| 3 | Backend test | Changed the expected `/api/health` body in `backend/tests/test_health.py` to `{"status": "definitely-not-ok"}` | `pytest -x -q` (from `backend/`) | Exit 1. `FAILED tests/test_health.py::test_health_returns_200_with_exact_body — AssertionError` | Restored expected body — `32 passed` |
| 4 | Frontend test | Changed `CommandCentre.tsx`'s `<h1>` text to `"Definitely Not Command Centre"` | `npm test` (from `frontend/`) | Exit 1. `TestingLibraryElementError` from `getByRole('heading', { level: 1, name: 'Command Centre' })` — element not found | Restored heading text — `26 passed` |

After all four restorations, `git status --porcelain` was empty and the full sequence above (steps 1-14) was re-run green end to end.

## Decisions Made

- Resolved action-version major tags live via `git ls-remote --tags` against `actions/checkout`, `actions/setup-python`, and `actions/setup-node` rather than the GitHub REST API (which was rate-limited for this network's unauthenticated requests), then confirmed each resolved tag (`v7`, `v6`, `v7`) is a real, fetchable ref by pulling its `action.yml` from `raw.githubusercontent.com` before committing to it in the workflow — avoids both a stale, training-data-recalled version number and an unverified guess.
- Used `MSYS_NO_PATHCONV=1` when running `policies/opa-gate.sh` locally in Git Bash, because Windows Git Bash's MSYS path-conversion layer rewrites the script's `/opa` container-exec argument into a Windows filesystem path (`C:/Program Files/Git/opa`), causing the container-exec route to fail with a spurious "no such file or directory". This is a Windows-Git-Bash-only artifact of the local development machine, not a defect in `opa-gate.sh` — the workflow's own steps run in real Linux `bash` on the GitHub-hosted runner, where no such path rewriting exists, so the workaround is a local-replay concern only and is not (and should not be) baked into `ci.yml` or `opa-gate.sh`.
- Recreated `backend/.venv` and `frontend/node_modules` in this worktree from the already-pinned `backend/requirements.txt` and `frontend/package-lock.json` before running any local replay step — both are gitignored, per-checkout artifacts that this parallel-executor worktree did not inherit, matching the same setup step plan 02-07's SUMMARY documented for its own worktree.
- Left the CI workflow's Compose bring-up unconditional on all three services (not a Stage-1-scoped subset), matching the plan's explicit instruction that skipping Qdrant would let an ENV-01 regression through unnoticed even though Stage 1 code doesn't yet call Qdrant directly.

## Deviations from Plan

None. Plan executed as written; both tasks' acceptance criteria were met without requiring a Rule 1-4 auto-fix to plan-authored code. The one adaptation (`MSYS_NO_PATHCONV=1` for the local replay) is a local-machine-only workaround for proving the pipeline on Windows Git Bash, explicitly not applied to any committed file, and is documented above and in Issues Encountered rather than tracked as a deviation against `.github/workflows/ci.yml` itself.

## Issues Encountered

- **GitHub REST API rate-limited from this network** for unauthenticated requests while resolving current action major-version tags. Worked around with `git ls-remote --tags` against the three `actions/*` repositories directly (no auth required, no rate limit hit), then double-checked each resolved tag by fetching its `action.yml` over `raw.githubusercontent.com`.
- **Windows Git Bash MSYS path-conversion mangles `policies/opa-gate.sh`'s `/opa` container-exec argument** into a Windows path, breaking the script's container-exec fallback route locally. Required `MSYS_NO_PATHCONV=1` for the local replay only (see Decisions above). Not a CI concern (Linux runner), not a script defect, and not fixed in this plan since `policies/` is outside this ticket's owned paths (BRANCHING.md §4) and the script is unmodified and correct for its actual (Linux/container) execution environment.
- **Each fresh Bash tool invocation starts a new shell that does not inherit `PATH` exports from a prior invocation** (confirmed via the environment note: Docker Desktop's CLI is not on this machine's default `PATH`). The very first `bash infra/verify-schema.sh` run in a fresh shell (without re-exporting the Docker Desktop `bin` directory first) produced a fully empty/`<none>` result for every check — not because tables were missing, but because `docker`/`docker-compose` resolved to nothing, the `dc()` helper's failure was swallowed by `psql_exec`'s `2>/dev/null`, and every query silently returned empty stdout. Re-running with `PATH` exported in the same tool call resolved this immediately and is unrelated to any code in this plan; documented here since it cost real diagnostic time and could recur for any future local Windows session that doesn't carry the PATH addition forward.

## User Setup Required

None for the workflow itself. One item requires a human with push/PR access to this repository's GitHub remote (see Coverage D6 and the Human Verification section below) — this executor has no such remote configured and cannot trigger a real Actions run.

## Windows-vs-Linux Risk Notes (plan-required)

The plan requires naming the two places the runner's Linux environment differs from local Windows development, since these are the most likely causes of a workflow that passes locally and fails on the very first real Actions run:

1. **Python interpreter path.** Locally: `backend/.venv/Scripts/python` (Windows venv layout, documented in `backend/README.md`). In CI: bare `python`, installed directly via `actions/setup-python` with no venv — a GitHub-hosted runner is already disposable and isolated, so the venv's sole local purpose (defending against this machine's global Anaconda `pip` shadowing) doesn't apply. `ci.yml` carries an inline comment stating this explicitly at the install step.
2. **Shell script line endings.** `.gitattributes` forces `*.sh` (and `Dockerfile`) to LF. Confirmed still in effect: `git check-attr text -- infra/health-check.sh` → `infra/health-check.sh: text: set`. A CRLF regression here would make every `bash infra/*.sh` invocation fail on the Linux runner with a `$'\r': command not found`-style error while continuing to work locally on this machine's Git Bash, which normalizes on checkout.

## Next Phase Readiness

- Every PR from Phase 3 onward runs this workflow automatically on `pull_request` and on `push` to `main`, per SENT-1-09's contract ("every PR from Stage 2 onward runs schema + Rego + basic API tests automatically").
- `SENT-6-01` (end-to-end flow tests) and `SENT-6-06` (demo-state reset) are documented as extending this workflow rather than replacing it — no structural change anticipated before then.
- No file outside `.github/workflows/` was left modified by this plan (`git status --porcelain` empty); `docker-compose.yml`, `.env.example`, root `README.md`, and `BRANCHING.md` are unmodified, consistent with BRANCHING.md §5's shared-file protocol.
- **Outstanding for a human:** push this branch, open the pull request, and watch the first real GitHub Actions run to completion — this is the only evidence for the runner image, the action versions actually resolved at execution time, Docker-in-Actions behavior, and the Actions engine's own interpretation of this YAML. Deferred per `workflow.human_verify_mode: end-of-phase` and the plan's own `<human-check>`; not performable from this execution context (no GitHub remote configured for a real Actions trigger).

## Self-Check: PASSED

`.github/workflows/ci.yml` verified present on disk. Task 1 commit (`b57ab77`) verified present in `git log --oneline`. `git status --porcelain` verified empty (no residue from Task 2's break/restore cycles) immediately before this SUMMARY was written.

---
*Phase: 02-foundation*
*Completed: 2026-08-21*
