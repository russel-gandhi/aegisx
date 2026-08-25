---
phase: 05-safety-remediation
plan: 05
subsystem: safety-remediation
tags: [websocket, react, fastapi, rbac, action-approval, capa, testing-library, vitest]

# Dependency graph
requires:
  - phase: 05-safety-remediation
    provides: "05-01: identity.py, c2_gateway.py, c3_gateway.py, a7_remediation.py, audit_trail.py, routes/actions.py (generate-capa/GET/approve); 05-04: routes/actions.py reject route, ActionProposalRecord's full field set"
provides:
  - "ws/copilot.py: _active_connections, broadcast_json, active_connection_count -- the copilot stream now pushes action_proposal_created to every connected client"
  - "routes/actions.py: generate_capa broadcasts the created proposal after persist + audit-log, best-effort (logged and swallowed on failure)"
  - "lib/identity.ts: DEMO_IDENTITIES, getIdentity/setIdentity/subscribeIdentity/useIdentity/identityHeaders -- fixed demo identity, localStorage-persisted, server re-derives independently"
  - "lib/api.ts: ApiError, apiPost, ActionProposalData/ActionProposalsResponse/GenerateCapaResponse, fetchActionProposals/generateCapa/approveAction/rejectAction"
  - "components/RoleSelector.tsx, components/ActionProposalCard.tsx -- persistent role chrome and props-only proposal card"
  - "pages/Actions.tsx: the live, working Action / Approval Centre (was a stub)"
affects: [05-06]

actuals:
  tokens: 18107
  tasks: 3
  commits: 6

tech-stack:
  added: []
  patterns:
    - "In-process WebSocket broadcast registry (module-level Set[WebSocket], snapshot-iterate, per-socket try/except, dead-set prune, delivery-count return) -- single-worker scale per 05-RESEARCH.md Pattern 4, no Redis pub/sub"
    - "Client-side identity as a useSyncExternalStore singleton (lib/identity.ts) -- convenience only, server independently re-derives/re-checks on every write-capable route"
    - "ApiError(status, detail, message) distinguishes RBAC-403 copy from generic-failure copy at every call site, replacing the previous bare Error"
    - "Props-only presentation component (ActionProposalCard) mirroring AssuranceCard's no-fetch/no-arithmetic/no-client-fallback discipline, extended with owned busy/error props so the page (not the card) owns async state"

key-files:
  created:
    - backend/tests/test_ws_broadcast.py
    - frontend/src/lib/identity.ts
    - frontend/src/components/RoleSelector.tsx
    - frontend/src/components/ActionProposalCard.tsx
    - frontend/src/__tests__/RoleSelector.test.tsx
    - frontend/src/__tests__/Actions.test.tsx
    - .planning/phases/05-safety-remediation/deferred-items.md
  modified:
    - backend/app/ws/copilot.py
    - backend/app/routes/actions.py
    - frontend/src/lib/api.ts
    - frontend/src/lib/ws.ts
    - frontend/src/App.tsx
    - frontend/src/pages/FindingInvestigation.tsx
    - frontend/src/pages/Actions.tsx
    - frontend/src/pages/Copilot.tsx

key-decisions:
  - "Worktree fast-forwarded to main (5cbff8c) before any edit: this worktree forked from f27e9bd, an ancestor of main predating 05-01 through 05-04's merges. Verified merge-base --is-ancestor HEAD main (clean fast-forward, no divergence) before running git merge --ff-only main -- same recovery pattern 05-04's own SUMMARY documented and explicitly flagged for the orchestrator's pre-dispatch base-check."
  - "pages/Copilot.tsx received a minimal, unplanned fix (Rule 3): extending lib/ws.ts's CopilotStreamFrame union to three variants broke Copilot.tsx's exhaustive ternary (frame.payload does not exist on the new ActionProposalCreatedFrame branch). Narrowed to three independent conditionals: rendered output is byte-identical for the two pre-existing frame types, and the new frame type is a documented no-op on this page (the Approval Centre is where it is consumed)."
  - "ActionProposalCard.category rendered defensively as (proposal.category ?? 'Not provided') even though backend/app/schemas.py's ActionProposalRecord.category is non-optional str (route_action always derives a value) -- 05-UI-SPEC.md's UI Considerations table explicitly lists a null-category backstop test, so the fallback exists for robustness against a future schema change, verified by test with a type-asserted null fixture."
  - "STATUS_STYLES/STATUS_BADGE_STYLES exported (unlike AssuranceCard's private CONFIDENCE_STYLES/CONFIDENCE_BADGE_STYLES) per this plan's own <artifacts> symbol list -- accepted the resulting oxlint react(only-export-components) warning (not an error) as the necessary cost of the plan's explicit interface contract."

