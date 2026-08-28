---
phase: 06-product-experience
plan: 03
subsystem: ui
tags: [react, react-joyride, react-router, vitest, guided-tour]

requires:
  - phase: 06-product-experience
    provides: "Copilot chat + live topology (06-01) -- useLocation().state?.prefillQuery seam this plan's tour drives into"
  - phase: 06-product-experience
    provides: "Command Centre dashboard (06-02) -- readiness dial + Audit Trail Integrity mini-card this plan's tour spotlights"
provides:
  - "GuidedTourOverlay.tsx -- the 8-step interactive react-joyride overlay (Bible Section 14.4, SENT-5-08) driving a user through Command Centre -> Copilot hero query -> AssuranceCard -> Blast Radius -> injected AI Safety input -> Generate CAPA + Approve -> Audit Integrity -> closing message"
  - "resolveRemediationDecision() -- pure, exported D-09 idempotency guard deciding generate / approve-existing / skip-terminal from live /api/actions state"
  - "data-tour selector attributes on CommandCentre.tsx, Copilot.tsx, FindingInvestigation.tsx, ActionProposalCard.tsx (additive only, no functional change to any of the four)"
affects: [06-verify-work, 06-secure-phase]

actuals:
  tokens: 10433
  tasks: 2
  commits: 2

tech-stack:
  added: ["react-joyride@3.2.0"]
  patterns:
    - "Guard logic (D-09) exposed as a pure, independently-unit-testable decision function rather than inline effect logic -- resolveRemediationDecision(findingId, proposals)"
    - "Idempotency guards for repeat-run demo flows are driven by a direct re-fetch of the source-of-truth REST endpoint (GET /api/actions), never a session-agnostic WS broadcast"
    - "react-joyride's target:'body'/placement:'center' pattern used for a target-less closing/welcome step, instead of a bespoke non-Joyride overlay"

key-files:
  created:
    - frontend/src/lib/tourSteps.ts
    - frontend/src/components/GuidedTourOverlay.tsx
    - frontend/src/__tests__/GuidedTourOverlay.test.tsx
  modified:
    - frontend/package.json
    - frontend/package-lock.json
    - frontend/src/App.tsx
    - frontend/src/pages/CommandCentre.tsx
    - frontend/src/pages/Copilot.tsx
    - frontend/src/pages/FindingInvestigation.tsx
    - frontend/src/components/ActionProposalCard.tsx

key-decisions:
  - "react-joyride 3.2.0's actual installed API (Props.onEvent + EventData, top-level options prop) differs materially from the plan's <action> text, which was written against the classic v2 API (callback prop, styles={{options:{...}}} including spotlightShadow). Implemented against the real v3 API: options prop for arrowColor/backgroundColor/overlayColor/primaryColor/textColor (transcribed verbatim from UI-SPEC), onEvent handler using the same ACTIONS/EVENTS/STATUS constants, and styles.spotlight with a CSS drop-shadow filter as the closest available approximation of the v2-only spotlightShadow value (documented as a deviation, not a silent substitution)."
  - "Resolved a plan-vs-behavior tension on Step 6 (Controlled Remediation): the plan's <acceptance_criteria> literally says 'the tour's step-6 flow calls generateCapa exactly once,' but the more detailed <behavior> paragraph says the tour 'proceeds to click-guide the real Generate CAPA button' and only reacts 'on the real click's generateCapa response resolving.' Implemented per <behavior> (the tour never calls generateCapa() itself; it polls GET /api/actions to detect the real click's result) and satisfied the acceptance criterion's literal intent via a full end-to-end integration test proving generateCapa is called exactly once by the real page in response to a real click, with the tour correctly detecting it via polling rather than a second, redundant call."
  - "Step 8 (closing message) implemented as a real react-joyride step (target:'body', placement:'center') rather than a bespoke overlay outside Joyride's lifecycle -- letting Joyride's own STATUS.FINISHED event naturally fire when the user clicks through the last configured step, instead of racing a custom 'step 9' state against Joyride's own tour-end detection."
  - "The closing step's primary button doubles as 'Restart Tour' (clicking it triggers STATUS.FINISHED + ACTIONS.NEXT, which immediately restarts the tour at step 1) and the Skip button doubles as 'Explore Freely' (STATUS.FINISHED/SKIPPED with a non-NEXT action just ends the tour) -- satisfies 06-UI-SPEC.md's 'offers Restart Tour / Explore Freely' requirement without inventing a second button pair."
  - "This worktree branch (worktree-agent-a6acd92b04ff164d3) was forked from a commit predating all of 06-01/06-02's work landing on main (18 commits behind). Merged main into the branch before starting (clean fast-forward-style merge, merge-base was a direct ancestor) to bring in the Copilot chat, Command Centre, and their data-tour target surfaces this plan depends on."

