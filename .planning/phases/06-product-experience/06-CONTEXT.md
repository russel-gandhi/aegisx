# Phase 6: Product Experience - Context

**Gathered:** 2026-08-27
**Status:** Ready for planning

<domain>
## Phase Boundary

A user lands on a Command Centre dashboard showing real system health at a glance, converses with the Ask GxP Copilot while watching the live agent investigation happen, and can walk the full Monitor→Investigate→Trust→Remediate→Audit loop unaided via an 8-step Guided Tour (Bible §14.4). Maps to Build-Map Stage 5, v1-required tickets SENT-5-01 (Command Centre) and SENT-5-08 (Guided Tour); satisfies UI-03 and UI-04.

</domain>

<decisions>
## Implementation Decisions

### Copilot query path
- **D-01:** The Copilot chat's hero query reuses the existing `GET /api/systems/{id}/assurance-cards/stream` SSE endpoint (Phase 4, `routes/findings.py`) rather than invoking the compiled LangGraph (`app/graph/state.py`). That endpoint already calls A2 + C1 directly and streams `AssuranceCard`s in completion order — deliberately bypassing the 5-way A1–A6 fan-out, which has no real work to do since only A2 Compliance is real in v1. No backend changes to the query path itself. — **Reversibility:** reversible — swapping to a real graph-invoking endpoint later only changes what the frontend calls; the SSE contract shape (cards streamed in order) can stay the same.
- **D-02:** The live agent topology visualization (`AgentTopologyCanvas`) does NOT reflect literal per-node backend state. Node Waiting → Running → Complete transitions are synthesized client-side, timed off real SSE event arrival from D-01's stream (not fabricated delays) — e.g. A0/A2 transition to Running when the stream opens, C1 transitions per-card as each `AssuranceCard` arrives, A7/C3 stay Waiting (out of scope for a read-only query). A1 and A3–A6 stay permanently Waiting/dimmed since they don't run for this query type in v1.
- **D-03:** A small, visible note near the topology canvas states "A1, A3–A6 not yet implemented (v2)" — required so the visualization never implies more agent breadth is real than v1 actually built. This is a direct extension of the product's own core value prop (never overstate what's verified/real).

### Chat input
- **D-04:** The Copilot page has a real free-text input (reads as an actual chat), but only the hero-query shape (a system-readiness question against a known/seeded system id) is actually wired to the assurance-cards flow. Any other input receives a clear, honest "not supported yet" response rather than a fabricated or misleading answer — consistent with D-02/D-03's never-overstate discipline.
- **D-05:** `AssuranceCard`s stream into the assistant's chat bubble one-by-one, in arrival order, directly reusing the existing SSE completion-order behavior from `/assurance-cards/stream` — no batching/waiting for all 4 checks before rendering.

