---
phase: quick
plan: 260827-0ls
subsystem: testing
tags: [vitest, sse, streaming, mocking, react-testing-library]

# Dependency graph
requires:
  - phase: quick/260826-p1q
    provides: streamAssuranceCards SSE client in frontend/src/lib/api.ts, consumed by FindingInvestigation.tsx
provides:
  - Shared SSE mock-response builder (frontend/src/__tests__/helpers/sseFetch.ts) used by every test that stubs the assurance-cards route
  - First direct contract tests for streamAssuranceCards (happy path, empty stream, chunk-split buffering, in-stream error frame, unterminated-frame remainder flush, non-2xx rejection)
  - Restored green frontend suite (93/93) after the 8-test cross-phase regression Phase 5's gate caught
affects: [phase-06-product-experience, any future test touching assurance-cards or the SSE stream contract]

# Actuals (#2632)
actuals:
  tokens: 4419
  tasks: 2
  commits: 3

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Shared vi.stubGlobal fetch router (stubAssuranceCardsFetch) with pluggable extraRoutes, so one builder serves every test file that touches the assurance-cards + evidence-graph + generate-capa routes without hand-rolled per-file stream text"

key-files:
  created:
    - frontend/src/__tests__/helpers/sseFetch.ts
    - frontend/src/__tests__/streamAssuranceCards.test.ts
  modified:
    - frontend/src/__tests__/AssuranceCard.test.tsx
    - frontend/src/__tests__/RoleSelector.test.tsx

key-decisions:
  - "helpers/sseFetch.ts deliberately carries no .test. segment in its filename so vitest's name-based include pattern does not collect it as a suite"
  - "Types SSE frames against the real exported AssuranceCardStreamFrame union (import type) so a future backend frame-shape change breaks the build here rather than silently drifting from the mock"
  - "stubAssuranceCardsFetch accepts an extraRoutes array consulted before its own defaults, letting RoleSelector.test.tsx's RBAC POST branch reuse the one router instead of hand-rolling a second"

patterns-established:
  - "Pattern 1: mock-response builders live in __tests__/helpers/ as plain (non-suite) modules, imported by name, never duplicated per test file"

requirements-completed: [EVID-03]

coverage:
  - id: D1
    description: "streamAssuranceCards has direct contract coverage for the first time: happy path (two cards + done), empty stream (done, count 0), chunk-split buffering (1-byte chunks), in-stream error frame, unterminated trailing-frame remainder flush, and non-2xx ApiError rejection"
    requirement: "EVID-03"
    verification:
      - kind: unit
        ref: "frontend/src/__tests__/streamAssuranceCards.test.ts (6 tests, all pass)"
        status: pass
    human_judgment: false
  - id: D2
    description: "The 8 tests broken by 260826-p1q's streaming migration (2 in AssuranceCard.test.tsx's /findings page block, 4 in its /findings Blast Radius links block, 1 RBAC-denial case in RoleSelector.test.tsx, plus the 1 already-passing rejected-fetch case left untouched) pass again through the real streamAssuranceCards parser, not a relaxed assertion"
    requirement: "EVID-03"
    verification:
      - kind: unit
        ref: "frontend/src/__tests__/AssuranceCard.test.tsx + RoleSelector.test.tsx (npm run test -- --run: 93/93 passed)"
        status: pass
    human_judgment: false

duration: 16min
completed: 2026-08-27
status: complete
---

# Quick Task 260827-0ls: Fix Cross-Phase Regression (8 Frontend Tests) Summary

**Shared SSE mock-response builder plus direct `streamAssuranceCards` contract tests, migrating the 8 tests 260826-p1q's streaming migration broke back to green without touching any production file.**

## Performance

- **Duration:** 16 min
- **Started:** 2026-08-27T00:34:45Z (first baseline test run confirming 79 passed / 8 failed)
- **Completed:** 2026-08-27T00:50:02Z
- **Tasks:** 2
- **Files modified:** 4 (2 created, 2 modified)

## Accomplishments
- Built one shared mock-response builder (`helpers/sseFetch.ts`) that is the single place the SSE wire format is encoded for the frontend test suite — `sseBody`, `streamingResponse`, `assuranceCardsStreamResponse`, `jsonResponse`, and the `stubAssuranceCardsFetch` router with pluggable `extraRoutes`
- Gave `streamAssuranceCards` its first direct test coverage (6 new tests: happy path, empty stream, 1-byte chunked buffering, in-stream error frame, unterminated-frame remainder flush, non-2xx rejection), proven against the real, unmodified production parser — confirmed RED (import failure) with the helper removed, then GREEN with it restored
- Migrated all 8 regressed tests across `AssuranceCard.test.tsx` and `RoleSelector.test.tsx` onto the shared builder, changing only the mocking layer — zero assertion, fixture, or test-name edits
- Restored the frontend suite to fully green: 93/93 passed (87 pre-existing + 6 new), with the backend suite (367 passed, 0 failed) and both production files (`api.ts`, `FindingInvestigation.tsx`) confirmed byte-identical throughout

