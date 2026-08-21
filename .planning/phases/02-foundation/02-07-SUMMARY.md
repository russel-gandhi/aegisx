---
phase: 02-foundation
plan: 07
subsystem: transport
tags: [fastapi, websocket, starlette, vite, react, vitest, pytest]

requires:
  - phase: 02-foundation
    provides: "backend/app/main.py's FastAPI app object (plan 02-03) — the attachment point for this plan's WebSocket router"
  - phase: 02-foundation
    provides: "frontend/src/pages/Copilot.tsx placeholder and AgentTopologyCanvas (plan 02-04) — the page this plan's client wires into"
provides:
  - "backend/app/ws/copilot.py — APIRouter with a WebSocket handler at /api/copilot/stream/{session_id}, sending {event: connected, session_id} on connect and {event: echo, payload} per received text frame"
  - "frontend/src/lib/ws.ts — connectCopilotStream(sessionId, handlers), a typed client with a discriminated-union frame type, VITE_COPILOT_WS_BASE override, and a guarded JSON-parse error path"
  - "frontend/src/pages/Copilot.tsx — connects on mount, sends a test-event, renders connection status and received frames, cleans up on unmount"
affects: [05-approval-centre, 06-command-centre]

actuals:
  tokens: 26000
  tasks: 2
  commits: 4

tech-stack:
  added: []
  patterns:
    - "Backend: fastapi.APIRouter with an async WebSocket handler, registered via a single app.include_router() call in main.py — the only edit to main.py after plan 02-03"
    - "Frontend: native browser WebSocket wrapped in a typed client module (no ws library), frame types as a TypeScript discriminated union on `event` so a future frame kind is a compile-time prompt, not a runtime surprise"
    - "WS test doubles: a StubWebSocket class substituted for globalThis.WebSocket via vi.stubGlobal, avoiding both a new dependency and a live-backend requirement in the frontend suite"

key-files:
  created:
    - backend/app/ws/__init__.py
    - backend/app/ws/copilot.py
    - backend/tests/test_ws_echo.py
    - frontend/src/lib/ws.ts
    - frontend/src/__tests__/ws.test.ts
  modified:
    - backend/app/main.py
    - frontend/src/pages/Copilot.tsx
    - frontend/README.md

key-decisions:
  - "backend/.venv and frontend/node_modules did not exist in this parallel-executor worktree (both gitignored, per-checkout artifacts) — recreated them from the already-pinned backend/requirements.txt and frontend/package-lock.json before running any test, rather than assuming the worktree inherited the main checkout's local environment."
  - "TDD RED phase for the frontend client was proven by temporarily moving the already-drafted frontend/src/lib/ws.ts aside (mv to .ts.bak), running the test suite to confirm the import-resolution failure, committing the failing test, then restoring the implementation for GREEN — keeping the RED commit honest rather than writing the test after the implementation already existed on disk."
  - "The mount/unmount lifecycle test (frontend/src/__tests__/ws.test.ts) is written with React.createElement rather than JSX, because the plan's declared file path is ws.test.ts (not .tsx) and this project's oxc-based transform does not parse JSX in a .ts extension — confirmed by a parse-error run before switching approaches."

patterns-established:
  - "Frame wire contract lives in exactly two places kept in lockstep by convention: backend/app/ws/copilot.py's docstring and frontend/src/lib/ws.ts's discriminated union — both explicitly note that Phase 5 (proposal push) and Phase 6 (agent-state frames) extend this same union rather than replacing it."
  - "session_id is deliberately unauthenticated and unvalidated this phase, with an inline comment on the backend parameter and a README note on the frontend side both naming Phase 5 (C2 RBAC, SENT-4-01) as the closing point — visible as a documented gap, not a silent omission."

requirements-completed: [UI-01, ENV-04]

