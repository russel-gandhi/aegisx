---
phase: 06-product-experience
plan: 02
subsystem: ui
tags: [react, fastapi, sqlite, svg, vitest, pytest]

requires:
  - phase: 06-product-experience
    provides: Copilot chat + live topology (06-01) — schemas.py/main.py conventions this plan extends
provides:
  - GET /api/systems/{system_id}/access-supplier-signals backend route (overdue access reviews + overdue suppliers)
  - ReadinessDial.tsx — hand-rolled SVG arc readiness dial, no chart library
  - HealthMiniCard.tsx — shared shell for 6 independent-status mini-cards
  - CommandCentre.tsx rebuilt as a live dashboard (dial + 6 mini-cards) computed from real backend data, never the stale gxp_systems.readiness_score seed column
affects: [06-product-experience-03-guided-tour]

actuals:
  tokens: 8300
  tasks: 2
  commits: 2

tech-stack:
  added: []
  patterns:
    - "Client-side aggregation over Promise.allSettled per-system fetches, never Promise.all — partial failure degrades gracefully instead of blanking the page"
    - "Readiness percentage always computed live from assurance-cards pass/fail ratio, never from a stale seed column"

key-files:
  created:
    - backend/app/routes/system_signals.py
    - backend/tests/test_routes_system_signals.py
    - frontend/src/components/ReadinessDial.tsx
    - frontend/src/components/HealthMiniCard.tsx
    - frontend/src/__tests__/CommandCentre.test.tsx
  modified:
    - backend/app/main.py
    - backend/app/schemas.py
    - frontend/src/pages/CommandCentre.tsx
    - frontend/src/lib/api.ts

key-decisions:
  - "Fixed a contradiction in 06-02-PLAN.md itself: <acceptance_criteria> stated the two-systems/one-failing-check-each scenario should read 88% (7/8), while <behavior> stated 75% (6/8) for the same setup. The correct arithmetic for totalChecks = 4 * fulfilledSystemsCount = 8, with 2 failing cards (one per system), is 6/8 = 75% — matching <behavior> and the second unit test's analogous single-system 3/4 = 75% case. Corrected the acceptance_criteria text and the test assertion (CommandCentre.test.tsx) to 75%, not the component implementation."
  - "Readiness dial and all 6 mini-cards read exclusively from live GET /api/systems/{id}/assurance-cards, /access-supplier-signals, /api/actions, and /api/audit/verify — never gxp_systems.readiness_score (confirmed stale/static per 06-RESEARCH.md Pitfall 1)."

patterns-established:
  - "Pattern: per-card independent loading/ready/error status via a shared HealthMiniCard shell, so one slow/failed backing call never blocks the other 5 cards from rendering."

requirements-completed: [UI-03]

coverage:
  - id: D1
    description: "Command Centre readiness dial computed live from assurance-cards pass/fail ratio across both systems, with a working system selector narrowing to one system's own 4-check denominator"
    requirement: "UI-03"
    verification:
      - kind: unit
        ref: "frontend/src/__tests__/CommandCentre.test.tsx#computes a 75% dial and card counts of 1 from one failing check per system"
        status: pass
      - kind: unit
        ref: "frontend/src/__tests__/CommandCentre.test.tsx#narrows the dial to a single system 4-check denominator when selected"
        status: pass
    human_judgment: false
  - id: D2
    description: "6 fixed mini-cards render in fixed order, each independently sourced (documentation/traceability, periodic review, remediation/approvals, audit trail integrity, access reviews, supplier qualification incl. named overdue supplier)"
    requirement: "UI-03"
    verification:
      - kind: unit
        ref: "frontend/src/__tests__/CommandCentre.test.tsx (mini-card count and content assertions)"
        status: pass
    human_judgment: false
  - id: D3
    description: "New GET /api/systems/{system_id}/access-supplier-signals endpoint returning overdue access reviews and overdue suppliers (incl. named suppliers)"
    requirement: "UI-03"
    verification:
      - kind: unit
        ref: "backend/tests/test_routes_system_signals.py"
        status: pass
    human_judgment: false
  - id: D4
    description: "Partial-failure and full-failure degradation: one system down renders a partial-data note and dismissible banner; every call failing renders the empty state"
    requirement: "UI-03"
    verification:
      - kind: unit
        ref: "frontend/src/__tests__/CommandCentre.test.tsx (partial-failure and empty-state describe blocks)"
        status: pass
    human_judgment: false

duration: ~50min (includes a mid-execution stall recovered by the orchestrator diagnosing a plan/test contradiction)
completed: 2026-08-28
status: complete
---

# Phase 6 Plan 02: Command Centre Dashboard Summary

**Command Centre rebuilt as a live dashboard: hand-rolled SVG readiness dial + 6 independently-sourced mini-cards, backed by one new FastAPI route and client-side Promise.allSettled aggregation — never the stale readiness_score seed column.**