patterns-established:
  - "Idempotency/repeat-run guards for any future demo-automation feature should follow resolveRemediationDecision()'s shape: a pure function taking the live REST response and returning a discriminated-union decision, kept separate from the effect/network-orchestration code around it, so the decision logic is unit-testable without mocking timers or DOM positioning."

requirements-completed: [UI-03, UI-04]

coverage:
  - id: D1
    description: "8-step Guided Tour overlay drives a user through Command Centre, Copilot hero query, the streamed AssuranceCard, Blast Radius, an injected AI Safety input, Controlled Remediation (Generate CAPA + Approve), Audit Integrity, and a closing message -- every step a real page/target, persistent 'Step N of 8' counter throughout"
    requirement: UI-04
    verification:
      - kind: unit
        ref: "frontend/src/__tests__/GuidedTourOverlay.test.tsx#renders the entry banner and starts the tour"
        status: pass
      - kind: unit
        ref: "frontend/src/__tests__/GuidedTourOverlay.test.tsx#renders a centered closing step (\"Step 8 of 8\") with no real-page target"
        status: pass
    human_judgment: false
  - id: D2
    description: "D-09 repeat-run idempotency guard: no existing proposal -> targets the real Generate CAPA button without the tour calling generateCapa itself; existing PENDING_APPROVAL -> jumps straight to Approve with a seed-and-continue note; existing terminal proposal -> skips straight to Audit Integrity with a skip-forward note, never re-attempting an already-terminal action"
    requirement: UI-04
    verification:
      - kind: unit
        ref: "frontend/src/__tests__/GuidedTourOverlay.test.tsx#D-09 idempotency guard (pure decision function) (3 branch tests)"
        status: pass
      - kind: unit
        ref: "frontend/src/__tests__/GuidedTourOverlay.test.tsx#D-09 idempotency guard (component-level, Step 6 branches) (4 tests)"
        status: pass
      - kind: integration
        ref: "frontend/src/__tests__/GuidedTourOverlay.test.tsx#D-09 full integration: a real Generate CAPA click drives the tour to Approve"
        status: pass
    human_judgment: false
  - id: D3
    description: "Target-not-found handling: if a step's target selector is not yet on the page, the tour shows a persistent note rather than crashing or silently skipping"
    requirement: UI-04
    verification:
      - kind: unit
        ref: "frontend/src/__tests__/GuidedTourOverlay.test.tsx#shows a persistent note rather than crashing or silently skipping when a target is not found"
        status: pass
    human_judgment: false
  - id: D4
    description: "react-joyride themed to the existing slate/emerald palette (no new hue introduced), with a scoped npm exception (verified legitimate on the registry) rather than a hand-rolled spotlight/positioning engine"
    requirement: UI-04
    verification:
      - kind: other
        ref: "npm view react-joyride version/peerDependencies (3.2.0, React 16.8-19) -- verified this session; frontend/package.json"
        status: pass
    human_judgment: false
  - id: D5
    description: "Manual live walkthrough against a running backend + seeded Postgres (start tour, complete all 8 steps, restart, confirm no duplicate action_proposals row)"
    verification: []
    human_judgment: true
    rationale: "This plan's automated environment has no running docker-compose services (Postgres/OPA) or live backend/frontend dev servers to drive an end-to-end manual walkthrough against. D2's automated integration test exercises the identical guard logic and click/poll wiring against mocked network boundaries and is the practical substitute available in this environment; the literal live-service walkthrough requires a human with the stack running."