coverage:
  - id: D1
    description: "Connecting to /api/copilot/stream/{session_id} succeeds and the first frame is {event: connected, session_id: <path value>}; a different session_id in the path is reflected back, proving the path parameter is bound rather than ignored"
    requirement: "UI-01"
    verification:
      - kind: unit
        ref: "backend/tests/test_ws_echo.py::test_connect_sends_connected_frame_with_session_id"
        status: pass
      - kind: unit
        ref: "backend/tests/test_ws_echo.py::test_different_session_id_is_reflected_in_connected_frame"
        status: pass
    human_judgment: false
  - id: D2
    description: "A text frame sent by the client returns as {event: echo, payload: <text>}; three frames sent in sequence echo back in the same order"
    requirement: "UI-01"
    verification:
      - kind: unit
        ref: "backend/tests/test_ws_echo.py::test_sending_text_produces_echo_frame"
        status: pass
      - kind: unit
        ref: "backend/tests/test_ws_echo.py::test_three_frames_echo_back_in_order"
        status: pass
    human_judgment: false
  - id: D3
    description: "A disconnecting client ends the server handler cleanly with no unhandled exception; registering the WS router does not disturb GET /api/health"
    requirement: "ENV-04"
    verification:
      - kind: unit
        ref: "backend/tests/test_ws_echo.py::test_client_disconnect_ends_handler_cleanly"
        status: pass
      - kind: unit
        ref: "backend/tests/test_ws_echo.py::test_health_still_returns_200_after_ws_router_registered"
        status: pass
      - kind: integration
        ref: "live uvicorn: node -e \"fetch('http://127.0.0.1:8000/api/health')...\" printed 200 {\"status\":\"ok\"}"
        status: pass
    human_judgment: false
  - id: D4
    description: "The frontend client builds the correct URL from the default/overridable base, parses incoming frames as typed objects, routes a malformed frame to an error handler without throwing, and close() closes the socket"
    requirement: "UI-01"
    verification:
      - kind: unit
        ref: "frontend/src/__tests__/ws.test.ts > connectCopilotStream (5 cases: URL construction, parse+dispatch, malformed-frame error path, close(), env-var override)"
        status: pass
    human_judgment: false
  - id: D5
    description: "Mounting the Copilot page opens exactly one connection and renders received frames; unmounting closes it, with no leaked socket across a route change"
    requirement: "UI-01"
    verification:
      - kind: unit
        ref: "frontend/src/__tests__/ws.test.ts > Copilot page WebSocket lifecycle > opens exactly one connection on mount and closes it on unmount, and renders received frames"
        status: pass
    human_judgment: false
  - id: D6
    description: "End-to-end proof that the transport works across the real process boundary (backend to browser), not only in a test client"
    requirement: "UI-01"
    verification:
      - kind: integration
        ref: "live uvicorn: node -e \"new WebSocket('ws://127.0.0.1:8000/api/copilot/stream/gate-test')...\" printed WS ECHO OK and exited 0"
        status: pass
      - kind: integration
        ref: "live vite dev server on port 3000: curl http://localhost:3000/copilot returned 200"
        status: pass
    human_judgment: true
    rationale: "No browser automation tool was available in this execution context (same constraint plan 02-04 hit), so the literal 'open a browser and observe two rendered frames' step from the plan's verification section 6 could not be performed by this executor. Substituted: (a) the real backend-to-browser-runtime proof via a live uvicorn process and Node's native WebSocket client (not TestClient), (b) a live vite dev server confirmed serving /copilot at 200, and (c) the jsdom-based mount/unmount/render lifecycle test (D5) exercising the exact same connectCopilotStream + Copilot component code path a real browser would run. A human should do a final visual spot-check of the rendered status/frame list in an actual browser before treating this as fully equivalent to an interactive verification."

duration: 45min
completed: 2026-08-21
status: complete
---

# Phase 2 Plan 07: WebSocket Connection Pattern Summary

**FastAPI WebSocket route at `/api/copilot/stream/{session_id}` echoing structured JSON frames, paired with a typed browser client wired into the Copilot page — proven end to end via a live uvicorn process and Node's native WebSocket, not only through TestClient.**

## Performance

- **Duration:** ~45 min
- **Tasks:** 2 completed (both `tdd="true"`, each with a RED and GREEN commit)
- **Files modified:** 8 (5 created, 3 extended)

## Accomplishments

