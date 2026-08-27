---
phase: 06-product-experience
plan: 01
subsystem: ui
tags: [react, fastapi, sse, react-flow, tailwind, copilot, injection-detection]

requires:
  - phase: 04-evidence-impact
    provides: "GET /api/systems/{id}/assurance-cards/stream (SSE, EVID-03) -- reused unmodified"
  - phase: 05-safety-remediation
    provides: "detect_injection() (app.agents.c2_gateway, zero-LLM, Critical-reviewed) -- reused unmodified"
provides:
  - "Real Ask GxP Copilot chat page (frontend/src/pages/Copilot.tsx) replacing the bare WS echo-test stub"
  - "AgentTopologyCanvas nodeStatus prop -- live node coloring driven off real SSE event arrival, plus permanent v1-scope dimming"
  - "POST /api/copilot/query -- detect_injection()'s first real HTTP caller"
affects: [06-02-command-centre, 06-03-guided-tour]

actuals:
  tokens: 13045
  tasks: 2
  commits: 4

tech-stack:
  added: []
  patterns:
    - "Chat-page-over-existing-SSE-stream: hero query routes to an unmodified Phase 4 SSE endpoint rather than the compiled LangGraph, keeping the client-synthesized topology animation decoupled from backend agent count"
    - "Client-side node-status synthesis timed off real event arrival (never a fabricated delay) -- AgentTopologyCanvas.nodeStatus prop pattern"
    - "Permanent DIMMED_NODE_IDS set, independent of live status, for agents not exercised by a given query type in v1"

key-files:
  created:
    - frontend/src/components/ChatMessage.tsx
    - frontend/src/__tests__/Copilot.test.tsx
    - frontend/src/__tests__/AgentTopologyCanvas.test.tsx
    - backend/app/routes/copilot_query.py
    - backend/tests/test_routes_copilot_query.py
  modified:
    - frontend/src/pages/Copilot.tsx
    - frontend/src/components/AgentTopologyCanvas.tsx
    - frontend/src/lib/api.ts
    - frontend/src/__tests__/ws.test.ts
    - backend/app/schemas.py
    - backend/app/main.py

key-decisions:
  - "Kept the existing connectCopilotStream() WS connection alive on mount for a future action_proposal_created push only, per 06-CONTEXT.md code_context -- not repurposed for the hero-query response path"
  - "matchHeroQuery() lives in Copilot.tsx (not a shared lib) since it is Copilot-page-specific routing logic, exported for direct unit testing"
  - "Auto-scroll-to-bottom implemented via a ref + scrollTop=scrollHeight effect (06-UI-SPEC.md overflow row, must_haves backstop truth) even though its own held-out test was deferred by the UI-SPEC to a later pass"

patterns-established:
  - "queryCopilot()/POST /api/copilot/query: the template for any future 'give an already-tested deterministic function its first real HTTP caller' route -- no pool, no RBAC, matches routes/actions.py's documented ungated-read-route precedent"

requirements-completed: [UI-04]

coverage:
  - id: D1
    description: "Hero query end-to-end: user types a seeded readiness question, AssuranceCards stream into the chat in arrival order, AgentTopologyCanvas transitions A0/A2/C1 waiting->running->complete in sync with real SSE events"
    requirement: UI-04
    verification:
      - kind: unit
        ref: "frontend/src/__tests__/Copilot.test.tsx"
        status: pass
      - kind: unit
        ref: "frontend/src/__tests__/AgentTopologyCanvas.test.tsx"
        status: pass
    human_judgment: false
  - id: D2
    description: "Non-hero-query input (including a jailbreak phrase) gets a real, honest, non-fabricated response via POST /api/copilot/query wrapping the real detect_injection()"
    requirement: UI-04
    verification:
      - kind: unit
        ref: "backend/tests/test_routes_copilot_query.py"
        status: pass
      - kind: unit
        ref: "frontend/src/__tests__/Copilot.test.tsx (Task 2 describe block)"
        status: pass
    human_judgment: false
  - id: D3
    description: "A1/A3-A6/C2/A7/C3 stay permanently dimmed with the literal 'A1, A3-A6 not yet implemented (v2)' note, regardless of live nodeStatus"
    requirement: UI-04
    verification:
      - kind: unit
        ref: "frontend/src/__tests__/AgentTopologyCanvas.test.tsx"
        status: pass
    human_judgment: false