duration: ~50min
completed: 2026-08-28
status: complete
---

# Phase 6 Plan 03: Guided Tour Summary

**8-step interactive react-joyride Guided Tour (Bible Section 14.4) driving real Command Centre / Copilot / Blast Radius / Actions surfaces end to end, with a D-09 idempotency guard (pure `resolveRemediationDecision()`) that polls `GET /api/actions` to make repeat tour runs safe -- never a second `generateCapa()` call, never a WS listener.**

## Performance

- **Duration:** ~50 min
- **Tasks:** 2 completed
- **Files modified:** 10 (3 created, 7 modified)

## Accomplishments

- Installed `react-joyride@3.2.0` (package-legitimacy verdict OK, re-verified this session: 1,380,658 weekly downloads, `github.com/gilbarbara/react-joyride`, confirmed React 19 peer support) as a scoped exception to the project's zero-component-library precedent, per 06-UI-SPEC.md's explicit resolution.
- `frontend/src/lib/tourSteps.ts`: the 8-entry `TOUR_STEPS` table matching 06-UI-SPEC.md's 8-step-to-7-real-surface-plus-closing mapping, with `HERO_SYSTEM_ID`/`HERO_QUERY_TEXT`/`JAILBREAK_QUERY_TEXT` constants.
- `frontend/src/components/GuidedTourOverlay.tsx`: a controlled `<Joyride>` themed to the existing slate/emerald palette, a custom `TourTooltip` rendering the persistent "Step N of 8" counter, Start Guided Tour / Explore Freely entry-exit UI, target-not-found handling, and the D-09 guard (`resolveRemediationDecision`) gating Step 6 (Controlled Remediation) against a real `GET /api/actions` re-fetch.
- Added `data-tour` selector attributes (additive only) to `CommandCentre.tsx`, `Copilot.tsx`, `FindingInvestigation.tsx`, and `ActionProposalCard.tsx` -- none of the four pages changed functionally.
- 13 tests in `GuidedTourOverlay.test.tsx`: entry/skip/target-not-found/closing-step behavior, the pure D-09 decision function's 3 branches, 4 component-level D-09 branch tests, and one full end-to-end integration test (`GuidedTourOverlay` + real `FindingInvestigation` + real `Actions`) proving a real "Generate CAPA" click drives the tour into the Approve phase via polling, with `generateCapa` called exactly once and `approveAction` never auto-invoked.

## Task Commits

Each task was committed atomically:

1. **Task 1: Guided Tour engine -- react-joyride, step table, entry/closing UI (D-08 skeleton)** - `2fb0ae1` (feat)
2. **Task 2: Wire real targets + D-09 repeat-run safety** - `5975fd1` (feat)

**Prerequisite:** merge commit bringing in 06-01/06-02 (this worktree branch was forked before those plans landed on `main` -- see Deviations)

**Plan metadata:** (this commit)

## Files Created/Modified

- `frontend/src/lib/tourSteps.ts` - new; 8-step tour table + hero/jailbreak query constants
- `frontend/src/components/GuidedTourOverlay.tsx` - new; the tour engine, D-09 guard, `resolveRemediationDecision`
- `frontend/src/__tests__/GuidedTourOverlay.test.tsx` - new; 13 tests
- `frontend/package.json` / `package-lock.json` - `react-joyride@3.2.0` dependency
- `frontend/src/App.tsx` - mounts `<GuidedTourOverlay />` in `AppShell`, after `RoleSelector`, before `main`
- `frontend/src/pages/CommandCentre.tsx` - `data-tour="readiness-dial"`, `data-tour="mini-card-audit-integrity"`
- `frontend/src/pages/Copilot.tsx` - `data-tour="copilot-input"`, `data-tour="copilot-messages"`
- `frontend/src/pages/FindingInvestigation.tsx` - `data-tour="blast-radius-link"`, `data-tour="generate-capa-button"`
- `frontend/src/components/ActionProposalCard.tsx` - `data-tour="approve-action"`

## Decisions Made

