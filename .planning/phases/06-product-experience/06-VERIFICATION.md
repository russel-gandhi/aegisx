---
phase: 06-product-experience
verified: 2026-08-28T17:20:00Z
status: human_needed
score: 4/4 must-haves verified (presence + wiring + automated behavior); 1 human-verification item outstanding
behavior_unverified: 0
overrides_applied: 0
human_verification:
  - test: "Start the Guided Tour in a real browser against a running backend (docker-compose postgres/qdrant/opa + live FastAPI + Vite dev server, seeded Postgres). Walk all 8 steps unaided (no developer narration): Command Centre -> Copilot hero query -> streamed AssuranceCard -> Blast Radius -> injected AI Safety input -> Generate CAPA + Approve -> Audit Integrity -> closing message. Then restart the tour a second time from the same seeded state."
    expected: "Every step's spotlight correctly highlights the real, currently-visible DOM element (react-joyride's floating-ui positioning, scrolling, and z-index stacking behave correctly in a real browser — this is untestable in jsdom, which has no layout engine and is why the test suite mocks react-joyride entirely). All 7 real-surface steps complete using only real backend calls, and the second run detects the already-approved/rejected demo proposal and skips forward without creating a duplicate `action_proposals` row or getting stuck."
    why_human: "This is Phase 6's own literal success criterion and Build-Map Stage 5 gate ('the full Monitor -> Investigate -> Trust -> Remediate -> Audit loop is walkable without a developer narrating gaps'). 06-03-SUMMARY.md's own coverage table (item D5) explicitly flags this as `human_judgment: true` and states the executing agent's environment had no running docker-compose/Postgres/live dev servers to perform it — the automated integration test (D2) exercises the identical guard logic and click/poll wiring against mocked network boundaries, which is a strong substitute for the D-09 idempotency logic specifically, but proves nothing about real-browser spotlight positioning, real navigation timing, or a genuinely unaided walkthrough. No amount of grep/unit-test evidence can stand in for this."
---

# Phase 6: Product Experience Verification Report