## Task Commits

Each task was committed atomically, split RED/GREEN per its `tdd="true"` marking:

1. **Task 1 (RED): streaming-contract tests** - `0ed5a15` (test) — added `streamAssuranceCards.test.ts`; confirmed failing (import error) without the helper
2. **Task 1 (GREEN): SSE mock builder** - `3b12497` (feat) — added `helpers/sseFetch.ts`; confirmed all 6 tests pass, `tsc -b` clean
3. **Task 2: migrate 8 regressed tests** - `2f008ea` (test) — `AssuranceCard.test.tsx` + `RoleSelector.test.tsx` onto `stubAssuranceCardsFetch`

**Plan metadata:** commit deferred to orchestrator per this task's constraints (docs artifacts not committed by the executor)

_Note: Task 1 carried `tdd="true"` and used the RED→GREEN split; Task 2 was a plain migration commit._

## Files Created/Modified
- `frontend/src/__tests__/helpers/sseFetch.ts` - Shared SSE mock-response builder: `ASSURANCE_CARDS_STREAM_PATH`, `sseBody`, `streamingResponse`, `assuranceCardsStreamResponse`, `jsonResponse`, `stubAssuranceCardsFetch`
- `frontend/src/__tests__/streamAssuranceCards.test.ts` - 6 direct contract tests for `streamAssuranceCards`
- `frontend/src/__tests__/AssuranceCard.test.tsx` - Retired its two local single-purpose stub helpers (`stubFetchOnce`, the inline body of `stubFindingsAndGraph`) in favor of the shared builder; 6 affected tests unchanged in assertion/fixture/name
- `frontend/src/__tests__/RoleSelector.test.tsx` - Rebuilt the RBAC-denial test's router on `stubAssuranceCardsFetch` with an `extraRoutes` POST branch for `generate-capa`; verbatim permission-sentence assertion untouched

## Decisions Made
- Filename `sseFetch.ts` (no `.test.` segment) so vitest's default include pattern does not collect it as an (empty, failing) suite
- `omitTerminator` strips the trailing `\n\n` from the whole composed body rather than adding a partial one, so the "final frame with no trailing blank line" test genuinely exercises the reader-done remainder flush with no terminator at all, not a single stray `\n`
- Left `AssuranceCard.test.tsx`'s local `stubFindingsAndGraph` wrapper function in place (its five call sites unchanged) but reimplemented its body as a thin delegate to `stubAssuranceCardsFetch`, keeping the diff minimal per the plan's "mocking layer only" constraint

## Deviations from Plan

None — plan executed exactly as written. Two environment-setup steps were required before any task work (both precondition-type, not code deviations): `frontend/node_modules` did not exist in this fresh worktree, so `npm ci` was run from the existing `package-lock.json` (not a new package add, so outside the package-legitimacy gate); similarly `backend/.venv` did not exist in the worktree, so the backend cross-check ran using the main checkout's existing venv (`C:/Users/Kashish Gandhi/Desktop/Sentinel_AI/backend/.venv/Scripts/python.exe`) pointed at this worktree's `backend/` directory and code — no backend file was opened or edited, satisfying the plan's `git diff --stat` constraint.

## Issues Encountered
- Worktree fork base was one merge behind `main` (missing Phase 5's full merge, `260826-p1q`'s plan, and this quick task's own plan file) — resolved with `git merge --ff-only main` before any edits, per the standing worktree-freshness instruction.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Frontend suite is green (93/93) and now has direct coverage of the SSE streaming contract that shipped with no tests in 260826-p1q — closes the coverage hole that let that migration land undetected at merge time
- Backend suite unaffected (367 passed, 0 failed)
- `helpers/sseFetch.ts` is available for any future test file that needs to stub the assurance-cards stream, evidence-graph, or generate-capa routes — no reason to hand-roll SSE frame text again

---
*Phase: quick*
*Completed: 2026-08-27*

## Self-Check: PASSED

- FOUND: frontend/src/__tests__/helpers/sseFetch.ts
- FOUND: frontend/src/__tests__/streamAssuranceCards.test.ts
- FOUND: commit 0ed5a15
- FOUND: commit 3b12497
- FOUND: commit 2f008ea