- react-joyride 3.2.0's real API (`onEvent`, top-level `options` prop, no `styles.options.spotlightShadow`) differs from the plan's v2-shaped `<action>` text -- implemented against the real, installed v3 API and approximated `spotlightShadow` via `styles.spotlight`'s CSS `filter: drop-shadow(...)` using the same emerald color, since v3's `Options` type has no such field.
- Resolved a plan self-contradiction on Step 6: `<behavior>` (more detailed) says the tour "click-guides" the real Generate CAPA button and reacts to "the real click's ... response resolving"; `<acceptance_criteria>` (less detailed) says "the tour's step-6 flow calls generateCapa exactly once." Implemented per `<behavior>` -- the tour polls `GET /api/actions` rather than calling `generateCapa()` itself -- and satisfied the acceptance criterion's underlying intent with a full integration test proving `generateCapa` is called exactly once, by the real page, in response to a real click.
- Step 8 (closing message) is a real Joyride step (`target: 'body'`, `placement: 'center'`) rather than a custom non-Joyride overlay, so `STATUS.FINISHED` fires naturally from Joyride's own last-step transition. Its primary button doubles as "Restart Tour" (immediate restart) and Skip doubles as "Explore Freely" (ends the tour), satisfying 06-UI-SPEC.md's dual-offer closing copy without new buttons.
- This worktree was 18 commits behind `main` (forked before 06-01/06-02 landed) -- merged `main` in first (clean, since merge-base was a direct ancestor) to get the Copilot/Command Centre surfaces this plan's tour targets.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking issue] Worktree was 18 commits behind main, missing this plan's declared dependencies (06-01, 06-02)**
- **Found during:** Setup, before Task 1
- **Issue:** This worktree's branch (`worktree-agent-a6acd92b04ff164d3`) was created from a commit predating both 06-01 and 06-02 landing on `main`. `Copilot.tsx`, `CommandCentre.tsx`, `AgentTopologyCanvas.tsx`, `ActionProposalCard.tsx`, and `lib/api.ts` were all still in their pre-06-01/06-02 state -- none of this plan's `data-tour` target surfaces existed yet, and `frontend/node_modules` was not installed at all.
- **Fix:** `git merge main` (clean fast-forward-style merge; `main` was 18 commits ahead with the merge-base as a direct ancestor, no conflicts), then `npm ci` in `frontend/`.
- **Files modified:** all of 06-01/06-02's files, brought in unmodified via the merge; no new authorship.
- **Commit:** merge commit (message: "chore(06-03): merge main to pull in 06-01/06-02 (dependencies for this plan)")

**2. [Rule 1 - Bug] Plan's react-joyride API usage (v2-shaped) does not match the installed v3.2.0 package**
- **Found during:** Task 1, initial implementation + `tsc -b`
- **Issue:** The plan's `<action>` text specifies a `callback` prop and `styles={{ options: { arrowColor, ..., spotlightShadow } }}` -- react-joyride 3.2.0's actual exported API (verified via its shipped `.d.cts`) uses `onEvent` (not `callback`), a top-level `options` prop (not nested under `styles`), and has no `spotlightShadow` field at all in its `Options` type (a v2-only key).
- **Fix:** Implemented against the real v3 API: `options={{ arrowColor, backgroundColor, overlayColor, primaryColor, textColor }}` (verbatim UI-SPEC hex values) plus `styles={{ spotlight: { style: { filter: 'drop-shadow(...)' } } }}` as the closest available approximation of the requested glow effect.
- **Files modified:** `frontend/src/components/GuidedTourOverlay.tsx`
- **Verification:** `npx tsc -b` clean; `GuidedTourOverlay.test.tsx` 13/13 passing.
- **Committed in:** `2fb0ae1` (Task 1 commit)