### Command Centre dashboard content
- **D-06:** The readiness dial and 6 health mini-cards aggregate across both seeded systems (`GXP-MFG-DEMO-01`, `BUS-IT-DEMO-02`) by default, computed from real backend data (assurance-cards pass/fail ratio for the dial). A system selector lets the user narrow the view to one system. — **Reversibility:** reversible — aggregation logic and selector are additive UI/query concerns, not a schema change.
- **D-07:** The 6 mini-cards cover four real signal themes (exact split across 6 cards is Claude's discretion, see below): (1) Compliance findings — open/resolved from A2 checks via assurance-cards; (2) Remediation & approvals — pending/approved/rejected counts from Phase 5's `action_proposals`; (3) Audit trail integrity — `verify_chain()` healthy/tampered signal from Phase 5's audit trail; (4) Access & supplier signals — overdue supplier/access review data already present in Phase 1 seed data (e.g. overdue DataSync Solutions supplier), even though the real A6 Access agent itself is v2.

### Guided Tour mechanics
- **D-08:** The 8-step Guided Tour (Bible §14.4) is an interactive overlay that drives the user through REAL pages performing REAL actions and REAL backend calls — navigate to Command Centre, ask the hero query on the Copilot page, watch topology + streaming cards, approve a proposal on the Actions.tsx Approval Centre, check the audit trail — not a scripted/static walkthrough. This is the literal proof of "the loop is walkable without a developer narrating gaps." — **Reversibility:** costly — once demo scripts, screenshots, and any judge-facing walkthrough reference the exact 8 real steps, swapping to a canned/scripted tour later means re-authoring the tour content, not just a config flip.
- **D-09:** The tour must handle repeat runs without breaking: if a step's target state is already satisfied (e.g. the demo proposal is already approved from a prior run), the tour either seeds a fresh action-proposal for that step or detects completion and skips forward gracefully with a note — it never fails or gets stuck reperforming an already-done irreversible action. A full one-command demo reset (HARD-05) remains out of scope/deferred — this is tour-level defensive handling only, not a DB reset mechanism.

### Claude's Discretion
- Exact split of the 4 mini-card themes (D-07) across the required 6 cards — e.g. which theme gets 2 cards vs. 1 (planner's call, informed by what's cheapest/most real to compute from existing Phase 4/5 data).
- Exact wire-level shape of the "not supported yet" response for non-hero-query chat input (D-04) — client-side guard vs. a real (small, honest) backend response.
- Exact mechanism for the "already completed" detection in D-09 (e.g. checking `action_proposals` status before starting the approval step vs. tour-local state).
- Where the system selector (D-06) lives in the UI (dashboard-level control vs. per-card).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Bible sections (source of truth, Rule 14)
- `AegisX-AI-Project-Bible-v6.md` §11.1 — Command Centre dashboard: readiness dial, health mini-cards, prototype banner
- `AegisX-AI-Project-Bible-v6.md` §11.2 — Ask GxP Copilot / Assurance Card field list (already built in Phase 4; this phase wires it into chat)
- `AegisX-AI-Project-Bible-v6.md` §10.3 — React Flow Visualization: node-type styling, "Trace Chain" pattern (precedent for topology canvas styling)
- `AegisX-AI-Project-Bible-v6.md` §14.4 — Guided Tour 8-step sequence (exact steps to implement)
- `AegisX-AI-Project-Bible-v6.md` §1.2 — fixed topology `C2 → A0 → [A1…A6] → C1 → A7 → C3` (what `AgentTopologyCanvas` already renders structurally)
- `AegisX-AI-Project-Bible-v6.md` §1.3 — deterministic-first decision table (no LLM in any decision path this phase touches)

### Build-Map (ticket contracts)
- `AegisX-Build-Map.md` Stage 5 — SENT-5-01 (Command Centre, P0), SENT-5-08 (Guided Tour, P0); SENT-5-02 (Ask GxP Copilot chat + live topology) as context

### Requirements & Roadmap
- `.planning/REQUIREMENTS.md` — UI-03 (Command Centre), UI-04 (Copilot chat + topology)
- `.planning/ROADMAP.md` §"Phase 6: Product Experience" — goal, 4 success criteria, `**Mode:** mvp`, dependency on Phase 5

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `frontend/src/pages/Copilot.tsx` — currently a bare WS echo-test stub (connects to `/api/copilot/stream/{session_id}`, renders raw frames); this phase replaces its body with the real chat UI, keeping the existing `connectCopilotStream` WS usage only for `action_proposal_created` frames (already wired from Phase 5), not for the hero-query response path (that's SSE, per D-01).
- `frontend/src/pages/CommandCentre.tsx` — currently a static placeholder paragraph, no data. Full rebuild this phase.
- `frontend/src/components/AgentTopologyCanvas.tsx` — already renders the correct fixed topology (C2→A0→[A1-A6]→C1→A7→C3) as React Flow nodes/edges with no color/state logic yet; its own docstring says "Phase 6's live agent-state streaming replaces node *colours* only, not this component" — confirms D-02's approach was anticipated.
- `backend/app/routes/findings.py` — `GET .../assurance-cards` (blocking, `asyncio.gather`, input order) and `GET .../assurance-cards/stream` (SSE, `asyncio.as_completed`, completion order) — the `/stream` route is the literal data source for D-01/D-05.
- `frontend/src/lib/ws.ts` — discriminated-union `CopilotStreamFrame` (`connected` / `echo` / `action_proposal_created`) — Phase 6 does NOT need to add a new WS frame type per D-01/D-02 (topology state is synthesized from SSE, not a new WS event).
- `backend/app/routes/actions.py` (Phase 5) — Approval Centre backend the Guided Tour's remediate/approve step (D-08) drives for real.
- `backend/app/agents/c1_verifier.py` / `a2_compliance.py` — the deterministic check functions the assurance-cards flow (and thus the Copilot hero query) is built on; read-only inputs, not modified by this phase.

### Established Patterns
- Deterministic-first (Bible §1.3) — this phase adds no new decision logic; it's presentation/orchestration of already-verified findings and already-built approval/audit backends.
- SSE-for-streaming-results pattern already established in `findings.py`'s `/stream` route (`asyncio.as_completed`, `text/event-stream`) — reuse, don't invent a second streaming mechanism for the same data.
- "Never present unverified output as real" discipline extends visually in this phase (D-02/D-03/D-04) — first phase where the product's evidence-honesty thesis becomes a UI/UX rule, not just a backend one.

### Integration Points
- Copilot chat (new) reads from `findings.py`'s existing `/assurance-cards/stream` route — no new backend route needed for the hero query itself.
- Command Centre (new) needs new aggregate-read backend support (D-06/D-07) — likely a new lightweight summary endpoint or client-side aggregation over existing per-system endpoints (`assurance-cards`, `action_proposals` list, audit `verify_chain()` status, supplier/access seed data) — planner's call on backend vs. frontend aggregation.
- Guided Tour (new) is a cross-page overlay component that must integrate with `CommandCentre.tsx`, `Copilot.tsx`, `Actions.tsx`, and whatever surfaces audit trail status — likely lives in `frontend/src/components/` with route-aware step logic.

</code_context>

<specifics>
## Specific Ideas

No further specific UI/visual references beyond the decisions above — open to standard approaches for exact card layout, dial rendering library, and tour overlay implementation (e.g. custom vs. a lightweight tour library).

</specifics>

<deferred>
## Deferred Ideas

- Real per-agent backend WS state events (a true `agent_state` frame type reflecting actual A0–A6 execution) — deferred until the compiled LangGraph's full fan-out is actually invoked for a query (v2, once A1/A3–A6 become real agents per AGT-01..05).
- Full one-command demo reset (HARD-05) — Guided Tour gets narrow, tour-scoped defensive handling (D-09) only, not a general reset mechanism.
- Live auto-refresh for `/blast-radius` and `/findings` pages (raised in Phase 4 verification, logged in STATE.md Pending Todos) — not picked up in this discussion; remains a candidate but wasn't folded into any of the four discussed areas. Left for planner/user to decide whether it belongs in this phase's scope or a later polish pass.

### Reviewed Todos (not folded)
None — `todo.match-phase` returned zero matches for Phase 6.

</deferred>

---

*Phase: 06-product-experience*
*Context gathered: 2026-08-27*
