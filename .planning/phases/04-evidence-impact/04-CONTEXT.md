# Phase 4: Evidence & Impact - Context

**Gathered:** 2026-08-21
**Status:** Ready for planning

<domain>
## Phase Boundary

The NetworkX evidence graph builds from live Postgres state and Blast Radius traversal returns correct downstream-impacted nodes, both wired into the browser, and a verified finding renders as a real Assurance Card. (Build-Map Stage 3, Gate: "NetworkX graph builds from live Postgres state; Blast Radius returns correct downstream nodes for a seeded change record.") Backend-graph-and-card phase — the full Ask GxP Copilot chat experience (Phase 6) is out of scope; Phase 4 exposes the Assurance Card through its own dedicated route.

</domain>

<decisions>
## Implementation Decisions

### Graph construction strategy
- **D-01:** Domain tables (`requirements`, `test_cases`, `risks`, `design_elements`, `changes`, `incidents`, `access_reviews`, `access_records`, `documents`, `suppliers`, etc.) remain the single source of truth. `graph_nodes`/`graph_edges` (already in schema, currently empty) are a **materialized cache** derived from domain state, not an independent data source — they never hold a fact that isn't derivable from the domain tables plus the new junction table (D-03).
- **D-02:** Rebuild is an **explicit, on-demand step** — a `POST /api/systems/{id}/evidence-graph/rebuild` (exact route TBD by planner) recomputes `graph_nodes`/`graph_edges` for that system from domain tables and overwrites. The `GET /api/systems/{id}/evidence-graph` read endpoint always reads from the cache tables and assumes freshness — it does NOT rebuild inline. — **Reversibility:** costly — swapping to auto-rebuild-on-read later means removing the explicit rebuild trigger from the frontend "Trace Chain" flow and the demo script, and re-testing staleness behavior.

### Change→downstream edge derivation
- **D-03:** Add an explicit **additive junction table** now (e.g. `change_affects(change_id, entity_type, entity_id)`), populated by a seed fixture for the demo change record — same pattern as Phase 3's `002_urs_fixture.sql` additive-seed precedent (D-05 there). This is a deliberate, user-approved schema change for this phase, not scope creep. — **Reversibility:** one-way — once `graph_edges` traversal and any seeded demo data depend on this table shape, changing the junction table's columns needs a migration and reseeding.
- Edge derivation priority, most to least authoritative: (1) explicit FK relationships already in the schema (e.g. `requirements.test_case_id` → `REQUIREMENT --VERIFIED_BY--> TEST_CASE`), (2) the new `change_affects` junction table / other explicit metadata keys, (3) seeded demo mappings for the one seeded change record GRAPH-02 requires, (4) hand-authored `graph_edges` rows as a last resort. **No LLM-generated edges, ever** — Bible Section 1.3's deterministic-first boundary applies to graph construction exactly as it does to C1.
- Same-`system_id` blanket association (treating every entity on a system as affected by every change on that system) was explicitly rejected as too coarse for a Critical-review graph algorithm — GRAPH-02 requires the *correct* downstream set, not "everything on this system."
- Fragile text/keyword matching between `change_actions.description` and `req_text`/`design_elements.description` was explicitly rejected as too unreliable for a deterministic, testable relationship.

