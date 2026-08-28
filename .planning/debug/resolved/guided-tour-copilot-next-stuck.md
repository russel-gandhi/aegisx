---
status: resolved
trigger: "Guided Tour breaks at the Copilot step (\"Ask a Real Question\") — after asking the pre-filled question, clicking \"Next\" in the tour tooltip does nothing (tour doesn't advance to Step 3 \"Evidence, Verified\")."
created: 2026-08-29
updated: 2026-08-29
---

## Symptoms

- **Expected behavior:** After the user submits the pre-filled hero query on the Copilot Guided Tour step (Step 2, "Ask a Real Question"), clicking "Next" in the tour tooltip should advance to Step 3 ("Evidence, Verified"), which targets `[data-tour="copilot-messages"]`.
- **Actual behavior:** Clicking "Next" does nothing — the tour stays on Step 2, no visible error.
- **Error messages:** None reported by user; not yet confirmed in browser console.
- **Timeline:** Reported 2026-08-29 during manual verification; Guided Tour was built in Phase 6 (06-03).
- **Reproduction:** Start Guided Tour → arrive at Copilot step → submit the pre-filled hero query → click "Next" in the tour tooltip.

## Current Focus

- bug_class: Bohrbug (deterministic — reproduced 2/2 in live browser runs)
- status: ROOT CAUSE CONFIRMED — proceeding to fix

reasoning_checkpoint:
  hypothesis: "The Guided Tour's Copilot step is unfinishable because Step 2 spotlights only the textarea (`[data-tour=\"copilot-input\"]`) while instructing the user to click the 'Ask Copilot' submit button, which sits outside the spotlight under react-joyride's pointer-intercepting overlay. The submit therefore never happens, so `messages.length` stays 0, so Step 3's target `[data-tour=\"copilot-messages\"]` (rendered only when `messages.length > 0`) never exists, so 'Next' lands on an unrenderable step and the tooltip unmounts."
  confirming_evidence:
    - "LIVE: `document.elementFromPoint()` at the centre of the 'Ask Copilot' button returns the overlay `path`, not the button."
    - "LIVE: Playwright click on 'Ask Copilot' times out with '<path ...> from <div id=\"react-joyride-portal\"> subtree intercepts pointer events'."
    - "LIVE: `msgCount: 0` / `messagesElPresent: false` after a 10s wait — the query is never submitted."
    - "LIVE: `error:target_not_found ... index=2 target=[data-tour=\"copilot-messages\"] domPresent=false` immediately follows the Next click."
    - "LIVE ARM 2: forcing the click through emits `action=close` (default `overlayClickAction: 'close'`) and STILL does not submit."
    - "Source: v3 default `blockTargetInteraction: false` makes ONLY the spotlighted element interactive."
  falsification_test: "If, after enlarging the spotlight to cover the whole form, the natural (non-forced) click on 'Ask Copilot' still fails to submit — or if messages render but 'Next' still fails to reach Step 3 — the hypothesis is wrong."
  fix_rationale: "Addresses the mechanism, not the symptom. Anchoring the Step-2/5 spotlight on the <form> puts the submit button inside the interactive cut-out, restoring the user action the step demands; this is what actually creates Step 3's target. Setting `overlayClickAction: false` stops stray overlay clicks from silently killing a guided demo. Raising `targetWaitTimeout` on the async step uses the library's own documented self-healing poll so a slow backend stream can never re-create the dead-end. Handling ACTIONS.CLOSE removes the remaining unrecoverable path."
  blind_spots:
    - "Steps 5 (jailbreak query, same form) and 6 (Generate CAPA) also require real clicks; step 6's target IS the button so it should already be interactive, but this was not exercised end-to-end in this session."
    - "Only tested at 1440x900; a narrower viewport could reflow the form and change spotlight geometry."
    - "The backend was live; behaviour with a dead backend (error message path) still yields messages.length > 0, so Step 3 should still resolve, but was not separately verified."
  candidate_causes:
    - "code (UI structure): spotlight anchor is the textarea, excluding the submit button the step requires — CONFIRMED"
    - "code (config/defaults): react-joyride defaults `overlayClickAction: 'close'` + `blockTargetInteraction: false` turn an out-of-spotlight click into a tour-killing CLOSE — CONFIRMED"
    - "code (error handling): `handleEvent` TARGET_NOT_FOUND is a terminal dead-end under controlled mode; `ACTIONS.CLOSE` unhandled — CONFIRMED"
    - "data: messages state empty — CONFIRMED as a downstream *consequence*, not an independent cause"
    - "environment: backend down preventing card stream — ELIMINATED (backend returned 200; and the user echo message alone would satisfy messages.length > 0)"
  and_gate: "YES — this failure requires >1 simultaneous condition. Cause A (submit button outside the interactive spotlight) prevents the target from ever being created. Cause B (TARGET_NOT_FOUND is a non-recoverable dead-end in controlled mode, plus unhandled ACTIONS.CLOSE) converts that into a permanently frozen tour rather than a graceful wait. Fixing only A would leave a latent trap on any slow-rendering target; fixing only B would leave the user unable to complete the step's required action. Both must be fixed."

