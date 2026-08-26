# Phase 6: Product Experience - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-08-27
**Phase:** 6-Product Experience
**Areas discussed:** Command Centre content, Copilot chat + hero query flow, Live agent topology semantics, Guided Tour mechanics

---

## Copilot query path

| Option | Description | Selected |
|--------|-------------|----------|
| Reuse assurance-cards SSE, synthesize topology states client-side | No backend changes; frontend infers A0-A6 node states from SSE event arrival; topology illustrative for agents that don't run in v1 | ✓ |
| Invoke the real compiled LangGraph end-to-end with new WS agent-state frames | New endpoint runs graph.ainvoke() through full topology, new `agent_state` WS frame per node | |

**User's choice:** Reuse assurance-cards SSE, synthesize topology states client-side
**Notes:** Avoids duplicating a working streaming mechanism; A1/A3-A6 are stubs anyway in v1 so a "real" graph invocation wouldn't show meaningfully different behavior for those nodes.

---

## Chat input

| Option | Description | Selected |
|--------|-------------|----------|
| Free-text input, but only the hero-query shape actually works | Real text box; anything outside hero-query shape gets an honest "not supported yet" response | ✓ |
| Preset hero-query button/chip, no free text | Just a button/chip + system selector, no text input | |

**User's choice:** Free-text input, but only the hero-query shape actually works
**Notes:** Matches v1 scope (only A2 Compliance real) while still reading as a genuine chat UI.

---

## Card rendering

| Option | Description | Selected |
|--------|-------------|----------|
| Cards stream in one-by-one inside the assistant's chat bubble, in arrival order | Reuses existing SSE completion-order behavior directly | ✓ |
| Assistant posts one placeholder message that all cards fill into after the full batch completes | Wait for all 4 checks then render at once | |

**User's choice:** Cards stream in one-by-one inside the assistant's chat bubble, in arrival order

---

## Dashboard scope

| Option | Description | Selected |
|--------|-------------|----------|
| Aggregate across both seeded systems, with a system selector to drill in | Dial/cards combine both systems by default; selector narrows to one | ✓ |
| Single-system view, no aggregation (defaults to GXP-MFG-DEMO-01) | Always shows one system | |

**User's choice:** Aggregate across both seeded systems, with a system selector to drill in

---

## Mini-cards (multiSelect)

| Option | Description | Selected |
|--------|-------------|----------|
| Compliance findings | Open vs. resolved findings from assurance-cards / A2 checks | ✓ |
| Remediation & approvals | Pending action_proposals count, approved/rejected counts | ✓ |
| Audit trail integrity | verify_chain() healthy/tampered signal | ✓ |
| Access & supplier signals | Overdue supplier/access review signals from seed data | ✓ |

**User's choice:** All four themes selected
**Notes:** Exact split across the required 6 cards left to Claude's discretion (recorded in CONTEXT.md).

---

## Tour mechanics

| Option | Description | Selected |
|--------|-------------|----------|
| Interactive overlay driving real pages/actions | Real navigation, real hero query, real approval, real audit check | ✓ |
| Scripted read-only walkthrough (canned screenshots/steps) | Static slideshow, no real backend calls | |

**User's choice:** Interactive overlay driving real pages/actions
**Notes:** Matches the phase goal's literal wording — "walkable without a developer narrating gaps."

---

## Tour repeatability

| Option | Description | Selected |
|--------|-------------|----------|
| Yes — tour should detect/skip already-completed steps or reset state before starting | Seeds fresh proposal or skips gracefully with a note | ✓ |
| No — out of scope, assume operator resets demo data manually between runs | No in-tour reset logic | |

**User's choice:** Yes — tour should detect/skip already-completed steps or reset state before starting
**Notes:** Full one-command demo reset (HARD-05) stays deferred/out of scope — this is narrower, tour-level defensive handling only.

---

## Topology honesty

| Option | Description | Selected |
|--------|-------------|----------|
| Synthesize transitions, no disclaimer needed | Real topology shape, real event timing, no explicit caveat about which agents are stubs | |
| Add a small "A1, A3–A6 not yet implemented (v2)" note near the canvas | Same synthesis approach plus explicit caveat | ✓ |

**User's choice:** Add a small "A1, A3–A6 not yet implemented (v2)" note near the canvas
**Notes:** Consistent with the product's core value prop — never overstate what's real/verified, extended here to the UI layer for the first time.

---

## Claude's Discretion

- Exact split of the 4 mini-card themes across the required 6 cards
- Exact wire-level shape of the "not supported yet" chat response (client-side guard vs. small honest backend response)
- Exact mechanism for "already completed" detection in the Guided Tour's repeatability handling
- Where the system selector lives in the Command Centre UI (dashboard-level vs. per-card)

## Deferred Ideas

- Real per-agent backend WS state events (`agent_state` frame reflecting actual A0–A6 execution) — deferred to v2, once A1/A3–A6 become real agents (AGT-01..05)
- Full one-command demo reset (HARD-05) — stays deferred; Guided Tour gets only narrow tour-scoped defensive handling
- Live auto-refresh for `/blast-radius` and `/findings` pages (Phase 4 pending todo) — not folded into this discussion's four areas; left open for planner/user to decide scope