patterns-established:
  - "Pattern: a write-capable POST route broadcasts its result over the existing WS registry only after the row is durably persisted and audit-logged, wrapped so a broadcast failure is logged and swallowed -- a dead socket never rolls back a completed write (routes/actions.py's _broadcast_new_proposal)."
  - "Pattern: page owns async decision state per-entity (Record<id, {busy, error}>), presentation component stays props-only and stateless except for its own local reject-confirmation toggle -- mirrors this codebase's existing page/component split (FindingInvestigation/AssuranceCard) extended to a two-action (approve/reject) surface."

requirements-completed: [REM-03, REM-04, UI-02, SAFE-01]

coverage:
  - id: D1
    description: "A created proposal reaches every open copilot-stream client as an action_proposal_created frame; a dead client is pruned without blocking delivery to the rest; a disconnect deregisters the socket; the Phase 2 echo contract is unchanged; exactly one WebSocket route remains registered"
    requirement: REM-04
    verification:
      - kind: integration
        ref: "backend/tests/test_ws_broadcast.py (5 tests: reaches every socket, prunes dead connections, disconnect deregisters, generate-capa pushes a real frame, echo contract unchanged)"
        status: pass
      - kind: unit
        ref: "backend/tests/test_ws_echo.py (6 tests, unchanged, all still pass)"
        status: pass
    human_judgment: false
  - id: D2
    description: "A persistent role selector supplies X-User-Id/X-User-Role on every frontend write; an unrecognised persisted role falls back to the default identity; apiPost attaches both headers; ApiError carries the parsed 403 detail"
    requirement: SAFE-01
    verification:
      - kind: unit
        ref: "frontend/src/__tests__/RoleSelector.test.tsx (8 tests: three Bible role labels, click updates getIdentity, aria-pressed, identityHeaders, localStorage fallback, apiPost headers, ApiError.status/detail)"
        status: pass
    human_judgment: false
  - id: D3
    description: "Generate CAPA works from a verified finding with the UI contract's exact loading (\"Generating...\") and error copy, including the RBAC-403 permission sentence verbatim"
    requirement: REM-03
    verification:
      - kind: automated_ui
        ref: "frontend/src/__tests__/RoleSelector.test.tsx::FindingInvestigation Generate CAPA RBAC denial (renders the UI contract permission sentence verbatim on a stubbed 403 from generateCapa)"
        status: pass
    human_judgment: false
  - id: D4
    description: "The Action / Approval Centre lists pending proposals oldest-first, updates live from the copilot stream without duplicate-rendering a repeated frame, renders every field from the server response with 'Not provided' for null justification/category, and a large payload scrolls inside a fixed-max-height <pre>"
    requirement: UI-02
    verification:
      - kind: automated_ui
        ref: "frontend/src/__tests__/Actions.test.tsx (loading/error/empty copy, Pending Actions (N) for 0/1/3, oldest-first ordering, Not provided x2, large-payload <pre> overflow class, live frame append + duplicate dedupe, socket-close degraded copy)"
        status: pass
    human_judgment: false
  - id: D5
    description: "Approve and Reject disable while in flight (label changes to Approving.../Rejecting...), never optimistically flip status before the server confirms, and surface distinct copy on 403 (permission sentence, status stays PENDING_APPROVAL) vs 5xx (generic decision-failure copy); Reject shows the destructive confirmation with the proposal's own action_type/target_system interpolated before firing"
    requirement: REM-03
    verification:
      - kind: automated_ui
        ref: "frontend/src/__tests__/Actions.test.tsx (Approve in-flight disables both buttons, 403 leaves PENDING_APPROVAL, 500 generic copy, Reject confirmation interpolation, server-record replacement after successful approve -- no optimistic flip)"
        status: pass
    human_judgment: false