- next_action: Apply the 4-part fix in `frontend/src/pages/Copilot.tsx` and `frontend/src/components/GuidedTourOverlay.tsx`, then re-run the live Playwright reproduction to verify the natural click submits and the tour reaches Step 3.

## Evidence

- timestamp: 2026-08-29
  checked: `frontend/node_modules/react-joyride/package.json` + `dist/index.d.cts` prop surface
  found: react-joyride **3.2.0** genuinely installed. `onEvent?: EventHandler` (line 242) and top-level `options?: Partial<Options>` (line 246) are both real v3 props, as are `stepIndex` (line 265).
  implication: ELIMINATES "wrong prop name / v2-vs-v3 API mismatch" as a cause. `GuidedTourOverlay.tsx`'s `onEvent={handleEvent}` and `options={...}` usage is correct for the installed version. The in-file comments are accurate.

- timestamp: 2026-08-29
  checked: `react-joyride/dist/index.mjs` TARGET_NOT_FOUND branch (~line 1230)
  found: On a missing/invisible target the library runs `addFailure(currentStep, "target_not_found"); emitEvent(EVENTS.TARGET_NOT_FOUND, currentStep);` and then auto-advances the index ONLY under `if (!currentState.controlled)`.
  implication: In controlled mode (this app passes `stepIndex`, so `controlled === true`) the library deliberately does NOT self-advance on a missing target. Advancement is 100% the app's responsibility. `handleEvent`'s TARGET_NOT_FOUND branch sets a note and `return`s without touching `stepIndex` — so IF this event fires, "Next does nothing" is the exact expected outcome. Consistent with the leading hypothesis; not yet proof that this event is the one firing.

- timestamp: 2026-08-29
  checked: `frontend/src/lib/tourSteps.ts` steps 2/3 and `frontend/src/pages/Copilot.tsx` render tree
  found: Step 2 (index 1) targets `[data-tour="copilot-input"]` (the textarea, always rendered). Step 3 (index 2) targets `[data-tour="copilot-messages"]`, rendered only in the `messages.length > 0` branch (Copilot.tsx:255-265). BOTH steps have `route: '/copilot'`.
  implication: Because both steps share the same route, `GuidedTourOverlay`'s navigation effect early-returns (`location.pathname === route`) — so there is NO remount/navigation between steps 2 and 3. Also, after a submit `messages.length >= 1` unconditionally (the user echo message is pushed synchronously in `handleSubmit`, before any network call), so the target element SHOULD exist even with the backend down. This WEAKENS the "target genuinely missing" form of the hypothesis and points instead at a visibility/timing or event-plumbing cause.

- timestamp: 2026-08-29
  checked: `frontend/src/__tests__/GuidedTourOverlay.test.tsx` lines 19-79
  found: The entire `react-joyride` module is `vi.mock`ed. The stub's "Next" button unconditionally calls `props.onEvent({ type: STEP_AFTER, action: NEXT, status: RUNNING })` regardless of whether any target exists in the DOM.
  implication: MAJOR — the existing test suite can never catch this class of bug. Every passing tour test asserts only `GuidedTourOverlay`'s own reducer logic against a synthetic event stream that is guaranteed well-formed. The real library's target-resolution/lifecycle path is entirely untested. This is the "why wasn't this caught" gate gap.

- timestamp: 2026-08-29
  checked: LIVE reproduction — Playwright + system Chrome (1440x900) against the real Vite dev server (:3000) and the real backend (:8000), with temporary `console.log` instrumentation in `handleEvent` plus Joyride's `debug` prop. ARM 1 = natural user click.
  found: Observed event sequence on the Copilot step:
    `step:before action=next index=1 target=[data-tour="copilot-input"]` -> `tooltip` (Step 2 renders fine)
    Probe `document.elementFromPoint(centre of "Ask Copilot" button)` returns **`path.`** — i.e. the Joyride overlay SVG, NOT the button.
    Playwright click on "Ask Copilot" **times out**: `<path ... d="M0 0H1440V1006H0Z M18 914H1309...V988...Z"> from <div id="react-joyride-portal"> subtree intercepts pointer events`.
    State stays `messagesElPresent: false, msgCount: 0` — the query is NEVER submitted.
    Then clicking "Next": `step:after action=next index=1` fires, immediately followed by
    `error:target_not_found action=next index=2 lifecycle=ready target=[data-tour="copilot-messages"] domPresent=false`.
    Final DOM: `step: "NO-TOOLTIP"`, `notFoundNote: "PRESENT"`.
  implication: **ROOT CAUSE CONFIRMED.** The spotlight cut-out (`M18 914 ... V988`) covers only the textarea. The "Ask Copilot" submit button lies OUTSIDE the hole, under the overlay, so the click the step's own copy demands ("submit it yourself") is physically impossible. No submit -> no messages -> Step 3's target never exists -> TARGET_NOT_FOUND -> tour dead. Note the symptom is actually WORSE than reported: the tooltip does not merely fail to advance, it **unmounts entirely**, leaving only a small amber note.