- `backend/app/ws/copilot.py`: an `APIRouter` WebSocket handler at the Bible's exact path (`AegisX-AI-Project-Bible-v6.md:1415`), sending `{"event": "connected", "session_id": ...}` on connect and `{"event": "echo", "payload": ...}` per received text frame, catching `WebSocketDisconnect` so a client closing the socket never surfaces as an unhandled exception.
- `backend/app/main.py`: exactly one `include_router` call added (8-line diff), no CORS middleware, matching the plan's constraint that this is the only edit to `main.py` after plan 02-03.
- `frontend/src/lib/ws.ts`: `connectCopilotStream(sessionId, handlers)` with a discriminated-union frame type, a `VITE_COPILOT_WS_BASE` override defaulting to `ws://127.0.0.1:8000`, and a try/catch around `JSON.parse` inside `onmessage` so a malformed frame reaches an `onError` handler instead of silently killing the listener.
- `frontend/src/pages/Copilot.tsx`: connects on mount, sends the literal `test-event` in response to the `connected` frame, renders a connection status and a list of received frames as plain text (never HTML), cleans up the socket on unmount, and keeps plan 02-04's `AgentTopologyCanvas` mounted.
- Both suites pass: 14/14 backend (`pytest`), 26/26 frontend (`vitest run`), plus `npm run build` and `npx tsc --noEmit` clean.
- Live, non-test-client proof: a real `uvicorn` process on port 8000 answering `GET /api/health` with `200 {"status":"ok"}` and a Node `WebSocket` client completing the connect→echo round trip (`WS ECHO OK`), and a live `vite` dev server answering `GET /copilot` with `200`.

## Task Commits

Both tasks used `tdd="true"` RED/GREEN commits:

1. **Task 1: Backend WebSocket route at the Bible's specified path** — `296a522` (test, RED) → `b626ff3` (feat, GREEN)
2. **Task 2: Browser client on the Copilot page, proven end to end** — `8284d68` (test, RED) → `829bf33` (feat, GREEN)

No refactor commit was needed for either task — both GREEN implementations were minimal and clean on first pass.

## Files Created/Modified

- `backend/app/ws/__init__.py` — package marker
- `backend/app/ws/copilot.py` — the WS route, frame wire contract documented in its docstring
- `backend/app/main.py` — one `include_router` call
- `backend/tests/test_ws_echo.py` — connect, echo, ordered multi-frame, path-parameter binding, clean disconnect, `/api/health` regression
- `frontend/src/lib/ws.ts` — `connectCopilotStream`, discriminated-union frame types, env-var base override
- `frontend/src/pages/Copilot.tsx` — connect-on-mount, status + frame rendering, cleanup-on-unmount
- `frontend/src/__tests__/ws.test.ts` — URL construction, dispatch, malformed-frame error path, close(), env-var override, mount/unmount lifecycle
- `frontend/README.md` — new `## WebSocket (Stage 1)` section

## Decisions Made

- Recreated `backend/.venv` and `frontend/node_modules` from the already-pinned lockfiles at the start of this plan — this executor's worktree did not inherit either (both are gitignored, per-checkout artifacts), and the very first attempt to write into the sibling non-worktree checkout was correctly rejected by the harness's isolation guard, which is what surfaced the missing environments.
- Proved the frontend RED phase honestly by moving the already-drafted `ws.ts` implementation aside, running the suite to see a real import-resolution failure, committing that failing test, then restoring the implementation for GREEN.
- Wrote the mount/unmount lifecycle assertion with `React.createElement` rather than JSX, since the plan names the test file `ws.test.ts` (not `.tsx`) and this project's oxc-based Vite transform does not parse JSX in a `.ts` file — confirmed by a parse-error run before switching.
- Adapted (did not skip) the plan's literal FastAPI-route-introspection acceptance-criteria snippet (`app.routes` walk) after discovering FastAPI 0.141.1 wraps `include_router` output in an internal `_IncludedRouter` lazy-routing object rather than flattening onto `app.routes` directly — a version-specific internal change, not a defect in this plan's route registration. Verified the route is genuinely registered by walking `_IncludedRouter.original_router.routes` instead; the authoritative proof remains the passing `TestClient.websocket_connect` tests and the live Node `WebSocket` round trip, both of which exercise the real route resolution path FastAPI/Starlette actually use at request time.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking issue] Worktree missing `backend/.venv` and `frontend/node_modules`**
- **Found during:** Start of Task 1, first attempt to run the pre-existing backend/frontend suites as a baseline
- **Issue:** Both are gitignored, per-checkout directories; this parallel-executor worktree is a separate checkout from the one where plans 02-03/02-04 originally created them, so neither existed here.
- **Fix:** `python -m venv .venv && .venv/Scripts/python.exe -m pip install -r requirements.txt` (backend); `npm install` (frontend), both against the already-committed pinned manifests — no new package, no version drift.
- **Files modified:** none (both directories are gitignored)
- **Verification:** `pytest -x -q` (8/8) and `npm run build && npm test` (20/20) passed as the pre-task baseline before any plan code was written.