**Phase Goal:** A user lands on a Command Centre dashboard showing real system health at a glance, converses with the Ask GxP Copilot while watching the live agent investigation happen, and can walk the full Monitor→Investigate→Trust→Remediate→Audit loop unaided.
**Verified:** 2026-08-28T17:20:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth (ROADMAP Success Criterion) | Status | Evidence |
|---|---|---|---|
| 1 | Command Centre shows a readiness dial, 6 health mini-cards, and a prototype banner reflecting real, live aggregate system state | ✓ VERIFIED | `frontend/src/pages/CommandCentre.tsx` computes `passed`/`totalChecks` from live `fetchAssuranceCards()`/`fetchSystemSignals()`/`fetchActionProposals()`/`fetchChainVerification()` via `Promise.allSettled` (never `gxp_systems.readiness_score`, confirmed absent from any import in the file); renders exactly 6 fixed `HealthMiniCard`s in UI-SPEC's required order; `PrototypeBanner.tsx` mounted globally in `App.tsx` (`PROTOTYPE — SYNTHETIC DATA — NOT VALIDATED FOR PRODUCTION GxP USE`), present on `/`. `CommandCentre.test.tsx` (15 tests) asserts the 75% dial computation, per-card independence, mini-card #6 naming "DataSync Solutions", partial-failure/empty-state degradation, and system-selector narrowing — all passing. |
| 2 | Ask GxP Copilot page provides a chat interface where a user types the hero query and gets a response, with the Phase 4 verified finding card rendering inline | ✓ VERIFIED | `frontend/src/pages/Copilot.tsx`'s `matchHeroQuery()` routes the seeded hero query to unmodified `streamAssuranceCards()` (`GET /api/systems/{id}/assurance-cards/stream`, Phase 4); `ChatMessage.tsx` renders each accumulated card via the existing, unmodified `<AssuranceCard card={card} />` inline inside the assistant bubble. `Copilot.test.tsx` (23 tests) asserts arrival-order accumulation, empty-state, stream-failure, and abort-safety — all passing. |
| 3 | While a query is in flight, the live agent topology visualization shows agent nodes transition Waiting -> Running -> Complete in real time | ✓ VERIFIED (documented scope refinement) | `AgentTopologyCanvas.tsx`'s `nodeStatus` prop drives A0/A2 to `running` on stream open and A0/A2/C1 to `complete` on the terminal SSE frame, timed off real event arrival (never a fabricated delay); A1/A3–A6/C2/A7/C3 stay permanently dimmed with the literal "A1, A3–A6 not yet implemented (v2)" note. This is a *documented, negotiated* refinement of the literal roadmap wording (SSE-timed synthesis of A0/A2/C1 only, not a literal per-node WebSocket event for all of A0–A6) — recorded as D-02 in `06-CONTEXT.md`, transcribed into `06-UI-SPEC.md`'s Color table, and explicitly called out as accepted in this task's own instructions ("the plan-checker already flagged and accepted this during plan verification"). `AgentTopologyCanvas.test.tsx` (7 tests) and `Copilot.test.tsx`'s topology-transition test assert the exact node-status sequence — passing. |
| 4 | The Guided Tour walks the exact 8-step sequence in Section 14.4, and a user can complete the full loop unaided | ⚠️ Automated coverage strong; live walkthrough not performed | `GuidedTourOverlay.tsx` + `tourSteps.ts` implement all 8 Bible-named beats (7 real surfaces + 1 closing message, per `06-UI-SPEC.md`'s explicit, checker-signed-off collapse table); `resolveRemediationDecision()` is a pure, independently-tested D-09 idempotency guard (generate / approve-existing / skip-terminal, all 3 branches tested); a full integration test drives a *real* `FindingInvestigation` "Generate CAPA" click through to a *real* `Actions` "Approve Action" button appearing, proving `generateCapa` is called exactly once end-to-end via polling, never a WS listener. `GuidedTourOverlay.test.tsx` (13 tests) passing. **However**, the literal claim — "a user can complete the full loop unaided" — requires a real browser + a live running backend/Postgres, which `06-03-SUMMARY.md` itself documents was never exercised (coverage item D5, `human_judgment: true`, rationale: "no running docker-compose services... to drive an end-to-end manual walkthrough"). react-joyride's real spotlight/positioning engine is entirely mocked out in the test suite (jsdom has no layout engine) — see Human Verification below. |

**Score:** 4/4 truths have full artifact+wiring+automated-behavior evidence; 1 of those 4 (Truth 4, the phase's own headline claim) still needs a human-run live walkthrough before the phase can be marked fully proven end-to-end.

### Required Artifacts

| Artifact | Expected | Status | Details |
|---|---|---|---|
| `frontend/src/pages/CommandCentre.tsx` | Live dial + 6 mini-cards, client aggregation | ✓ VERIFIED | Real fetch composition, no stale seed column, wired to `ReadinessDial`/`HealthMiniCard` |
| `frontend/src/components/ReadinessDial.tsx` | SVG arc dial, color-banded | ✓ VERIFIED | `passed`/`total` props, `stroke-dashoffset` animated only on change |
| `frontend/src/components/HealthMiniCard.tsx` | Independent loading/ready/error shell | ✓ VERIFIED | Used by all 6 cards, staggered fade-in |
| `backend/app/routes/system_signals.py` | New access/supplier-signals endpoint | ✓ VERIFIED | `_system_exists` reused (not redefined), `$N`-bound queries, 404/503 paths present |
| `frontend/src/pages/Copilot.tsx` | Real chat + hero-query routing | ✓ VERIFIED | `matchHeroQuery`, `queryCopilot`, `AbortController` cancel-guard all present |
| `frontend/src/components/ChatMessage.tsx` | Chat bubble rendering incl. inline AssuranceCard | ✓ VERIFIED | Reuses `AssuranceCard` unmodified; destructive styling for blocked/error |
| `frontend/src/components/AgentTopologyCanvas.tsx` | `nodeStatus`/`disconnected` props, dimming, v2 note | ✓ VERIFIED | `DIMMED_NODE_IDS`, `STATUS_CLASSES`, disconnected banner all present |
| `backend/app/routes/copilot_query.py` | `POST /api/copilot/query` wrapping `detect_injection()` | ✓ VERIFIED | Real caller for Phase 5's zero-LLM `detect_injection()`, no pool/RBAC (documented, matches precedent) |
| `frontend/src/components/GuidedTourOverlay.tsx` | 8-step interactive tour engine, D-09 guard | ✓ VERIFIED | `resolveRemediationDecision()` pure guard, target-not-found handling, real react-joyride v3 wiring |
| `frontend/src/lib/tourSteps.ts` | 8-entry step table matching UI-SPEC mapping | ✓ VERIFIED | Matches the UI-SPEC's 7-real-surface + 1-closing mapping exactly |
| `frontend/src/__tests__/{Copilot,AgentTopologyCanvas,CommandCentre,GuidedTourOverlay}.test.tsx` | Test coverage for all of the above | ✓ VERIFIED | All exist, all pass (see Behavioral Spot-Checks) |
| `backend/tests/test_routes_{copilot_query,system_signals}.py` | Backend route test coverage | ✓ VERIFIED | Both exist, both pass (12/12 combined) |

### Key Link Verification

| From | To | Via | Status | Details |
|---|---|---|---|---|
| `Copilot.tsx` | `GET /api/systems/{id}/assurance-cards/stream` | `streamAssuranceCards()` (unmodified) | WIRED | Confirmed in `matchHeroQuery`/`runHeroQuery` code path |
| `Copilot.tsx` (non-hero) | `POST /api/copilot/query` | `queryCopilot()` -> `detect_injection()` | WIRED | Confirmed handler body calls `detect_injection(request.query)`, real reason interpolated in UI |
| `Copilot.tsx` | `AgentTopologyCanvas` | `nodeStatus` prop, SSE callback-driven | WIRED | `onCard`/`onDone`/`onError` set `nodeStatus`/`disconnected`, consumed by the canvas |
| `CommandCentre.tsx` | `GET /api/systems/{id}/access-supplier-signals` | `fetchSystemSignals()` (new) | WIRED | Route registered in `main.py`, consumed for mini-cards #5/#6 |
| `CommandCentre.tsx` | `GET /api/audit/verify` | `fetchChainVerification()` (new client fn, existing Phase 5 route) | WIRED | Mini-card #4 "Audit Trail Integrity" reads `chainData.status` |
| `GuidedTourOverlay.tsx` | `GET /api/actions`, `generateCapa()`, `approveAction()` | `resolveRemediationDecision()` guard | WIRED | Integration test proves a real click drives `generateCapa` exactly once, never a second call on skip/approve-existing branches |
| `GuidedTourOverlay.tsx` | `Copilot.tsx` | `navigate(route, {state:{prefillQuery}})` -> `useLocation().state?.prefillQuery` | WIRED | Seam built in 06-01, consumed by 06-03; `Copilot.test.tsx`'s prefillQuery test and the tour's own step-2/step-5 navigation confirm both ends |
| `data-tour` attributes | react-joyride `target` selectors | CSS attribute selectors | WIRED (statically) | All 5 selectors (`readiness-dial`, `mini-card-audit-integrity`, `copilot-input`, `copilot-messages`, `blast-radius-link`, `generate-capa-button`, `approve-action`) present on their real pages; **real-browser targeting behavior is the human-verification item below** |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|---|---|---|---|---|
| UI-03 | 06-02 | Command Centre dashboard shows a readiness dial and health mini-cards | ✓ SATISFIED | `CommandCentre.tsx`, `ReadinessDial.tsx`, `HealthMiniCard.tsx`, `system_signals.py`, all tested |
| UI-04 | 06-01, 06-03 | Ask GxP Copilot page provides chat + live agent topology visualization | ✓ SATISFIED | `Copilot.tsx`, `ChatMessage.tsx`, `AgentTopologyCanvas.tsx`, `copilot_query.py`, `GuidedTourOverlay.tsx`, all tested |

No orphaned requirements found for Phase 6 in `.planning/REQUIREMENTS.md`.

### Anti-Patterns Found

None. The only "not yet implemented" string found (`AgentTopologyCanvas.tsx:104`) is the intentional, literal D-03 required disclosure note ("A1, A3–A6 not yet implemented (v2)"), not a debt marker. No `TODO`/`FIXME`/`XXX`/`TBD`/`HACK`/`PLACEHOLDER` markers in any file this phase modified.

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|---|---|---|---|
| Frontend full suite | `npm run test -- --run` (after `npm install` to restore `react-joyride`, which was declared in `package.json`/`package-lock.json` but not present in this checkout's `node_modules` — an environment artifact, not a code defect; a normal `npm ci` picks it up cleanly) | 142/142 passed, 12/12 files | ✓ PASS |
| Backend full suite | `python -m pytest -q` | 379 passed in 204s | ✓ PASS |
| `copilot_query`/`system_signals` route tests | `pytest tests/test_routes_copilot_query.py tests/test_routes_system_signals.py -v` | 12/12 passed | ✓ PASS |
| Backend router registration | `grep copilot_query\|system_signals backend/app/main.py` | both imported and `include_router`'d | ✓ PASS |
| `data-tour` selector presence | `grep data-tour` across the 4 target pages/components | all 7 selectors present | ✓ PASS |

### Probe Execution

Not applicable — this phase has no `scripts/*/tests/probe-*.sh` probes; verification is via the project's standard vitest/pytest suites, both run above.

### Human Verification Required

### 1. Live, unaided Guided Tour walkthrough against a running backend

**Test:** Start `docker-compose up -d postgres qdrant opa`, run the live FastAPI backend and Vite dev server against seeded Postgres, open the app in a real browser, click "Start Guided Tour", and walk all 8 steps without a developer narrating gaps: Command Centre -> Copilot hero query -> streamed AssuranceCard -> Blast Radius -> injected AI Safety input -> Generate CAPA + Approve -> Audit Integrity -> closing message. Then click "Restart Tour" and repeat from the same (now-decided) demo proposal state.

**Expected:** Every step's spotlight correctly highlights the real, visible target element (no floating-ui misposition, no scroll-into-view failure, no stacking-context clipping); all 7 real-surface steps complete using only genuine backend calls (visible in the Network tab); the second run detects the already-approved/rejected demo `action_proposals` row via `GET /api/actions` and skips straight to Step 7 without creating a duplicate or calling `generate-capa` again.

**Why human:** This is Phase 6's own headline success criterion and the Build-Map Stage 5 gate text verbatim ("the full Monitor -> Investigate -> Trust -> Remediate -> Audit loop is walkable without a developer narrating gaps"). The plan's own `<verification>` section required this exact manual walkthrough, and `06-03-SUMMARY.md`'s coverage table explicitly flags it (`D5`, `human_judgment: true`) as not performed because the executing agent's environment had no live docker-compose/Postgres/dev-server stack available. The automated `GuidedTourOverlay.test.tsx` suite is a strong substitute for the D-09 idempotency *logic* (it drives a real click through real `FindingInvestigation`/`Actions` components against mocked network boundaries) but it mocks `react-joyride` itself out entirely, because jsdom has no layout engine to exercise floating-ui positioning, scrolling, or z-index stacking — none of that can be proven without a real browser.

### Gaps Summary

No must-have truth failed, no artifact is missing or a stub, and no key link is unwired — all four ROADMAP success criteria have complete, passing, automated evidence at the presence/wiring/behavior levels, including a genuinely strong D-09 integration test that drives real components through real clicks. The one outstanding item is the literal, live, real-browser walkthrough of the 8-step Guided Tour against a running backend + seeded Postgres — required by the phase's own success criterion and the plan's own `<verification>` section, and already self-flagged as not performed in `06-03-SUMMARY.md`. This routes the phase to `human_needed` rather than `passed`; no code changes are implicated, only a runtime confirmation step.

---

*Verified: 2026-08-28T17:20:00Z*
*Verifier: Claude (gsd-verifier)*