- timestamp: 2026-08-29
  checked: LIVE reproduction ARM 2 — identical flow but Playwright `click({ force: true })` to bypass the overlay interception.
  found: The forced click emitted `step:after action=**close** index=1` and `messagesElPresent` stayed `false`. The form still did not submit; the pointer event was consumed by the overlay and interpreted by Joyride as an overlay click.
  implication: Confirms a THIRD contributing defect. `react-joyride` default `overlayClickAction: 'close'` means any click landing on the overlay fires `ACTIONS.CLOSE`. `handleEvent`'s `STEP_AFTER` branch handles only `ACTIONS.NEXT`/`ACTIONS.PREV`, so a `CLOSE` action leaves `stepIndex` untouched while Joyride's own lifecycle completes -> tooltip unmounts, tour dead, no recovery.

- timestamp: 2026-08-29
  checked: `react-joyride/dist/index.mjs` defaults block (L20-49) and `dist/index.d.cts` option docs (L569-624)
  found: v3 defaults: `blockTargetInteraction: false` (spotlighted element IS interactive), `overlayClickAction: 'close'`, `targetWaitTimeout: 1000`. v3 renamed v2's `spotlightClicks` -> `blockTargetInteraction` (inverted) and `disableOverlayClose` -> `overlayClickAction`.
  implication: Only the SPOTLIGHTED element is interactive — which is exactly why the out-of-spotlight submit button is unreachable. Confirms the fix must bring the submit button INSIDE the spotlight. Also gives the idiomatic fix for the dead-end: the library already polls every 100ms up to `targetWaitTimeout` and self-heals to `LIFECYCLE.READY` the moment the element appears (L1172-1190) — so raising `targetWaitTimeout` on the async step is the library-sanctioned recovery, not a hand-rolled retry.

- timestamp: 2026-08-29
  checked: `grep data-tour` across `frontend/src`
  found: `data-tour` attributes appear only in page/component source; no test asserts on them (tour tests assert `mock-joyride-target` text sourced from `tourSteps.ts`).
  implication: Moving the `data-tour="copilot-input"` anchor from the textarea to its wrapping form is safe — no test coupling to break.

## Eliminated

- hypothesis: "`onEvent`/`options` are v2-only prop names, so the callback never fires (wrong-API mismatch)"
  evidence: react-joyride 3.2.0 `dist/index.d.cts` declares `onEvent?: EventHandler` (L242) and `options?: Partial<Options>` (L246) as first-class v3 props.
  timestamp: 2026-08-29

- hypothesis: "Step 3's target is missing because of a React render/DOM-update race — Joyride evaluates the target before React commits the messages container"
  evidence: LIVE ARM 1 shows `msgCount: 0` and `messagesElPresent: false` even after a 10-second wait with no pending work. The element is not late — it is never created at all, because the submit never happened. Furthermore the library polls for 1000ms before declaring TARGET_NOT_FOUND, which would absorb any realistic commit race.
  timestamp: 2026-08-29

- hypothesis: "The `stepIndex` controlled-sync is broken / `setStepIndex` never fires on Next"
  evidence: LIVE ARM 1 shows `step:after action=next index=1` firing correctly and Joyride subsequently attempting `index=2` with Step 3's target — proving `stepIndex` DID advance to 2. The advance works; the destination step is unrenderable.
  timestamp: 2026-08-29

## Resolution