## Performance

- **Duration:** ~50 min
- **Tasks:** 2
- **Files modified:** 9 (5 created, 4 modified)

## Accomplishments
- New `GET /api/systems/{system_id}/access-supplier-signals` backend route (overdue access reviews + overdue suppliers, named), mirroring the existing `_check_a6`/`_system_exists` query patterns with no f-string SQL.
- `ReadinessDial.tsx`: a 160×160 hand-rolled SVG arc dial, color-banded (emerald ≥80%, amber 50–79%, orange <50%), animating `stroke-dashoffset` only when the computed percent actually changes.
- `HealthMiniCard.tsx`: shared shell for the 6 fixed mini-cards, each with independent loading/ready/error status and a staggered fade-in mount transition.
- `CommandCentre.tsx` rebuilt: aggregates `fetchAssuranceCards` + `fetchSystemSignals` (per system, `Promise.allSettled`) plus global `fetchActionProposals` + `fetchChainVerification` into a live dial and 6 mini-cards. System selector narrows scope to one system. Partial failure renders a dismissible banner + partial-data note (already-loaded cards keep their data); total failure renders the empty state.

## Task Commits

Each task was committed atomically:

1. **Task 1: access/supplier overdue-signals backend endpoint (D-07 mini-card #4/#5 data source)** - `eee76db` (feat)
2. **Task 2: Command Centre dashboard — dial + 6 mini-cards, client-side aggregation (D-06, D-07)** - `0c354c5` (feat)

## Files Created/Modified
- `backend/app/routes/system_signals.py` - new access/supplier-signals route
- `backend/app/schemas.py` - `SystemSignalsResponse`
- `backend/app/main.py` - router registration
- `backend/tests/test_routes_system_signals.py` - route unit tests
- `frontend/src/components/ReadinessDial.tsx` - SVG readiness dial
- `frontend/src/components/HealthMiniCard.tsx` - shared mini-card shell
- `frontend/src/pages/CommandCentre.tsx` - rebuilt dashboard page
- `frontend/src/lib/api.ts` - `fetchSystemSignals`, `fetchChainVerification` + response types
- `frontend/src/__tests__/CommandCentre.test.tsx` - component test suite

## Decisions Made
- Corrected a planning-doc contradiction (06-02-PLAN.md's `<acceptance_criteria>` said 88%/7-8 where `<behavior>` correctly said 75%/6-8 for the identical two-systems-one-failing-check-each scenario) — fixed the plan text and the test assertion to 75%, the arithmetically correct value; the component implementation was never wrong.
- Readiness computation strictly follows D-06: `passed/total` from live assurance-cards data, `total = 4 * fulfilledSystemsCount`; never `gxp_systems.readiness_score`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Plan defect] 06-02-PLAN.md acceptance_criteria/behavior contradiction (88% vs 75%)**
- **Found during:** Task 2 (Command Centre test authoring) — the executor's `CommandCentre.test.tsx` assertion (88%) matched `<acceptance_criteria>` but failed against the actual, correctly-specified `<behavior>`-driven implementation (75%), causing repeated test failures.
- **Issue:** Plan's own two sections gave contradictory expected values for the same fixture setup; the 88% figure was a planning arithmetic error (7/8 does not correspond to "1 failing check each" of 2 systems at 4 checks/system — that setup yields 2 failures across 8 checks = 75%).
- **Fix:** Corrected `<acceptance_criteria>` in 06-02-PLAN.md and the test's expected value/description to `75%`, matching `<behavior>` and the arithmetic.
- **Files modified:** `.planning/phases/06-product-experience/06-02-PLAN.md`, `frontend/src/__tests__/CommandCentre.test.tsx`
- **Verification:** `npx vitest run src/__tests__/CommandCentre.test.tsx` → 10/10 passed; full frontend suite 129/129 passed; backend suite 379/379 passed.
- **Committed in:** `0c354c5` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (plan arithmetic defect)
**Impact on plan:** Corrects a self-contradictory acceptance criterion; no scope creep, no behavior change to shipped code.

## Issues Encountered
The executing agent stalled twice on infra timeouts while investigating the above test failure without recognizing it as a plan-doc defect rather than an implementation bug. The orchestrator diagnosed the root cause directly (read `<behavior>` vs `<acceptance_criteria>`, recomputed the arithmetic), applied the fix, and the agent's own committed implementation code required no changes — only the test assertion and the plan's own inconsistent prose needed correction.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
Command Centre is fully live-data-driven and ready for the Guided Tour (06-03) to drive a user through it. `fetchChainVerification` (GET `/api/audit/verify`) now has its first frontend caller here, available for 06-03's audit-integrity tour beat to reuse.

---
*Phase: 06-product-experience*
*Completed: 2026-08-28*