duration: 25min
completed: 2026-08-27
status: complete
---

# Phase 6 Plan 1: Ask GxP Copilot Chat + Live Topology Summary

**Rebuilt the Copilot page as a real chat that streams AssuranceCards from the existing Phase 4 SSE endpoint while a client-synthesized agent-topology animation tracks real event arrival, and gave `detect_injection()` its first real HTTP caller so every other input gets an honest, never-fabricated response.**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-08-27T19:04 IST
- **Completed:** 2026-08-27T19:21 IST
- **Tasks:** 2 completed
- **Files modified:** 11 (5 created, 6 modified)

## Accomplishments

- `frontend/src/pages/Copilot.tsx` rebuilt from a bare WS echo-test stub into a real chat: `matchHeroQuery()` routes the two seeded system-readiness questions to the unmodified `GET /api/systems/{id}/assurance-cards/stream` SSE endpoint (D-01), accumulating `AssuranceCard`s into the assistant's bubble one at a time as they arrive (D-05).
- `AgentTopologyCanvas` gained a `nodeStatus` prop and a permanent `DIMMED_NODE_IDS` set: A0/A2 go `running` on stream open, C1 goes `running` on the first card, all three go `complete` together on the terminal frame (single transition, not per-check) — colors are synthesized client-side but timed strictly off real SSE arrival, never a fabricated delay (D-02). The literal note "A1, A3–A6 not yet implemented (v2)" always renders (D-03).
- `POST /api/copilot/query` (new, `backend/app/routes/copilot_query.py`) gives the already Critical-reviewed, zero-LLM `detect_injection()` its first real HTTP caller. A blocked non-hero-query input renders the injection-detected copy with the real interpolated `reason`; a non-blocked input renders an honest "not supported yet" response; a transport failure degrades to the same honest response rather than a raw error (D-04).
- Added the message-list auto-scroll-to-bottom behavior called for by 06-UI-SPEC.md's overflow row.

## Task Commits

Each task was committed atomically:

1. **Task 1: Hero query end-to-end — real chat + live topology sync (D-01, D-02, D-03, D-05)** — `48d952e` (feat)
2. **Task 2: Non-hero-query path via real detect_injection() (D-04)** — `9c9e116` (feat)
3. **Follow-up: auto-scroll the Copilot message list** — `48a44eb` (fix, backstop truth from must_haves)

**Prerequisite:** `f9a8cc2` (docs: synced phase 6 planning docs into this worktree — see Deviations)

**Plan metadata:** (this commit)

## Files Created/Modified

- `frontend/src/pages/Copilot.tsx` - rebuilt as the real chat page (hero-query routing, streaming, topology wiring, non-hero-query routing, auto-scroll)
- `frontend/src/components/ChatMessage.tsx` - new; renders user/assistant bubbles including AssuranceCard accumulation and the "every check passes" empty state, with a decorative fade-in
- `frontend/src/components/AgentTopologyCanvas.tsx` - added `nodeStatus`/`disconnected` props, `DIMMED_NODE_IDS`, the v2 note, and the disconnected banner
- `frontend/src/lib/api.ts` - added `queryCopilot()`/`CopilotQueryResponse`
- `frontend/src/__tests__/Copilot.test.tsx` - new; full coverage of both tasks plus the auto-scroll behavior
- `frontend/src/__tests__/AgentTopologyCanvas.test.tsx` - new; node-status coloring, dimming, and disconnected-banner coverage
- `frontend/src/__tests__/ws.test.ts` - updated the Copilot-page describe block for the removed echo-test-stub UI
- `backend/app/routes/copilot_query.py` - new; `POST /api/copilot/query`
- `backend/app/schemas.py` - added `CopilotQueryRequest`/`CopilotQueryResponse`
- `backend/app/main.py` - registered the new router
- `backend/tests/test_routes_copilot_query.py` - new; UNIT/NEGATIVE/EDGE/INTEGRATION coverage against the real `detect_injection()`

## Decisions Made

