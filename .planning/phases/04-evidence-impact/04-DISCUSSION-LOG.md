# Phase 4: Evidence & Impact - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-08-21
**Phase:** 04-evidence-impact
**Areas discussed:** Graph construction strategy, Change→downstream edge derivation, Assurance Card placement, Evidence graph API + React Flow scope

---

## Graph construction strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Live only | Build the graph from domain tables fresh on every request (Bible §10.1 pattern), ignore graph_nodes/graph_edges | |
| Cache only | Read/write only through graph_nodes/graph_edges (Bible §14.3 pattern) | |
| Both, domain tables as source of truth | graph_nodes/graph_edges are a materialized cache derived from domain tables | ✓ |

**User's choice:** Use both. Domain tables remain the source of truth; graph_nodes/graph_edges are a derived materialized cache used for traversal and visualization.

**Follow-up — cache refresh timing:**

| Option | Description | Selected |
|--------|-------------|----------|
| Build on-demand per request (auto-rebuild inside GET) | build_evidence_graph() rebuilds fresh on every GET call | |
| Explicit rebuild step, GET reads cache only | A separate POST rebuild endpoint recomputes graph_nodes/edges; GET always reads the cache and assumes freshness | ✓ |

**User's choice:** Explicit rebuild step writes to graph_nodes/edges; traversal reads only from there.

**Follow-up — rebuild trigger:**

| Option | Description | Selected |
|--------|-------------|----------|
| On-demand endpoint | POST /api/systems/{id}/evidence-graph/rebuild recomputes and overwrites; GET assumes freshness | ✓ |
| Auto-rebuild inside GET | Every GET rebuilds first, then reads back | |

**User's choice:** On-demand endpoint.

---

## Change→downstream edge derivation

| Option | Description | Selected |
|--------|-------------|----------|
| Same system_id | Blanket-associate every entity on a system with every change on that system | |
| Text-match change_actions.description against req_text/design_elements.description | Fragile deterministic string matching | |
| Add an explicit junction table now (e.g. change_affects) | Additive migration + seed fixture for the demo change record, same pattern as Phase 3's URS fixture | ✓ |

**User's choice:** Add an explicit junction table now, populated by a seed fixture. Deterministic derivation priority: explicit relationships → metadata matching → seeded demo mappings → manual graph edges. No LLM-generated authoritative relationships, ever.
**Notes:** Same-system_id was rejected as too coarse for a Critical-review graph algorithm (GRAPH-02 requires the *correct* downstream set). Text-matching was rejected as too fragile/unreliable for a deterministic, testable relationship.

---

## Assurance Card placement

| Option | Description | Selected |
|--------|-------------|----------|
| Embed inside a chat/Copilot stub | Minimal chat UI just to host the card | |
| Dedicated finding/evidence investigation route | Reusable AssuranceCard component, its own route in Phase 4; Phase 6 Copilot reuses the same component | ✓ |

**User's choice:** Dedicated finding/evidence investigation route with a reusable AssuranceCard component, reused by Phase 6's Copilot later.

---

## Evidence Graph API + React Flow scope

| Option | Description | Selected |
|--------|-------------|----------|
| Full visual polish now (color coding, animate-pulse, etc.) | Bible §10.3's full visual spec built in Phase 4 | |
| Basic API + React Flow, defer polish | Real nodes/edges/click-through now; color coding, animate-pulse Trace Chain highlight deferred to Phase 6 | ✓ |

**User's choice:** Implement API + basic React Flow (nodes, edges, click-through details). Defer animations and visual polish to Phase 6.

---

## Claude's Discretion

- Junction table (`change_affects`) exact column names/types beyond the implied shape.
- Exact REST route names/shapes for the rebuild and read endpoints.
- `AssuranceCard` component prop shape and the dedicated investigation route's URL/name.
- React Flow node/edge typing and layout algorithm specifics beyond Bible §10.3's high-level description.

## Deferred Ideas

- React Flow visual polish (node-type color coding, `animate-pulse` Trace Chain highlight) — Phase 6 or a later polish pass.
- Assurance Card reuse inside the full Ask GxP Copilot chat thread — Phase 6.
- SENT-3-06 (Deterministic Verification Centre), SENT-3-07 (FSM engine + visualization), SENT-3-08 (ALCOA+ extended verification) — v2-territory per ROADMAP.md, not this phase.
- Auto-rebuild-on-read for the evidence graph cache — rejected in favor of explicit on-demand rebuild; could be revisited later if staleness becomes a real problem.
