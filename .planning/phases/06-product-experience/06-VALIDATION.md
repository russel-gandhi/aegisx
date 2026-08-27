---
phase: 6
slug: product-experience
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-08-27
---

# Phase 6 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (backend); Vitest 4.1.11 + @testing-library/react 16.3.2 (frontend) |
| **Config file** | `backend/pytest.ini`; `frontend/vite.config.ts` (test block) + `frontend/vitest.setup.ts` |
| **Quick run command** | `pytest tests/test_routes_findings.py -x` (backend); `npm run test -- Actions.test.tsx` (frontend) |
| **Full suite command** | `pytest` (backend, from `backend/`); `npm run test` (frontend, from `frontend/`) |
| **Estimated runtime** | ~60 seconds |

---

## Sampling Rate

- **After every task commit:** Run the specific new/changed test file (e.g. `npm run test -- CommandCentre.test.tsx`)
- **After every plan wave:** Run full frontend (`npm run test`) + full backend (`pytest`) suites
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 06-01-01 | 01 | 1 | UI-04 | T-06-01 | Copilot hero query streams `AssuranceCard`s into the chat in arrival order; topology canvas nodes transition Waiting→Running→Complete off real SSE timing | unit (component) | `npm run test -- Copilot.test.tsx` / `npm run test -- AgentTopologyCanvas.test.tsx` | ❌ W0 | ⬜ pending |
| 06-01-02 | 01 | 1 | UI-04 | T-06-01 | Non-hero-query chat input gets an honest "not supported"/injection-blocked response via real `detect_injection()`, never a fabricated answer | unit (backend) | `pytest tests/test_c2_gateway.py -x` + new route test | ⚠️ partial | ⬜ pending |
| 06-02-01 | 02 | 2 | UI-03 | T-06-07 | Command Centre renders a readiness dial value derived from live assurance-cards data across both systems | unit (component) | `npm run test -- CommandCentre.test.tsx` | ❌ W0 | ⬜ pending |
| 06-02-02 | 02 | 2 | UI-03 | T-06-07 | Command Centre's 4th mini-card reflects overdue supplier/access data via new `/api/systems/{id}/access-supplier-signals` route | unit (backend route) + unit (component) | `pytest tests/test_routes_system_signals.py -x`; `npm run test -- CommandCentre.test.tsx` | ❌ W0 | ⬜ pending |
| 06-03-01 | 03 | 3 | UI-03, UI-04 | — | Guided Tour completes all 8 beats without re-creating a duplicate action proposal on a second run (D-09 idempotency guard) | integration | `pytest tests/test_routes_actions.py -x` + new frontend integration test | ❌ W0 | ⬜ pending |
| 06-03-02 | 03 | 3 | UI-03, UI-04 | — | Guided Tour target-not-found retries rather than crashing or silently skipping | integration | new frontend integration test (`GuidedTourOverlay.test.tsx`) | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `frontend/src/__tests__/CommandCentre.test.tsx` — covers UI-03 (dial + 6 mini-cards)
- [ ] `frontend/src/__tests__/Copilot.test.tsx` — covers UI-04 (chat + hero query + non-hero-query path)
- [ ] `frontend/src/__tests__/AgentTopologyCanvas.test.tsx` — covers UI-04 (node status coloring)
- [ ] `frontend/src/__tests__/GuidedTourOverlay.test.tsx` — covers SENT-5-08 (step sequencing + D-09 skip detection)
- [ ] `backend/tests/test_routes_system_signals.py` — covers the new access/supplier signals endpoint (Wave 0 must also create `backend/app/routes/system_signals.py` itself)
- [ ] No framework install needed — both pytest and Vitest are already fully configured and exercised by 25+ existing test files in each suite.

---

## Manual-Only Verifications

*All phase behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