### Assurance Card placement
- **D-04:** Build a reusable `AssuranceCard` component now, exposed through a **dedicated finding/evidence investigation route** in Phase 4 (not embedded in a chat UI, since the full Copilot chat doesn't exist until Phase 6). Phase 6 will reuse this same component inside the Copilot chat thread rather than building a second card.
- Card shows CLAIM / EVIDENCE / RULE / DETERMINISTIC CHECK / CONFIDENCE, sourced entirely from server-trusted data (the C1 `AgentFinding` + confidence output from Phase 3) — never LLM-generated UI, matching EVID-03 and Bible Section 11.2's field list.

### Evidence Graph API + React Flow scope
- **D-05:** Build the `/api/systems/{id}/evidence-graph` (+ rebuild endpoint) and a **basic** React Flow rendering: real nodes, real edges, click-through to node/entity details. In scope for Phase 4.
- Visual polish — node-type color coding beyond basic differentiation, the `animate-pulse` Trace Chain highlight animation described in Bible §10.3, and any other cosmetic pass — is explicitly **deferred to Phase 6** (or a later polish pass), not built in Phase 4. Phase 4's bar is "the graph is real, traversal is correct, and it's visible in the browser," not demo-polish.

### Claude's Discretion
- Exact junction table column names/types beyond the shape implied above (`change_affects(change_id, entity_type, entity_id)`).
- Exact REST route names/shapes for the rebuild and read endpoints (`/api/systems/{id}/evidence-graph`, `/api/systems/{id}/evidence-graph/rebuild` are directional, not locked).
- Exact `AssuranceCard` component prop shape and the dedicated investigation route's URL/name.
- React Flow node/edge typing and layout algorithm specifics not covered by Bible §10.3's high-level description.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Bible sections
- `AegisX-AI-Project-Bible-v6.md` §10.1 (NetworkX Graph Definition — `build_evidence_graph`, `find_downstream_impacts`) — baseline pattern for graph construction; note it queries domain tables directly, and this phase's decisions (D-01/D-02) reconcile that with §14.3's cache-table wording.
- `AegisX-AI-Project-Bible-v6.md` §10.3 (React Flow Visualization) — node-type styling, "Trace Chain" button, `animate-pulse` highlight (deferred per D-05).
- `AegisX-AI-Project-Bible-v6.md` §11.2 (Ask GxP Copilot / Assurance Card field list — CLAIM / EVIDENCE ID / ALCOA+ score / Confidence Level / Model Attribution) — the card's content contract; Phase 4 builds the component, Phase 6 wires it into chat.
- `AegisX-AI-Project-Bible-v6.md` §14.3 (Blast Radius / Impact Analysis) — the Graph Questions list (directly/indirectly affected entities, affected requirements/tests/risks/changes/controls, highest-impact downstream dependency) and the example relationship-type list (`REQUIREMENT --VERIFIED_BY--> TEST_CASE`, `CHANGE --AFFECTS--> REQUIREMENT`, etc.) — the authoritative source for what Blast Radius must answer correctly for GRAPH-02.
- `AegisX-AI-Project-Bible-v6.md` §1.3 (deterministic-first decision table) — LLMs may explain/summarize impact but must never invent graph relationships or edges.

### Schema
- `infra/postgres/initdb/001_schema.sql` — existing `graph_nodes` (lines ~212-217) and `graph_edges` (lines ~219-223) cache tables (currently unseeded); `requirements`, `risks`, `design_elements`, `test_cases`, `test_results`, `incidents`, `access_reviews`, `access_records`, `changes`, `change_actions`, `findings`, `evidence_refs` — the domain tables the graph is built from. **No existing FK connects `changes`/`change_actions` to `requirements`/`design_elements`/`test_cases`** — this gap is why D-03's junction table is needed.
- `infra/postgres/seed/002_urs_fixture.sql` + `infra/apply-seed.sh` / `infra/verify-seed.sh` — the additive-seed-fixture pattern (Phase 3, D-05 there) to follow for the new `change_affects` seed data.

### Requirements
- `.planning/REQUIREMENTS.md` — EVID-03 (line 32), GRAPH-01/02/03 (lines 37-39) — the four requirements this phase satisfies.
- `.planning/ROADMAP.md` §"Phase 4: Evidence & Impact" — phase goal, 4 success criteria, ticket context (SENT-3-01/02/03/04/05 in scope; SENT-3-06/07/08 v2-territory, not this phase).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/app/db.py` — asyncpg pool (`acquire_pool_or_none`) from Phase 3; the graph-build queries against domain tables reuse this directly.
- `backend/app/schemas.py` — Pydantic models; extend with graph/node/edge and Blast Radius response schemas.
- `backend/app/agents/c1_verifier.py` — the `AgentFinding` + confidence output the Assurance Card renders; Phase 4 consumes this as read-only input, does not modify C1.
- `backend/app/opa_client.py` — not directly needed for graph construction, but confirms the pattern of "live Postgres + typed client" this phase should mirror for graph queries.
- Frontend: Vite/React/TS/Tailwind v4 shell + React Flow v12 (already a dependency from Phase 2's `02-04-PLAN.md`) — the evidence graph view is a new page/route inside this existing shell, not a new frontend stack.

### Established Patterns
- Deterministic-first (Bible §1.3): every phase so far keeps LLM output out of any decision path (C1's confidence, OPA's rule evaluation). Blast Radius traversal is NetworkX-only, same discipline — no LLM inventing edges or answering "what's affected."
- Additive-seed-fixture pattern (Phase 3, `002_urs_fixture.sql`, `infra/apply-seed.sh`, `infra/verify-seed.sh`): the precedent this phase's `change_affects` seed fixture follows.
- "Minimal-but-real, not stub" agent bar from Phase 3 — Phase 4's graph/traversal code should hit the same bar: real, tested, proportionate to what GRAPH-01/02/03 actually require, no premature abstraction.

### Integration Points
- New graph-build/traversal module lands under `backend/app/graph/` or a new `backend/app/evidence_graph.py` (planner's call) — reads domain tables + writes `graph_nodes`/`graph_edges` on rebuild.
- New FastAPI routes (`/api/systems/{id}/evidence-graph`, `/api/systems/{id}/evidence-graph/rebuild`, and whatever Blast Radius endpoint the planner defines) register alongside the existing `/api/health` and copilot WebSocket routes in `backend/app/main.py`.
- Frontend: new evidence-graph page/route + `AssuranceCard` component land in the existing 8-route Vite/React shell from Phase 2.

</code_context>

<specifics>
## Specific Ideas

No specific visual/UX references beyond what's already decided above (basic React Flow now, polish in Phase 6) and the Bible's own field lists for the Assurance Card and Blast Radius Graph Questions.

</specifics>

<deferred>
## Deferred Ideas

- React Flow visual polish: node-type color coding beyond basic differentiation, `animate-pulse` Trace Chain highlight animation (Bible §10.3) — Phase 6 or a later dedicated polish pass.
- Assurance Card reuse inside the full Ask GxP Copilot chat thread — Phase 6, once the chat UI itself exists.
- SENT-3-06 (Deterministic Verification Centre), SENT-3-07 (FSM engine + visualization), SENT-3-08 (ALCOA+ extended verification) — v2-territory per ROADMAP.md, not this phase.
- Auto-rebuild-on-read for the evidence graph cache — rejected in favor of explicit on-demand rebuild (D-02); could be revisited if staleness becomes a real problem later.

### Reviewed Todos (not folded)
None — no pending todos matched this phase's scope.

</deferred>

---

*Phase: 4-Evidence & Impact*
*Context gathered: 2026-08-21*