**3. [Plan defect, resolved per <important_note>] Acceptance-criteria/behavior contradiction on Step 6's generateCapa call**
- **Found during:** Task 2, designing the D-09 guard
- **Issue:** `<acceptance_criteria>` says "the tour's step-6 flow calls generateCapa exactly once" for the no-existing-proposal case; the more detailed `<behavior>` paragraph says the tour "proceeds to click-guide the real 'Generate CAPA' button" and reacts "on the real click's generateCapa response resolving" -- i.e. the tour itself never calls it.
- **Fix:** Implemented per `<behavior>` (higher detail, and consistent with D-08's "no synthetic DOM events" discipline established for the chat-input steps): the tour polls `GET /api/actions` to detect the real click's effect rather than calling `generateCapa()` itself. Verified the acceptance criterion's underlying intent (exactly one `generateCapa` call, end to end) with a full integration test.
- **Files modified:** `frontend/src/components/GuidedTourOverlay.tsx`, `frontend/src/__tests__/GuidedTourOverlay.test.tsx`
- **Verification:** Integration test asserts `mockGenerateCapa` called exactly once and `mockApproveAction` never auto-called.
- **Committed in:** `5975fd1` (Task 2 commit)

---

**Total deviations:** 3 auto-fixed (1 Rule 3, 1 Rule 1, 1 plan defect)
**Impact on plan:** All three were necessary preconditions/corrections to execute the plan's actual intent; no scope creep.

## TDD Gate Compliance

Task 2 carried `tdd="true"` but its `<action>` is a single combined block (data-tour wiring + D-09 guard + retry handling) without a separate `<implementation>` tag, so it does not map cleanly onto the standard RED-test-commit / GREEN-implementation-commit two-commit pattern. The test file (`GuidedTourOverlay.test.tsx`) and the implementation (`GuidedTourOverlay.tsx` + the four `data-tour` annotations) were written together and committed in a single `feat(06-03)` commit (`5975fd1`) after both were verified passing together (13/13 tests, `tsc -b` clean). No separate `test(...)` RED commit exists for this task. The behavior itself was still verified end-to-end (unit + integration), including the two explicitly required backstop truths (target-not-found handling, repeat-run duplicate-proposal prevention) with real, executed tests rather than code inspection alone.

## Issues Encountered

- The shared SSE test helper (`frontend/src/__tests__/helpers/sseFetch.ts`)'s `streamingResponse` mock is single-use per call to `stubAssuranceCardsFetch` (a shared reader object with internal cursor state, not re-entrant across repeated `fetch` calls). The full integration test drives `FindingInvestigation.tsx` through two separate mounts (Step 4 "Blast Radius" and Step 6 "Controlled Remediation" both route to `/findings`), so the mock needed re-installing with a fresh reader between the two mounts. Resolved within the test itself (no helper file change) by calling `stubAssuranceCardsFetch` a second time immediately before the second mount.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- The Guided Tour is mounted globally in `AppShell` and available on every route; Phase 6's stated success criterion ("the full Monitor -> Investigate -> Trust -> Remediate -> Audit loop is walkable without a developer narrating gaps") now has an interactive, real-backend-driven walkthrough backing it.
- `resolveRemediationDecision()` is exported and independently testable -- any future demo-automation feature needing a similar repeat-run idempotency guard can reuse the same pure-function pattern.
- The literal manual walkthrough against a live `docker-compose` backend + seeded Postgres (this plan's own `<verification>` section) was not run in this environment (no live services available to this executor) -- flagged as `human_judgment: true` (D5) for a human to perform before final sign-off; the automated integration test (D2) is the closest available substitute and exercises identical logic.

## Self-Check: PASSED

- FOUND: frontend/src/lib/tourSteps.ts
- FOUND: frontend/src/components/GuidedTourOverlay.tsx
- FOUND: frontend/src/__tests__/GuidedTourOverlay.test.tsx
- FOUND: frontend/src/pages/CommandCentre.tsx (data-tour attributes present)
- FOUND: frontend/src/pages/Copilot.tsx (data-tour attributes present)
- FOUND: frontend/src/pages/FindingInvestigation.tsx (data-tour attributes present)
- FOUND: frontend/src/components/ActionProposalCard.tsx (data-tour attribute present)
- FOUND commit 2fb0ae1
- FOUND commit 5975fd1
- Full suites green: frontend `npx vitest run` (142/142 passed), backend `python -m pytest` (379/379 passed)

---
*Phase: 06-product-experience*
*Completed: 2026-08-28*