duration: 62min
completed: 2026-08-25
status: complete
---

# Phase 5 Plan 5: WebSocket Proposal Push + Live Action/Approval Centre Summary

**A generated CAPA proposal now streams live to the browser over the existing `/api/copilot/stream/{session_id}` socket, a persistent role selector carries `X-User-Id`/`X-User-Role` on every write, and the previously-stub Action / Approval Centre lists, approves, and rejects proposals from server-trusted data with the UI contract's exact copy.**

## Performance

- **Duration:** ~62 min
- **Started:** 2026-08-25 (after fast-forwarding this worktree to `main`, see Deviations)
- **Completed:** 2026-08-25
- **Tasks:** 3 of 3 completed
- **Files modified:** 14 (7 created, 8 modified -- one, `frontend/src/pages/Copilot.tsx`, is an unplanned Rule 3 fix; `.planning/phases/05-safety-remediation/deferred-items.md` created separately, not counted in the 14)

## Accomplishments

- `backend/app/ws/copilot.py` gained an in-process broadcast registry (`_active_connections`, `broadcast_json`, `active_connection_count`), extending the existing echo route in place -- no second `@router.websocket` route was added. `broadcast_json` iterates a snapshot, catches per-socket send failures, prunes the dead set, and returns a delivery count, so one stale client never blocks delivery to the rest.
- `backend/app/routes/actions.py`'s `generate_capa` now calls `broadcast_json({"event": "action_proposal_created", "proposal": ...})` after `persist_proposal` and the `PROPOSAL_CREATED` audit log both succeed, wrapped so a broadcast failure is logged and swallowed -- the proposal is already a durable, audit-logged fact by that point.
- `frontend/src/lib/identity.ts` implements D-01's fixed demo identity: three Bible-spelled roles (`IT System Manager`, `QA/Compliance`, `Auditor`), `localStorage`-persisted with an unrecognised-role fallback to the default, and a `useSyncExternalStore`-based `useIdentity()` hook so every consumer re-renders on a role change.
- `frontend/src/lib/api.ts` gained `ApiError` (status + parsed `detail`), `apiPost<T>`, and the full `ActionProposalData`/`ActionProposalsResponse`/`GenerateCapaResponse` contract mirroring `backend/app/schemas.py` field for field.
- `frontend/src/components/RoleSelector.tsx` is mounted in `App.tsx`'s `AppShell` immediately after `NavBar`, matching its exact pill classes, so a role is selected before the operator ever reaches `/findings` or `/actions`.
- `frontend/src/pages/FindingInvestigation.tsx` gained a per-finding "Generate CAPA" button with `Generating...` in-flight state, a success link to `/actions` naming the new proposal id, the UI contract's exact 403 permission sentence, and a generic `Couldn't generate CAPA — {reason}.` for any other failure.
- `frontend/src/components/ActionProposalCard.tsx` is a props-only presentation component (REM-03): every field reads from the `proposal` prop, `justification`/`category` fall back to the literal `Not provided`, `payload` renders inside a `max-h-48 overflow-auto` `<pre>`, and Approve/Reject render only for `PENDING_APPROVAL` with the contract's destructive Reject confirmation.
- `frontend/src/pages/Actions.tsx` (previously a static stub) now fetches the queue with a cancelled-guard effect, sorts oldest-first by `created_at` (falling back to `id`), opens the copilot stream once on mount and merges `action_proposal_created` frames into the queue by id (deduping a repeat), and wires Approve/Reject to replace the proposal only with the server's returned record -- never an optimistic flip.
- Backend suite: 294 passed, 13 pre-existing failures unrelated to this plan's scope (OPA-corroboration path; see Deviations and `deferred-items.md`), unchanged before and after this plan's edits. Frontend suite: 87 passed, `npm run build` and `npx oxlint` both clean (oxlint warnings only, no errors).

## Task Commits

1. **Task 1: Push pending proposals over the existing copilot WebSocket** - `6e6e489` (feat)
2. **Task 2: Identity chrome, the write-capable API client, and the Generate CAPA trigger** - `313b167` (feat)
3. **Task 3: The live Action / Approval Centre** - `7d5ea31` (feat)

**Plan metadata:** (this commit) - `docs(05-05): complete WebSocket proposal push + live Action/Approval Centre plan`

## Files Created/Modified

- `backend/app/ws/copilot.py` - `_active_connections`, `broadcast_json`, `active_connection_count`; extends the existing echo route in place
- `backend/app/routes/actions.py` - `_broadcast_new_proposal` called from `generate_capa` after persist + audit-log
- `backend/tests/test_ws_broadcast.py` - 5 tests covering broadcast/prune/disconnect/real-frame/echo-unchanged
- `frontend/src/lib/identity.ts` - `DEMO_IDENTITIES`, `getIdentity`/`setIdentity`/`subscribeIdentity`/`useIdentity`/`identityHeaders`
- `frontend/src/lib/api.ts` - `ApiError`, `apiPost`, `ActionProposalData`/`ActionProposalsResponse`/`GenerateCapaResponse`, `fetchActionProposals`/`generateCapa`/`approveAction`/`rejectAction`
- `frontend/src/components/RoleSelector.tsx` - three-button role picker matching `NavBar`'s pill classes
- `frontend/src/App.tsx` - mounts `<RoleSelector />` after `<NavBar />`, outside `<main>`
- `frontend/src/pages/FindingInvestigation.tsx` - per-card Generate CAPA button, in-flight/success/error states
- `frontend/src/__tests__/RoleSelector.test.tsx` - 8 tests (identity module, RoleSelector component, apiPost/ApiError, FindingInvestigation 403 render)
- `frontend/src/lib/ws.ts` - `ActionProposalCreatedFrame` added to `CopilotStreamFrame`
- `frontend/src/components/ActionProposalCard.tsx` - props-only proposal card, `STATUS_STYLES`/`STATUS_BADGE_STYLES`
- `frontend/src/pages/Actions.tsx` - the live Action / Approval Centre (queue fetch, WS merge, Approve/Reject)
- `frontend/src/pages/Copilot.tsx` - minimal Rule 3 fix for the grown `CopilotStreamFrame` union
- `frontend/src/__tests__/Actions.test.tsx` - 15 tests covering states, ordering, live updates, and decisions
- `.planning/phases/05-safety-remediation/deferred-items.md` - logs 13 pre-existing, out-of-scope backend test failures

## Decisions Made

- **Worktree fast-forward recovery.** See Deviations.
- **`pages/Copilot.tsx` minimal fix.** See Deviations.
- **`ActionProposalCard.category` defensive `?? 'Not provided'`.** See key-decisions in frontmatter -- the backend schema never actually sends a null `category`, but 05-UI-SPEC.md's own UI Considerations table specifies this as a required backstop, so the component and its test cover it even though the current backend contract can't produce it.
- **`STATUS_STYLES`/`STATUS_BADGE_STYLES` exported, unlike `AssuranceCard`'s private equivalents.** This plan's `<artifacts>` section explicitly lists them as required new symbols; the resulting `oxlint react(only-export-components)` warning (not an error) was accepted rather than working around the plan's own interface contract.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Worktree fast-forwarded to `main` before any edit**
- **Found during:** environment setup, before Task 1's precondition ("Postgres running with Phase 2 seed data") could be usefully checked
- **Issue:** This worktree's branch (`worktree-agent-a7014c62676bf3538`) forked from `f27e9bd`, an ancestor of `main` predating 05-01 through 05-04's merges -- `backend/tests/test_routes_actions.py` and the modules this plan's Task 1 depends on (`app.ws.copilot`'s existing shape, `app.routes.actions`'s `generate_capa`/`approve_action`/`reject_action`) did not exist on this branch yet.
- **Fix:** Verified `git merge-base --is-ancestor HEAD main` (clean fast-forward possible, no divergence, working tree clean) before running `git merge --ff-only main`. This adds commits only; nothing was discarded. Matches the exact recovery pattern 05-04's own SUMMARY documented for the identical situation and explicitly flagged for the orchestrator's pre-dispatch base-check (#2649) to catch earlier in a future run.
- **Files modified:** none directly (a pure git fast-forward; brought in 25 files from 05-01 through 05-04's already-merged commits)
- **Verification:** `backend/tests/test_routes_actions.py` (18 tests) and the full backend suite passed immediately after the fast-forward, before any of this plan's own edits.
- **Committed in:** N/A (fast-forward merge, not a new commit on this branch)

**2. [Rule 3 - Blocking] `frontend/src/pages/Copilot.tsx` fixed for the grown `CopilotStreamFrame` union**
- **Found during:** Task 3, `npm run build` after extending `lib/ws.ts`'s `CopilotStreamFrame` to three variants
- **Issue:** `Copilot.tsx`'s existing frame-rendering ternary (`frame.event === 'connected' ? ... : frame.payload`) assumed exactly two frame shapes; adding `ActionProposalCreatedFrame` broke TypeScript's narrowing (`Property 'payload' does not exist on type 'ActionProposalCreatedFrame'`), a direct, unavoidable consequence of extending a type this plan is explicitly instructed to extend.
- **Fix:** Narrowed to three independent per-variant conditionals. Rendered output is byte-identical to before for the two pre-existing frame types (`connected`/`echo`); the new `action_proposal_created` case renders `proposal created: {id}` as a documented no-op -- this page does not yet consume that frame shape, the live Approval Centre (`pages/Actions.tsx`) is where it is meaningfully handled.
- **Files modified:** `frontend/src/pages/Copilot.tsx`
- **Verification:** `npm run build` exits 0; no `Copilot.tsx` test exists in this repo to regress, and full frontend suite (87 tests) still passes.
- **Committed in:** `7d5ea31` (part of Task 3's commit)

**3. [Rule 1 - Bug] `updateDecision`'s object-spread pattern rewritten to satisfy a real TypeScript error**
- **Found during:** Task 3, `npm run build`
- **Issue:** `{ busy: null, error: null, ...prev[id], ...patch }` triggered `TS2783: 'busy'/'error' is specified more than once, so this usage will be overwritten` -- `Record<string, DecisionState>` indexing yields a non-optional `DecisionState`, so the literal defaults preceding the spread were statically dead code, not just stylistically redundant.
- **Fix:** Replaced with `const existing: DecisionState = prev[id] ?? { busy: null, error: null }; return { ...prev, [id]: { ...existing, ...patch } }` -- same runtime behavior, no redundant literal keys.
- **Files modified:** `frontend/src/pages/Actions.tsx`
- **Verification:** `npm run build` exits 0; `Actions.test.tsx`'s Approve/Reject in-flight and error-copy tests still pass.
- **Committed in:** `7d5ea31` (part of Task 3's commit)

**4. [Rule 1 - Bug] Removed a synchronous `setLoadState('loading')` call inside the queue-fetch effect**
- **Found during:** Task 3, `npx oxlint` (`react(set-state-in-effect)` warning)
- **Issue:** Calling `setState` synchronously at the top of an effect body (before any awaited work) starts an avoidable second render on every commit of that effect, including the identity-change re-run this plan requires -- a real anti-pattern the linter caught, not a false positive.
- **Fix:** Removed the redundant call (the initial `loadState` value is already `'loading'`); the Retry button's own `onClick` handler now sets `loadState` to `'loading'` before incrementing `retryToken`, since an event handler (not an effect body) is the correct place for that synchronous update.
- **Files modified:** `frontend/src/pages/Actions.tsx`
- **Verification:** `npx oxlint` no longer reports the warning; `Actions.test.tsx`'s loading/error-state tests still pass.
- **Committed in:** `7d5ea31` (part of Task 3's commit)

---

**Total deviations:** 4 (1 blocking-issue worktree recovery, 1 blocking-issue type-narrowing fix in an out-of-plan-scope file, 2 bug fixes surfaced by the build/lint gate itself). **Impact:** All four were necessary preconditions for this plan's own verification to run or pass at all. Deviation 2 is the only one touching a file outside this plan's declared `<files>` list, and it is a minimal, behavior-preserving fix directly and unavoidably caused by this plan's own required change to a shared type (`lib/ws.ts`'s `CopilotStreamFrame` union) -- not scope creep.

## Issues Encountered

- **13 pre-existing backend test failures, confirmed unrelated to this plan's scope.** All in `test_c1_verifier.py`, `test_hero_loop.py`, `test_hero_tracer.py`, `test_opa_client.py`, and `test_routes_findings.py` -- none in `test_ws_broadcast.py`, `test_ws_echo.py`, or `test_routes_actions.py` (this plan's own scope). Confirmed present immediately after the worktree fast-forward (before any 05-05 edit) and unchanged after all three tasks (same 13 failing, same 294 passing both times). Spot-checked one: `evaluate_opa_policy()` against the live OPA sidecar returns zero violations where a test expects one, pointing at OPA policy-bundle/container drift, not application code. Logged in `.planning/phases/05-safety-remediation/deferred-items.md` for a future OPA-owning plan or `/gsd-secure-phase 05` to investigate; not fixed here (out of this plan's declared `<files>`, per the executor's scope-boundary rule).

## User Setup Required

None - no external service configuration required. (Postgres, OPA, and Qdrant were already running via `docker compose` from a prior session; no new environment variable or service was introduced.)

## Next Phase Readiness

- The approval loop is now fully browser-operable end to end: Generate CAPA -> live WS push -> Approval Centre -> Approve/Reject, with server-trusted rendering throughout (REM-03) and no LLM-authored UI at any point.
- `frontend/src/lib/identity.ts` and `frontend/src/lib/api.ts`'s `ApiError`/`apiPost` are now the established convention any future write-capable frontend surface (e.g. 05-06's graph-node wiring, if it needs a write path) should reuse rather than reinvent.
- No blockers for 05-06.

## Self-Check: PASSED

- `backend/app/ws/copilot.py` exists on disk and contains `broadcast_json`: **FOUND**
- `backend/app/routes/actions.py` calls `_broadcast_new_proposal`: **FOUND**
- `backend/tests/test_ws_broadcast.py` exists on disk: **FOUND**
- `frontend/src/lib/identity.ts` exists on disk: **FOUND**
- `frontend/src/components/RoleSelector.tsx` exists on disk: **FOUND**
- `frontend/src/components/ActionProposalCard.tsx` exists on disk: **FOUND**
- `frontend/src/__tests__/RoleSelector.test.tsx` exists on disk: **FOUND**
- `frontend/src/__tests__/Actions.test.tsx` exists on disk: **FOUND**
- Commit `6e6e489` exists in `git log`: **FOUND**
- Commit `313b167` exists in `git log`: **FOUND**
- Commit `7d5ea31` exists in `git log`: **FOUND**
- Plan `<verification>` block re-run: (1) `cd backend && python -m pytest` -- 294 passed, 13 pre-existing unrelated failures (see Issues Encountered) -- **PASS** (no regression); (2) `cd frontend && npm test` -- 87 passed -- **PASS**; (3) `cd frontend && npm run build` exits 0, `npx oxlint` reports no new errors (2 plan-mandated warnings only) -- **PASS**; (4) exactly one WebSocket route registered -- **PASS** (confirmed via `app.routes[i].original_router.routes`, the FastAPI 0.141.1 `_IncludedRouter`-flattening quirk 05-04 already documented -- the plan's own literal `app.routes` acceptance command undercounts to 0 for the same reason 05-04 found; the route itself is real and singular)
- Plan `<must_haves><truths>` re-checked: broadcast reaches every client + dead-client pruning -- **PASS**; role selector supplies both headers on every write -- **PASS**; Generate CAPA success + 403 permission copy -- **PASS**; Approval Centre oldest-first + live updates + no client-invented fallback -- **PASS**; Approve/Reject disable-while-busy + no optimistic flip + distinct 403/5xx copy -- **PASS**

---
*Phase: 05-safety-remediation*
*Completed: 2026-08-25*