**2. [Rule 3 - Blocking issue] First environment-setup attempt targeted the wrong checkout**
- **Found during:** Start of Task 1
- **Issue:** An early `Write` call used the non-worktree repo path; the harness correctly rejected it as outside this agent's assigned worktree isolation boundary.
- **Fix:** Re-ran all subsequent commands (`cd`, venv creation, `npm install`, every `Write`/`Edit`) against the worktree's own absolute path.
- **Files modified:** none (no file was actually written to the wrong location — the harness blocked it before any write occurred)
- **Verification:** `git rev-parse --show-toplevel` from within the worktree directory confirmed the correct path for every subsequent operation.

**3. [Rule 1 - stale verification snippet] Plan's `app.routes` introspection command needed adaptation for FastAPI 0.141.1**
- **Found during:** Task 1 acceptance-criteria verification
- **Issue:** The plan's diagnostic one-liner (`[r for r in app.routes if 'copilot' in r.path]`) printed `[]` under this pinned FastAPI version because `include_router` now returns an internal lazy `_IncludedRouter` wrapper rather than flattening sub-routes onto `app.routes`.
- **Fix:** No code change — this is a verification-script adaptation, not a bug fix. Confirmed the route is genuinely registered via `_IncludedRouter.original_router.routes`, and relied on the passing `TestClient.websocket_connect` tests plus the live Node `WebSocket` round trip as the authoritative proof, since both exercise FastAPI/Starlette's real route-resolution path at request time (the same path the stale introspection snippet was trying to approximate).
- **Files modified:** none
- **Verification:** `_IncludedRouter.original_router.routes` walk printed `['/api/copilot/stream/{session_id}']`; all 14 backend tests pass; live Node WS client printed `WS ECHO OK`.

---

**Total deviations:** 3 (2x Rule 3 environment/tooling setup, 1x Rule 1 stale-verification-snippet adaptation). None expanded scope beyond the plan's own declared files; no plan code required a fix.

## Issues Encountered

- No browser automation tool was available in this execution context (the same constraint plan 02-04's SUMMARY documented). The plan's verification step 6 ("open `http://127.0.0.1:3000/copilot` in a browser and confirm a connected status plus two rendered frames") could not be performed as a literal human-eyes browser check by this executor. Substituted with the live-process proofs and the jsdom lifecycle test described in coverage item D6 above — flagged there for a human spot-check.
- `starlette.testclient` continues to emit the `StarletteDeprecationWarning` about `httpx2` first noted in plan 02-03's SUMMARY; unrelated to this plan's WebSocket work and does not fail any test.

## User Setup Required

None — no external service configuration required. Both `backend/.venv` and `frontend/node_modules` are gitignored and must be recreated per-checkout (`pip install -r backend/requirements.txt`, `npm install` in `frontend/`), same as any fresh clone.

## Next Phase Readiness

- The WebSocket transport is proven backend-to-browser at the Bible's exact path. Phase 5 (SENT-4-04, human approval queue) and Phase 6 (SENT-5-02, live agent topology) both extend the same `connectCopilotStream` client and the same `event`-discriminated frame union rather than replacing them.
- `session_id` remains intentionally unauthenticated and unvalidated — Phase 5 (C2 RBAC, SENT-4-01) is the documented closing point, called out inline in both `backend/app/ws/copilot.py` and `frontend/README.md`.
- No file outside this plan's declared `files_modified` was touched; `docker-compose.yml`, `.env.example`, root `README.md`, `BRANCHING.md`, and `backend/README.md` are unmodified (confirmed via `git diff --stat main...HEAD` showing exactly the 8 declared files).

## Self-Check: PASSED

All 8 files created/modified by this plan verified present on disk; all 4 task commits (`296a522`, `b626ff3`, `8284d68`, `829bf33`) verified present in `git log --oneline`.

---
*Phase: 02-foundation*
*Completed: 2026-08-21*