- root_cause: |
    AND-gate — two independently-necessary contributing causes:

    **A. The step's required user action was physically impossible.** Step 2 ("Ask a Real
    Question") anchored its spotlight on `[data-tour="copilot-input"]`, which was the
    `<textarea>` alone, while the step copy instructs "submit it yourself". react-joyride
    renders a full-screen overlay with a spotlight cut-out and intercepts pointer events
    everywhere outside it; only the spotlighted element remains interactive (v3 default
    `blockTargetInteraction: false`). The "Ask Copilot" submit button is a SIBLING of the
    textarea, so it sat under the overlay. Verified live: `elementFromPoint()` over the
    button returned the overlay `<path>`, and the click was intercepted. Worse, with v3's
    default `overlayClickAction: 'close'`, a click that does land on the overlay is
    interpreted as ACTIONS.CLOSE — so even a forced click tore the step down instead of
    submitting. Net effect: the hero query was NEVER submitted, so `messages.length`
    stayed 0, so `[data-tour="copilot-messages"]` (Step 3's target, rendered only when
    `messages.length > 0`) never existed.

    **B. The resulting missing-target state was an unrecoverable dead-end.** Clicking
    "Next" advanced `stepIndex` to 2 correctly, but Joyride could not resolve Step 3's
    target and emitted `error:target_not_found`. In CONTROLLED mode (`stepIndex` prop set)
    the library deliberately refuses to auto-advance — `dist/index.mjs` guards the recovery
    branch with `if (!currentState.controlled)`. `handleEvent`'s TARGET_NOT_FOUND branch
    only set a cosmetic amber note and returned, and its STEP_AFTER branch handled only
    NEXT/PREV, ignoring CLOSE. So the tooltip unmounted entirely and the tour froze with
    no path forward.

    A alone would leave a latent trap on any slow-rendering target; B alone would leave the
    user unable to perform the step's required action. Both were required to produce the
    reported symptom, and both are fixed.

- fix: |
    1. `Copilot.tsx` — moved the `data-tour="copilot-input"` anchor from the `<textarea>`
       to the wrapping `<form>`, so the spotlight cut-out contains BOTH the textarea and
       the "Ask Copilot" submit button. This is what actually restores the user action
       that creates Step 3's target. (Also fixes Step 5, which reuses the same target for
       the jailbreak submit and was broken identically.)
    2. `GuidedTourOverlay.tsx` — set `overlayClickAction: false` so a stray click on the
       overlay is inert rather than silently destroying a guided demo.
    3. `GuidedTourOverlay.tsx` — added `targetWaitTimeout: 15000` for the three steps whose
       targets only exist after real backend work (indexes 2, 3, 6). The library already
       polls every 100ms and self-heals to LIFECYCLE.READY once the element appears, so a
       slow stream now degrades into a brief wait instead of a permanent dead-end.
    4. `GuidedTourOverlay.tsx` — `handleEvent` now handles `ACTIONS.CLOSE` on STEP_AFTER by
       calling `reset()`, returning the user to the "Start Guided Tour" entry point instead
       of stranding them under an overlay with no tooltip.

- verification: |
    guardrail_verdict: accepted

    - signal_1_regression_test_bisects_the_bug: PASS. New `GuidedTourTargetReachability.test.tsx`
      (5 tests) asserts the structural invariant "a step's spotlight target must contain every
      control the step tells the user to operate". MUTATION-VERIFIED: reverting the anchor to the
      textarea fails 3/5 (`expected false to be true`, `expected 'TEXTAREA' not to be 'TEXTAREA'`).
      The 3 new guards in `GuidedTourOverlay.test.tsx` were mutation-verified the same way —
      removing `overlayClickAction: false`, the CLOSE branch, and the targetWaitTimeout override
      fails exactly those 3 tests.
    - signal_2_not_deletion_only: PASS. +126/-5; the change adds a structural anchor move plus
      three explicit behavioural guards. No test or assertion was weakened or removed.
    - signal_3_bug_returns_on_revert: PASS. Demonstrated twice via the mutation runs above.
    - signal_4_full_suite: PASS. 150/150 tests across 13 files (was 142/12 — 8 new tests, zero
      regressions).
    - signal_5_typecheck_lint_build: PASS. `tsc -b` clean; `vite build` succeeds; oxlint warning
      count unchanged at 7 (all pre-existing `only-export-components`/`set-state-in-effect`).
    - signal_6_live_reproduction: PASS. Playwright + system Chrome against the real Vite dev
      server (:3000) and real backend (:8000), instrumentation removed:
        * `elementFromPoint` over "Ask Copilot" now returns the BUTTON, not the overlay path.
        * The natural (non-forced) click submits: `msgCount: 2`, `messagesElPresent: true`.
        * "Next" reaches `Step 3 of 8 — "Evidence, Verified"`, `notFound: no`.
        * Full walk verified steps 1→6 with real clicks, including Step 5's jailbreak submit
          (which was broken by the same defect). Step 6 correctly entered the D-09
          seed-and-continue approve phase. Stopped before Generate CAPA / Approve to avoid
          mutating real GxP demo data.

    oracle_type: derived (structural containment contract), not implicit — the assertion states
    the required invariant rather than merely checking for absence of a crash.

- files_changed:
    - frontend/src/pages/Copilot.tsx (spotlight anchor moved from textarea to form)
    - frontend/src/components/GuidedTourOverlay.tsx (overlayClickAction, targetWaitTimeout, ACTIONS.CLOSE)
    - frontend/src/__tests__/GuidedTourTargetReachability.test.tsx (NEW — 5 structural regression tests)
    - frontend/src/__tests__/GuidedTourOverlay.test.tsx (3 new guards + mock exposes wait/overlay options)