- Kept `connectCopilotStream()` connected on mount but rendering nothing from it (per 06-CONTEXT.md code_context — reserved for a future `action_proposal_created` push, not the hero-query path).
- `matchHeroQuery()` and `injectionDetectedCopy()` live in `Copilot.tsx` itself (exported for direct unit test import) rather than a new shared lib file, since both are Copilot-page-specific.
- Implemented the auto-scroll-to-bottom behavior from 06-UI-SPEC.md's overflow row even though its own held-out scroll-position test was explicitly deferred by the UI-SPEC — the underlying behavior is a `must_haves` truth, only its formal verification was marked backstop.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking issue] Worktree branch was missing phase-6 planning docs and had no installed dependencies**
- **Found during:** Setup, before Task 1
- **Issue:** This worktree's branch (`worktree-agent-aad335f2a82a153fd`) was created from a commit (716a905) that predates the phase-6 planning docs (06-CONTEXT.md, 06-UI-SPEC.md, 06-RESEARCH.md, PLAN files) landing on `main` — the required-reading files this plan's `<execution_flow>` mandates reading did not exist in the worktree's working tree. Additionally, `frontend/node_modules` and `backend`'s Python environment were not present/importable from this worktree checkout, so no test could run at all.
- **Fix:** Brought the 06-product-experience planning docs in unmodified via `git checkout main -- .planning/phases/06-product-experience` (identical content already on `main`, not new authorship) and ran `npm ci` in `frontend/`. Backend dependencies were already importable via the system Python install.
- **Files modified:** `.planning/phases/06-product-experience/*.md` (8 files, content sourced from `main`, no changes)
- **Commit:** `f9a8cc2`

**2. [Rule 1 - Bug] `ws.test.ts`'s Copilot-page describe block tested removed behavior**
- **Found during:** Task 1, full-suite verification
- **Issue:** The plan's own Task 1 action explicitly required rewriting `Copilot.tsx` and dropping the old raw-frame-list rendering / echo-test-stub UI (`ws-status`/`ws-frames` testids, sending `'test-event'` back). `ws.test.ts`'s pre-existing "Copilot page WebSocket lifecycle" test asserted exactly that removed behavior and failed after the rewrite.
- **Fix:** Updated that one test to assert only the WS connection lifecycle (opens on mount, closes on unmount, no frame is echoed back) — the behavior the rewritten page actually needs to keep, per 06-CONTEXT.md's own instruction to preserve the connection for a future proposal push.
- **Files modified:** `frontend/src/__tests__/ws.test.ts`
- **Commit:** `48d952e`

---

**Total deviations:** 2 auto-fixed (1 Rule 3, 1 Rule 1)
**Impact on plan:** Both were necessary preconditions/consequences of executing the plan as written in an out-of-sync worktree; no scope creep.

## Issues Encountered

None beyond the deviations above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `Copilot.tsx`'s `useLocation().state?.prefillQuery` seam is in place and tested — 06-03's Guided Tour can navigate to `/copilot` with `state: { prefillQuery: '...' }` to pre-fill the hero query or a jailbreak phrase with no further `Copilot.tsx` change.
- `AgentTopologyCanvas`'s `nodeStatus`/`disconnected` props are the stable contract 06-02/06-03 can drive if either later needs to display topology state elsewhere.
- `POST /api/copilot/query` is registered and tested — ready as the Guided Tour's Step 5 ("AI Safety") real backend call.

## Self-Check: PASSED

- FOUND: frontend/src/pages/Copilot.tsx
- FOUND: frontend/src/components/ChatMessage.tsx
- FOUND: frontend/src/components/AgentTopologyCanvas.tsx
- FOUND: frontend/src/__tests__/Copilot.test.tsx
- FOUND: frontend/src/__tests__/AgentTopologyCanvas.test.tsx
- FOUND: backend/app/routes/copilot_query.py
- FOUND: backend/tests/test_routes_copilot_query.py
- FOUND commit f9a8cc2
- FOUND commit 48d952e
- FOUND commit 9c9e116
- FOUND commit 48a44eb
- Full suites green: frontend `npx vitest run` (119/119 passed), backend `python -m pytest` (373/373 passed)
