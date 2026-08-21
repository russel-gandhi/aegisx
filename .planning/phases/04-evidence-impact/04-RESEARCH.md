# Phase 4: Evidence & Impact - Research

**Researched:** 2026-08-21
**Domain:** Directed-graph construction from relational (Postgres) state (NetworkX), deterministic downstream-impact traversal, React Flow graph visualization, server-trusted "Assurance Card" UI contract
**Confidence:** HIGH (backend code/schema claims — all directly read this session) / MEDIUM (NetworkX and @xyflow/react API usage — official docs, not project-specific)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Graph construction strategy**
- **D-01:** Domain tables (`requirements`, `test_cases`, `risks`, `design_elements`, `changes`, `incidents`, `access_reviews`, `access_records`, `documents`, `suppliers`, etc.) remain the single source of truth. `graph_nodes`/`graph_edges` (already in schema, currently empty) are a **materialized cache** derived from domain state, not an independent data source — they never hold a fact that isn't derivable from the domain tables plus the new junction table (D-03).
- **D-02:** Rebuild is an **explicit, on-demand step** — a `POST /api/systems/{id}/evidence-graph/rebuild` (exact route TBD by planner) recomputes `graph_nodes`/`graph_edges` for that system from domain tables and overwrites. The `GET /api/systems/{id}/evidence-graph` read endpoint always reads from the cache tables and assumes freshness — it does NOT rebuild inline. — **Reversibility:** costly — swapping to auto-rebuild-on-read later means removing the explicit rebuild trigger from the frontend "Trace Chain" flow and the demo script, and re-testing staleness behavior.

**Change→downstream edge derivation**
- **D-03:** Add an explicit **additive junction table** now (e.g. `change_affects(change_id, entity_type, entity_id)`), populated by a seed fixture for the demo change record — same pattern as Phase 3's `002_urs_fixture.sql` additive-seed precedent (D-05 there). This is a deliberate, user-approved schema change for this phase, not scope creep. — **Reversibility:** one-way — once `graph_edges` traversal and any seeded demo data depend on this table shape, changing the junction table's columns needs a migration and reseeding.
- Edge derivation priority, most to least authoritative: (1) explicit FK relationships already in the schema (e.g. `requirements.test_case_id` → `REQUIREMENT --VERIFIED_BY--> TEST_CASE`), (2) the new `change_affects` junction table / other explicit metadata keys, (3) seeded demo mappings for the one seeded change record GRAPH-02 requires, (4) hand-authored `graph_edges` rows as a last resort. **No LLM-generated edges, ever** — Bible Section 1.3's deterministic-first boundary applies to graph construction exactly as it does to C1.
- Same-`system_id` blanket association (treating every entity on a system as affected by every change on that system) was explicitly rejected as too coarse for a Critical-review graph algorithm — GRAPH-02 requires the *correct* downstream set, not "everything on this system."
- Fragile text/keyword matching between `change_actions.description` and `req_text`/`design_elements.description` was explicitly rejected as too unreliable for a deterministic, testable relationship.

**Assurance Card placement**
- **D-04:** Build a reusable `AssuranceCard` component now, exposed through a **dedicated finding/evidence investigation route** in Phase 4 (not embedded in a chat UI, since the full Copilot chat doesn't exist until Phase 6). Phase 6 will reuse this same component inside the Copilot chat thread rather than building a second card.
- Card shows CLAIM / EVIDENCE / RULE / DETERMINISTIC CHECK / CONFIDENCE, sourced entirely from server-trusted data (the C1 `AgentFinding` + confidence output from Phase 3) — never LLM-generated UI, matching EVID-03 and Bible Section 11.2's field list.

**Evidence Graph API + React Flow scope**
- **D-05:** Build the `/api/systems/{id}/evidence-graph` (+ rebuild endpoint) and a **basic** React Flow rendering: real nodes, real edges, click-through to node/entity details. In scope for Phase 4.
- Visual polish — node-type color coding beyond basic differentiation, the `animate-pulse` Trace Chain highlight animation described in Bible §10.3, and any other cosmetic pass — is explicitly **deferred to Phase 6** (or a later polish pass), not built in Phase 4. Phase 4's bar is "the graph is real, traversal is correct, and it's visible in the browser," not demo-polish.

### Claude's Discretion
- Exact junction table column names/types beyond the shape implied above (`change_affects(change_id, entity_type, entity_id)`).
- Exact REST route names/shapes for the rebuild and read endpoints (`/api/systems/{id}/evidence-graph`, `/api/systems/{id}/evidence-graph/rebuild` are directional, not locked).
- Exact `AssuranceCard` component prop shape and the dedicated investigation route's URL/name.
- React Flow node/edge typing and layout algorithm specifics not covered by Bible §10.3's high-level description.

### Deferred Ideas (OUT OF SCOPE)
- React Flow visual polish: node-type color coding beyond basic differentiation, `animate-pulse` Trace Chain highlight animation (Bible §10.3) — Phase 6 or a later dedicated polish pass.
- Assurance Card reuse inside the full Ask GxP Copilot chat thread — Phase 6, once the chat UI itself exists.
- SENT-3-06 (Deterministic Verification Centre), SENT-3-07 (FSM engine + visualization), SENT-3-08 (ALCOA+ extended verification) — v2-territory per ROADMAP.md, not this phase.
- Auto-rebuild-on-read for the evidence graph cache — rejected in favor of explicit on-demand rebuild (D-02); could be revisited if staleness becomes a real problem later.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| GRAPH-01 | NetworkX evidence graph is built directly from live Postgres state | "NetworkX Graph Construction" pattern below: domain-table read → `nx.DiGraph` build → `graph_nodes`/`graph_edges` cache write, mirroring Bible §10.1's `build_evidence_graph` shape and D-01/D-02's cache-not-source-of-truth model |
| GRAPH-02 | Blast Radius traversal returns correct downstream-impact nodes (affected tests/controls/systems) for a seeded change record | "Blast Radius Traversal" pattern below: `nx.descendants()` over the cached graph, edge-type provenance from `change_affects` (D-03), and the concrete `change_affects` seed rows needed for `CR-2026-089` |
| GRAPH-03 | Evidence graph renders in-browser via React Flow from a graph API endpoint | "React Flow Integration" pattern below: `@xyflow/react` v12 (already installed, confirmed in `frontend/package.json`), API JSON → `Node[]`/`Edge[]` mapping, reusing `AgentTopologyCanvas.tsx`'s established layout conventions |
| EVID-03 | A verified finding renders CLAIM / EVIDENCE / RULE / DETERMINISTIC CHECK / CONFIDENCE, sourced from server-trusted data — never LLM-generated UI | "Assurance Card Data Contract" section below: exact field mapping from `backend/app/agents/c1_verifier.py`'s `verify_finding()` return shape (quoted verbatim) and `backend/README.md`'s "AgentFinding conventions" table |
</phase_requirements>

## Summary

Phase 4 has two independent halves that share one discipline: **never let an LLM invent a graph edge or a card field** (Bible §1.3, reaffirmed by CONTEXT.md D-03). Half one is a batch ETL job — read the domain tables Phase 2/3 already populate, plus a new `change_affects` junction table, into an in-memory `networkx.DiGraph`, then persist that graph's nodes/edges into the already-declared-but-empty `graph_nodes`/`graph_edges` cache tables (`infra/postgres/initdb/001_schema.sql` lines 212–223). Half two is read-only rendering — a `GET` endpoint serializes the cache tables to JSON, `@xyflow/react` (already an installed frontend dependency, confirmed in `frontend/package.json`) renders it, and a `find_downstream_impacts`-style traversal (`nx.descendants` over the persisted graph, rebuilt in-process from the cache rows) answers Bible §14.3's Blast Radius questions.

The Assurance Card is unrelated to the graph mechanically but shares the "server-trusted only" discipline: Phase 3's `c1_verifier.run_c1()` already produces every field the card needs (`verification_results[finding_id]` — `confidence`, `db_record_found`, `opa_corroborated`, `opa_rule_ids`, `evidence_ids`) alongside the `AgentFinding` itself (`claim`, `regulatory_citations`, `evidence_ids`, `alcoa_score`, `model_attribution`). No new backend computation is needed for the card — only a route that returns an already-computed finding + verification pair, and a frontend component that renders those exact fields with no LLM in the render path.

**Two material gaps exist between the Bible's idealized design and what Phase 3 actually shipped**, both **must** be accounted for in planning: (1) `networkx` is **not yet a dependency anywhere in this repo** — `pip show networkx` returns "not found" in `backend/.venv` and it is absent from `backend/requirements.txt` — so adding it is Phase 4's own first task, not a pre-existing given. (2) The `changes`/`change_actions` tables have **no existing foreign key to `requirements`/`design_elements`/`test_cases`** (confirmed by reading `001_schema.sql` in full) and `design_elements` has **zero seeded rows** (confirmed by reading `001_seed.sql` in full) — so the `change_affects` seed fixture for the one demo change record `CR-2026-089` must pick real, already-seeded target entities (e.g. `URS-042`, `TC-2026-042`, `DOC-2026-OM-99`) or add new `design_elements` seed rows in the same pass, or GRAPH-02's traversal has nothing real to return.

**Primary recommendation:** Build a `backend/app/graph/evidence_graph.py` module with two pure functions — `build_graph(pool, system_id) -> nx.DiGraph` (reads domain tables + `change_affects`, no writes) and `persist_graph(pool, system_id, G)` (overwrites that system's `graph_nodes`/`graph_edges` rows) — wired to a `POST /api/systems/{id}/evidence-graph/rebuild` route; a separate `load_graph(pool, system_id) -> nx.DiGraph` reconstructs the in-memory graph from the cache tables for `GET /api/systems/{id}/evidence-graph` (serialize to JSON) and a `GET /api/systems/{id}/blast-radius/{node_id}` route (run `nx.descendants` + edge-type bucketing). Frontend: one new `/evidence-graph` (or similar) route rendering `@xyflow/react` from the JSON, plus a `AssuranceCard.tsx` component and its own dedicated route consuming a new `GET /api/findings/{finding_id}` (or equivalent) that returns the `AgentFinding` + `verification_results` entry pair.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Evidence graph construction (domain tables → `nx.DiGraph` → cache tables) | API / Backend | Database / Storage | Pure Python/SQL ETL; must stay deterministic per Bible §1.3 — no LLM, no browser logic |
| Graph cache persistence (`graph_nodes`/`graph_edges`) | Database / Storage | API / Backend | Materialized cache written only by the rebuild endpoint (D-02); domain tables remain source of truth (D-01) |
| Blast Radius traversal (`nx.descendants`/reachability) | API / Backend | — | NetworkX reachability is CPU-bound in-process Python; must never move to the browser tier (deterministic-first, Bible §1.3) |
| Evidence graph JSON serialization | API / Backend | — | Read endpoint only reads cache tables (D-02) — no rebuild-on-read, no graph computation in the request path |
| Evidence graph rendering (`@xyflow/react`) | Browser / Client | — | Pure presentation of already-computed, already-verified server data; zero graph logic in the browser |
| Blast Radius UI (impact-radius display) | Browser / Client | API / Backend (data source) | Renders the backend traversal's JSON result; the browser performs no traversal itself |
| Assurance Card rendering | Browser / Client | API / Backend (data source) | Renders `AgentFinding` + `verification_results` fields verbatim — CLAUDE.md Rule 13 / Bible §1.3 forbid any client-side reinterpretation of confidence or claim text |
| Assurance Card data assembly (finding + verification lookup) | API / Backend | — | A new read endpoint joins Phase 3's already-computed `AgentFinding`/`verification_results` — no new verification logic, per D-04 |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `networkx` | 3.6.1 (verified current on PyPI via `pip index versions`) [VERIFIED: pip index versions networkx, run this session] | Directed graph construction (`nx.DiGraph`), downstream reachability (`nx.descendants`) | Bible §10.1 names this library explicitly (`import networkx as nx`); it is the de facto standard pure-Python graph library and matches the deterministic-first constraint (no LLM, no external service) |
| `@xyflow/react` | ^12.11.3 (already installed — confirmed by reading `frontend/package.json` this session) [VERIFIED: frontend/package.json, read this session] | React Flow graph rendering | Already a Phase 2 dependency (`frontend/src/components/AgentTopologyCanvas.tsx` already imports it for the agent-topology page); Phase 4 reuses the same package for the evidence graph, not a new dependency |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `asyncpg` | 0.31.0 (already pinned in `backend/requirements.txt`, read this session) [VERIFIED: backend/requirements.txt] | Reads domain tables + writes cache tables | Already the established pattern (`backend/app/db.py`, `backend/app/agents/c1_verifier.py`) — graph-build queries reuse `acquire_pool_or_none()` exactly as C1 does |
| `pydantic` | 2.13.4 (already pinned) [VERIFIED: backend/requirements.txt] | Response schemas for the new graph/blast-radius/finding routes | Matches `backend/app/schemas.py`'s existing convention; extend that module, don't create a parallel schema style |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `networkx` | Hand-rolled adjacency-list BFS/DFS in plain Python | Rejected — Bible §10.1 names NetworkX explicitly, and hand-rolling reachability/traversal for a Critical-review ticket (SENT-3-03) reintroduces exactly the kind of "silently wrong edge case" risk NetworkX's tested `descendants`/`dfs_preorder_nodes` already close |
| `@xyflow/react` | `reactflow` (the pre-v12 package name) or the Bible's literal `react-flow-renderer` | Rejected — `react-flow-renderer` was renamed/archived years ago; the codebase already installed and uses `@xyflow/react` v12 (the current successor package) in Phase 2's `AgentTopologyCanvas.tsx`. Using a different package name would fork the frontend's graph-rendering approach for no reason. |
| `nx.descendants(G, source)` | `nx.dfs_preorder_nodes(G, source)` | Both return the reachable-node set; `descendants` is documented for DAGs and is the more direct, purpose-built API for "what's downstream of this node" (Blast Radius's exact question). `dfs_preorder_nodes` works on graphs with cycles too and exposes traversal order, which Blast Radius does not need. Recommend `descendants` for the primary query, but note NetworkX's own docs describe it as DAG-oriented — if a future cyclic edge is ever introduced (unlikely given the schema's tree-like FK shape), `dfs_preorder_nodes` degrades more gracefully. [CITED: networkx.org/documentation/stable — descendants and dfs_preorder_nodes reference pages] |

**Installation:**
```bash
# Backend (add to backend/requirements.txt, then reinstall in backend/.venv)
pip install networkx==3.6.1

# Frontend: no new install — @xyflow/react is already a dependency
```

**Version verification:** `networkx` version confirmed via `pip index versions networkx` (this session, output: `networkx (3.6.1) Available versions: 3.6.1, 3.6, 3.5, ...`). `@xyflow/react` version confirmed by reading `frontend/package.json` directly (`"@xyflow/react": "^12.11.3"`), not by registry lookup, since it is already installed and in use.

## Package Legitimacy Audit

| Package | Registry | Age | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| `networkx` | PyPI | Published 2025-12-08 (latest release; project itself dates to 2005) | Unknown — legitimacy-check tool returned `weeklyDownloads: null` from the registry stats endpoint, not a real low-download signal | https://networkx.org/ | `SUS` (reason: `unknown-downloads`) | **Flagged — but assessed as a false positive.** `networkx` is one of the most widely used scientific-Python libraries (NumFOCUS-sponsored, in every major Linux distro's package repos, named explicitly by Bible §10.1). The `SUS` verdict here is an artifact of the automated download-count lookup returning no data, not a suspicious-package signal (no missing repo, no missing description, no postinstall script). Per protocol, the planner must still add a `checkpoint:human-verify` task before the `pip install networkx==3.6.1` step — treat this as a formality, not a real risk signal. |

**Packages removed due to `[SLOP]` verdict:** none.
**Packages flagged as suspicious `[SUS]`:** `networkx` — see disposition above; planner must add one `checkpoint:human-verify` task ahead of the `pip install` step per protocol, even though the underlying signal (unknown download count) does not indicate an actual legitimacy problem.

*`@xyflow/react` was not run through the legitimacy gate — it is not a new package being installed this phase; it is already present in `frontend/package.json` and already in production use in `frontend/src/components/AgentTopologyCanvas.tsx`.*

## Architecture Patterns

### System Architecture Diagram

```
                         ┌─────────────────────────────┐
                         │  Postgres (domain tables)    │
                         │  requirements, test_cases,    │
                         │  risks, design_elements,      │
                         │  changes, change_actions,     │
                         │  incidents, access_reviews,   │
                         │  access_records, documents,    │
                         │  suppliers, change_affects*    │
                         └───────────────┬───────────────┘
                                         │ read (asyncpg, $1 placeholders)
                                         ▼
                         ┌─────────────────────────────┐
POST /api/systems/{id}/  │  build_graph(pool, system_id) │
evidence-graph/rebuild ─▶│  → nx.DiGraph (in memory)     │
                         │  edges: FK-derived (prio 1),  │
                         │  change_affects-derived (2)   │
                         └───────────────┬───────────────┘
                                         │ persist_graph() — overwrite
                                         ▼
                         ┌─────────────────────────────┐
                         │  graph_nodes / graph_edges    │
                         │  (materialized cache tables)  │
                         └───────────────┬───────────────┘
                                         │ read-only, no rebuild
              ┌──────────────────────────┼──────────────────────────┐
              ▼                                                     ▼
┌───────────────────────────┐                      ┌───────────────────────────┐
│ GET /api/systems/{id}/     │                      │ GET /api/systems/{id}/     │
│ evidence-graph              │                      │ blast-radius/{node_id}      │
│ → load_graph() → JSON       │                      │ → load_graph() →            │
│   {nodes:[...], edges:[...]}│                      │   nx.descendants(G, node)   │
└──────────────┬──────────────┘                      │   bucketed by node_type     │
               │ fetch                                └──────────────┬──────────────┘
               ▼                                                     │ fetch
┌───────────────────────────┐                                        ▼
│ Browser: EvidenceGraph page │                      ┌───────────────────────────┐
│ @xyflow/react renders       │◀── click node ───────│ Browser: Blast Radius panel │
│ nodes/edges                 │      (Trace Chain)    │ "Direct N / Indirect N /   │
└─────────────────────────────┘                      │  Affected controls N"       │
                                                       └───────────────────────────┘

  Separately (no shared code path with the graph above):

┌───────────────────────────┐        ┌───────────────────────────┐        ┌───────────────────────────┐
│ Phase 3: c1_verifier.py     │        │ GET /api/findings/{id}      │        │ Browser: AssuranceCard      │
│ run_c1() → verification_    │───────▶│ (new, Phase 4) joins         │───────▶│ component + dedicated       │
│ results[finding_id] + the   │        │ AgentFinding + verification_ │        │ investigation route          │
│ AgentFinding it verified    │        │ results[finding_id]          │        │ renders CLAIM/EVIDENCE/RULE/│
│ (already computed, Phase 3) │        │ — no new computation          │        │ CHECK/CONFIDENCE verbatim    │
└───────────────────────────┘        └───────────────────────────┘        └───────────────────────────┘

* change_affects(change_id, entity_type, entity_id) — new, additive junction table (D-03), seeded for CR-2026-089.
```

### Recommended Project Structure
```
backend/app/
├── graph/
│   ├── state.py                # existing (LangGraph state) — untouched
│   └── evidence_graph.py       # NEW: build_graph(), persist_graph(), load_graph(),
│                                #      find_downstream_impacts()/blast_radius()
├── routes/                     # NEW package (main.py currently registers routes inline —
│   ├── systems.py              #   planner's call whether to keep inline in main.py or split;
│   └── findings.py             #   either satisfies GRAPH-03/EVID-03, this is a style choice)
└── schemas.py                  # EXTEND: GraphNode, GraphEdge, EvidenceGraphResponse,
                                 #         BlastRadiusResponse, AssuranceCardResponse

infra/postgres/
├── initdb/001_schema.sql       # ADD: CREATE TABLE change_affects (new migration file,
│                                #      not an edit to this closed Phase-2 file — see Pitfall 1)
└── seed/
    └── 003_change_affects_fixture.sql   # NEW, additive — same pattern as 002_urs_fixture.sql

frontend/src/
├── pages/
│   ├── EvidenceGraph.tsx       # NEW — GRAPH-03: renders GET .../evidence-graph via @xyflow/react
│   └── FindingDetail.tsx       # NEW — EVID-03: dedicated Assurance Card investigation route (D-04)
├── components/
│   ├── AgentTopologyCanvas.tsx # existing — reference pattern, do not modify
│   ├── EvidenceGraphCanvas.tsx # NEW — mirrors AgentTopologyCanvas's ReactFlow/Background/Controls shape
│   ├── BlastRadiusPanel.tsx    # NEW — direct/indirect/controls counts, wired to blast-radius endpoint
│   └── AssuranceCard.tsx       # NEW — reusable component (D-04), consumed here and reused in Phase 6
└── lib/
    ├── ws.ts                   # existing — reference pattern for env-var base URL resolution
    └── api.ts                  # NEW — fetch() wrapper following ws.ts's VITE_*-env-var convention
```

### Pattern 1: Domain-table-to-graph ETL (GRAPH-01)
**What:** A pure function reads every relevant domain table for one `system_id`, adds one `graph_nodes`-shaped node per row, and adds edges per the D-03 priority order (explicit FK first, `change_affects` junction second). No LLM, no request-time computation — this only runs on an explicit rebuild call.
**When to use:** `POST /api/systems/{id}/evidence-graph/rebuild`, and nowhere else (D-02 — the read endpoint never triggers this).
**Example:**
```python
# Pattern synthesized from Bible §10.1's build_evidence_graph() sketch
# (AegisX-AI-Project-Bible-v6.md lines 1347-1356, read this session) and
# this codebase's established acquire_pool_or_none() + asyncpg $1
# convention (backend/app/agents/c1_verifier.py, backend/app/db.py).
import networkx as nx

async def build_graph(pool, system_id: str) -> nx.DiGraph:
    G = nx.DiGraph()

    requirements = await pool.fetch(
        "SELECT id, test_case_id FROM requirements WHERE system_id = $1", system_id
    )
    for req in requirements:
        G.add_node(req["id"], node_type="REQUIREMENT")
        if req["test_case_id"]:
            G.add_edge(req["id"], req["test_case_id"], relation_type="VERIFIED_BY")

    test_cases = await pool.fetch(
        "SELECT id FROM test_cases WHERE system_id = $1", system_id
    )
    for tc in test_cases:
        G.add_node(tc["id"], node_type="TEST_CASE")

    changes = await pool.fetch(
        "SELECT id FROM changes WHERE system_id = $1", system_id
    )
    for chg in changes:
        G.add_node(chg["id"], node_type="CHANGE")

    change_actions = await pool.fetch(
        "SELECT id, change_id FROM change_actions WHERE change_id = ANY($1::varchar[])",
        [c["id"] for c in changes],
    )
    for action in change_actions:
        G.add_node(action["id"], node_type="CHANGE_ACTION")
        G.add_edge(action["change_id"], action["id"], relation_type="HAS_ACTION")

    # D-03 priority 2: the new change_affects junction table
    affects = await pool.fetch(
        "SELECT change_id, entity_type, entity_id FROM change_affects "
        "WHERE change_id = ANY($1::varchar[])",
        [c["id"] for c in changes],
    )
    for row in affects:
        G.add_edge(row["change_id"], row["entity_id"], relation_type="AFFECTS")

    return G
```

### Pattern 2: Cache-table persistence (D-01, D-02)
**What:** `graph_nodes`/`graph_edges` are overwritten (delete-then-insert for that `system_id`, in a transaction) from the in-memory `nx.DiGraph` built by Pattern 1. The read endpoint (`GET .../evidence-graph`) never calls Pattern 1 — it only ever reads these two tables.
**When to use:** Immediately after `build_graph()` inside the rebuild route handler.
**Example:**
```python
# infra/postgres/initdb/001_schema.sql (read this session, lines 212-223):
#   CREATE TABLE graph_nodes (node_id VARCHAR(100) PRIMARY KEY,
#     system_id VARCHAR(50) REFERENCES gxp_systems(id),
#     node_type VARCHAR(50), properties JSONB);
#   CREATE TABLE graph_edges (source_id VARCHAR(100) REFERENCES graph_nodes(node_id),
#     target_id VARCHAR(100) REFERENCES graph_nodes(node_id), relation_type VARCHAR(50));
async def persist_graph(pool, system_id: str, G) -> None:
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                "DELETE FROM graph_edges WHERE source_id IN "
                "(SELECT node_id FROM graph_nodes WHERE system_id = $1)",
                system_id,
            )
            await conn.execute("DELETE FROM graph_nodes WHERE system_id = $1", system_id)
            for node_id, attrs in G.nodes(data=True):
                await conn.execute(
                    "INSERT INTO graph_nodes (node_id, system_id, node_type, properties) "
                    "VALUES ($1, $2, $3, $4)",
                    node_id, system_id, attrs.get("node_type"), {},
                )
            for source, target, attrs in G.edges(data=True):
                await conn.execute(
                    "INSERT INTO graph_edges (source_id, target_id, relation_type) "
                    "VALUES ($1, $2, $3)",
                    source, target, attrs.get("relation_type"),
                )
```

### Pattern 3: Blast Radius traversal (GRAPH-02)
**What:** Reconstruct an `nx.DiGraph` from the persisted `graph_nodes`/`graph_edges` rows, then answer Bible §14.3's Graph Questions via `nx.descendants()` bucketed by the target nodes' `node_type`.
**When to use:** `GET /api/systems/{id}/blast-radius/{node_id}` (or equivalent — route name is planner's discretion per D-05).
**Example:**
```python
# Bible §14.3 (AegisX-AI-Project-Bible-v6.md lines 1720-1732, read this
# session) "Graph Questions": directly affected, indirectly affected,
# affected requirements/tests/risks/changes/controls, potential GxP
# impact, highest-impact downstream dependency.
def blast_radius(G: nx.DiGraph, source_node: str) -> dict:
    direct = set(G.successors(source_node))
    all_downstream = nx.descendants(G, source_node)
    indirect = all_downstream - direct

    by_type: dict[str, list[str]] = {}
    for node_id in all_downstream:
        node_type = G.nodes[node_id].get("node_type", "UNKNOWN")
        by_type.setdefault(node_type, []).append(node_id)

    return {
        "direct_dependencies": sorted(direct),
        "indirect_dependencies": sorted(indirect),
        "affected_requirements": by_type.get("REQUIREMENT", []),
        "affected_tests": by_type.get("TEST_CASE", []),
        "affected_risks": by_type.get("RISK", []),
        "affected_changes": by_type.get("CHANGE", []),
        "affected_controls": by_type.get("ACCESS_REVIEW", []) + by_type.get("ACCESS_RECORD", []),
    }
```
**Edge case (must be tested per SENT-3-03's Critical-review bar):** `nx.descendants()` raises `NetworkXError` if `source_node` is not in `G`. The route handler must catch this and return an empty/404 result, not a 500 — a change record with zero build_graph()-derived edges (e.g. a change with no `change_affects` rows yet) is a valid, expected state, not a server error. [CITED: networkx.org/documentation/stable/reference/algorithms/generated/networkx.algorithms.dag.descendants.html]

### Pattern 4: React Flow rendering from a JSON graph endpoint (GRAPH-03)
**What:** Fetch `GET /api/systems/{id}/evidence-graph`, map its `{nodes, edges}` JSON to `@xyflow/react`'s `Node[]`/`Edge[]` shape, render with `<ReactFlow>`. Mirrors the exact pattern `AgentTopologyCanvas.tsx` already establishes (read this session), just with server-fetched data instead of a hardcoded topology.
**When to use:** The new evidence-graph page/route.
**Example:**
```tsx
// Pattern mirrors frontend/src/components/AgentTopologyCanvas.tsx exactly
// (read this session) — same ReactFlow/Background/Controls shape, same
// fixed-height wrapper div (React Flow renders nothing inside a
// zero-height parent, per that file's own comment).
import { ReactFlow, Background, Controls, type Node, type Edge } from '@xyflow/react'

interface EvidenceGraphResponse {
  nodes: { node_id: string; node_type: string }[]
  edges: { source_id: string; target_id: string; relation_type: string }[]
}

function toFlowElements(data: EvidenceGraphResponse): { nodes: Node[]; edges: Edge[] } {
  // Basic layout only per D-05 — no force-directed/dagre layout algorithm
  // this phase; a simple row-per-type or index-based grid is sufficient.
  const nodes: Node[] = data.nodes.map((n, i) => ({
    id: n.node_id,
    position: { x: (i % 6) * 180, y: Math.floor(i / 6) * 100 },
    data: { label: `${n.node_type}\n${n.node_id}` },
  }))
  const edges: Edge[] = data.edges.map((e) => ({
    id: `e-${e.source_id}-${e.target_id}`,
    source: e.source_id,
    target: e.target_id,
    label: e.relation_type,
  }))
  return { nodes, edges }
}
```
[CITED: reactflow.dev/api-reference/hooks/use-nodes-state, reactflow.dev/examples/nodes/custom-node — general v12 API shape, not project-specific]

### Anti-Patterns to Avoid
- **Rebuilding the graph inside the `GET` read endpoint:** Explicitly rejected by D-02. The read endpoint must only ever `SELECT` from `graph_nodes`/`graph_edges` — recomputing on every read reintroduces the exact "auto-rebuild-on-read" design CONTEXT.md's `<deferred>` section says was rejected.
- **Same-`system_id` blanket association as an edge-derivation shortcut:** Explicitly rejected by D-03 (CONTEXT.md). Every edge must come from an explicit FK or the `change_affects` junction table — never "these two rows share a `system_id`, so they're related."
- **Letting an LLM narrate or invent a Blast Radius edge:** Bible §14.3 states plainly: "LLMs may explain or summarize impact, but should not invent graph relationships." The traversal result (the node-id lists) must be computed by `nx.descendants`/`dfs_preorder_nodes` only; an LLM may only be handed the *already-computed* result to phrase as a sentence, if the UI wants that at all (D-05's scope does not require it this phase).
- **Reusing `graph_edges.relation_type` as a free-text field:** The schema declares it `VARCHAR(50)` with no `CHECK` constraint (confirmed reading `001_schema.sql`), so nothing stops an inconsistent value being written. Define a fixed Python-side enum/allowlist of relation-type strings (mirroring `c1_verifier.py`'s `RULE_EVIDENCE_TABLES` allowlist pattern) so `build_graph()` never writes an ad hoc string.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Downstream reachability from a change record | A hand-rolled recursive SQL `WITH RECURSIVE` CTE or a manual BFS/DFS in Python | `nx.descendants(G, source)` / `nx.dfs_preorder_nodes(G, source)` | NetworkX's traversal functions are tested against cycles, disconnected components, and missing nodes — exactly the edge cases SENT-3-03's Critical-review bar (unit + negative + edge-case + integration) requires. Bible §10.1 already names this library; reinventing it duplicates well-tested code for no benefit. |
| React Flow layout (node positions) | A custom force-directed layout algorithm | A simple deterministic grid/row layout (Pattern 4 above) for this phase; `dagre`/`elkjs` auto-layout only if Phase 6's polish pass needs it | D-05 explicitly scopes Phase 4 to "basic" rendering — real nodes/edges/click-through — deferring visual polish (including any layout algorithm sophistication) to Phase 6 |
| Polymorphic entity references (`change_affects.entity_id` pointing at one of several different tables) | A single `FOREIGN KEY` constraint spanning multiple target tables (not supported by Postgres) or a trigger-based integrity enforcement layer | Application-level validation only (the allowlist pattern `c1_verifier.py`'s `RULE_EVIDENCE_TABLES` already establishes) — `entity_type` names which table `entity_id` must resolve against, checked in Python before insert, not enforced by the database schema | Matches this codebase's own established convention (Phase 2/3's schema deliberately has "no check constraints" per `001_schema.sql`'s own header comment) and avoids inventing a new integrity-enforcement mechanism not used anywhere else in the project |

**Key insight:** Every "don't hand-roll" item here is really the same discipline restated: this phase adds no new *kind* of correctness mechanism to the codebase. NetworkX for traversal, Python-side allowlists for referential integrity, `asyncpg` `$1` placeholders for SQL — all three are already this codebase's established patterns from Phase 2/3, not new ones invented for Phase 4.

## Common Pitfalls

### Pitfall 1: Editing the closed `001_schema.sql` instead of adding a migration
**What goes wrong:** `infra/postgres/initdb/001_schema.sql`'s own header comment (read this session) states: *"Editing this file requires `docker compose down -v --remove-orphans` followed by `docker compose up -d --wait` to take effect"* and *"Add nothing the Bible does not declare... (CLAUDE.md Rule 7 — no scope expansion)."* This file is Phase 2's closed deliverable, transcribed verbatim from the Bible. `change_affects` is a new, Bible-undeclared table.
**Why it happens:** It looks like the "natural" place to add a new table, since it's where every other table lives.
**How to avoid:** Add a new file (e.g. `infra/postgres/initdb/002_change_affects.sql` or a clearly-named migration under a new `infra/postgres/migrations/` directory — planner's call) that only contains `CREATE TABLE change_affects (...)`, following the same bind-mount-triggers-on-fresh-volume mechanism `001_schema.sql` already uses. Document why this table exists and that it is additive, Phase-4-specific schema (same rationale style as `002_urs_fixture.sql`'s own header comment).
**Warning signs:** A diff touching `001_schema.sql` in a Phase 4 plan/PR.

### Pitfall 2: Assuming `networkx` is already installed
**What goes wrong:** `pip show networkx` in `backend/.venv` returns `WARNING: Package(s) not found: networkx` (confirmed this session) and it does not appear in `backend/requirements.txt` (confirmed this session, 10-line file, no `networkx` entry). A plan that imports `networkx` without an explicit install step will fail at import time.
**Why it happens:** Bible §10.1 already shows `import networkx as nx` code, which reads like it's assumed available.
**How to avoid:** First task of the phase's graph-construction plan must add `networkx==3.6.1` to `backend/requirements.txt` and run `pip install -r backend/requirements.txt` (or equivalent) before any graph module is imported. Gate this `pip install` behind a `checkpoint:human-verify` per the Package Legitimacy Audit above (SUS verdict due to unknown-downloads signal, assessed as a false positive but the protocol still requires the checkpoint).

### Pitfall 3: `change_affects` seed fixture with no real target entities
**What goes wrong:** `design_elements` has zero seeded rows (confirmed by reading `001_seed.sql` in full this session — no `INSERT INTO design_elements` statement anywhere in the file). If the `change_affects` seed fixture for `CR-2026-089` targets a `design_elements` row that doesn't exist, GRAPH-02's traversal returns nothing meaningful for that entity type, and if a naive implementation adds a FK from `change_affects.entity_id` to a specific table, the insert fails outright.
**Why it happens:** Bible §14.3's example relation-type list includes `CHANGE --AFFECTS--> DESIGN_ELEMENT`, which reads as if design elements are already populated.
**How to avoid:** Either (a) point the `change_affects` seed rows at already-real, already-seeded entities from other tables (`URS-042` [requirement], `TC-2026-042` [test case], `DOC-2026-OM-99` [document] — all confirmed present in `001_seed.sql`), or (b) add one or more `design_elements` seed rows in the same additive-fixture file, following `002_urs_fixture.sql`'s established pattern (idempotent `ON CONFLICT (id) DO NOTHING`, routed to SENT-7-05 for Bible reconciliation). Either choice is a planner decision — CONTEXT.md D-03 only fixes the junction table's shape, not its seed content.

### Pitfall 4: `graph_nodes.node_id` primary-key collision across entity types
**What goes wrong:** `graph_nodes.node_id` is the table's sole `PRIMARY KEY` (`VARCHAR(100)`, confirmed reading `001_schema.sql`). Nothing in the current schema guarantees a `requirements.id` value can never collide with a `test_cases.id` or `risks.id` value across different domain tables — they are independent `VARCHAR(50) PRIMARY KEY` columns in separate tables. The current seed data happens to use disjoint naming prefixes (`URS-*`, `TC-*`, `RSK-*`, `DOC-*`, `CR-*`, `CA-*`, `AR-*`, `ACC-*`, `SUP-*`, `PE-*`, `INC-*` — confirmed reading `001_seed.sql`), but nothing in the schema enforces that discipline going forward.
**Why it happens:** It's tempting to insert each entity's own primary key directly as `graph_nodes.node_id` since it "just works" against today's seed data.
**How to avoid:** Either document the disjoint-prefix convention as a hard invariant new seed data must respect (cheapest, matches current reality), or prefix `node_id` with the node type at insert time (e.g. `f"{node_type}:{entity_id}"`, e.g. `"REQUIREMENT:URS-042"`) to make collision structurally impossible. Given the existing convention already holds and this is `[ASSUMED]` future risk rather than a proven bug, either choice is defensible — flag as an Open Question for the planner to decide explicitly rather than silently picking one.
**Warning signs:** Two different domain tables sharing an `id` value (not observed in current seed data, but not schema-prevented either).

### Pitfall 5: `ACCESS_REVIEW --CONTROLS--> ACCESS_RECORD` has no derivable edge in the current schema
**What goes wrong:** Bible §14.3's example relationship-type list includes `ACCESS_REVIEW --CONTROLS--> ACCESS_RECORD`, but `access_reviews` and `access_records` (confirmed reading `001_schema.sql` in full) share **no foreign key to each other** — both independently reference `gxp_systems(id)` via their own `system_id` column and nothing else. Per D-03, same-`system_id` association was explicitly rejected as too coarse.
**Why it happens:** The relationship reads as obviously true in the Bible's narrative example (§14.3's ASCII diagram: "Access Review Overdue → Privileged Account"), but no column in the actual DDL expresses it.
**How to avoid:** Either scope this relationship type out of GRAPH-01/02's v1 edge set entirely (document it as a known Bible/schema gap, routed to SENT-7-05 like every other documented deviation this project has recorded) or add it to the same `change_affects`-style junction-table treatment (a new, explicitly-seeded linking table) if a demo scenario actually needs it. GRAPH-02's own bar — "answers Section 14.3 correctly for a **seeded change record**" — does not require this specific relationship type to be built, since the demo change record (`CR-2026-089`) does not involve access reviews.

## Code Examples

### Fetching a single system's domain rows for graph construction
```python
# Mirrors backend/app/agents/a2_compliance.py's established asyncpg $1
# placeholder convention (read this session) — never an f-string built
# from system_id, which is user-facing input (ASVS V5).
rows = await pool.fetch(
    "SELECT id, test_case_id FROM requirements WHERE system_id = $1", system_id
)
```

### Loading the persisted cache graph back into memory (for the read/blast-radius endpoints)
```python
async def load_graph(pool, system_id: str) -> nx.DiGraph:
    G = nx.DiGraph()
    node_rows = await pool.fetch(
        "SELECT node_id, node_type FROM graph_nodes WHERE system_id = $1", system_id
    )
    for row in node_rows:
        G.add_node(row["node_id"], node_type=row["node_type"])

    edge_rows = await pool.fetch(
        "SELECT ge.source_id, ge.target_id, ge.relation_type FROM graph_edges ge "
        "JOIN graph_nodes gn ON gn.node_id = ge.source_id WHERE gn.system_id = $1",
        system_id,
    )
    for row in edge_rows:
        G.add_edge(row["source_id"], row["target_id"], relation_type=row["relation_type"])

    return G
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| `react-flow-renderer` (Bible §10.3's literal package name) | `@xyflow/react` | The `react-flow` project was renamed/relaunched as `@xyflow/react` (v11+) some time before this project's Phase 2 dependency was pinned to `^12.11.3` | The Bible's literal import name is stale; this codebase already made the correct substitution in Phase 2 (`frontend/src/components/AgentTopologyCanvas.tsx`) — Phase 4 continues using the same, already-installed package, no action needed beyond following the existing pattern |

**Deprecated/outdated:**
- Bible §10.1's `find_downstream_impacts()` uses `nx.dfs_preorder_nodes` — still valid NetworkX API (3.6.1), not deprecated, but `nx.descendants()` is the more purpose-fit function for a pure "what's downstream" query (see Alternatives Considered above); either is acceptable, `descendants` is the research recommendation.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `nx.descendants()` is the better-fit primary Blast Radius API vs. Bible §10.1's literal `dfs_preorder_nodes()` | Alternatives Considered, Pattern 3 | Low — both return the correct reachable-node set for the schema's tree-like FK shape (no cycles observed in current domain tables); switching between them is a one-line change if testing reveals a preference |
| A2 | `graph_nodes.node_id` should be the entity's own domain-table primary key (not type-prefixed) unless the planner chooses otherwise | Pitfall 4 | Medium — if two different domain tables' seed/demo data ever share an `id` string, the `graph_nodes` cache silently loses a node (last INSERT wins on a PK conflict, or the insert fails) — flagged explicitly as an Open Question below rather than decided here |
| A3 | The `change_affects` seed fixture should target `URS-042`/`TC-2026-042`/`DOC-2026-OM-99` (existing seeded entities) rather than adding new `design_elements` rows | Pitfall 3 | Low — either choice satisfies GRAPH-02's "correct downstream set for the seeded change record" bar; this is a content choice with no architectural consequence, left to the planner |
| A4 | `ACCESS_REVIEW --CONTROLS--> ACCESS_RECORD` and similarly under-specified Bible §14.3 relationship types can be scoped out of Phase 4's v1 edge set without violating GRAPH-02 | Pitfall 5 | Low — GRAPH-02's actual acceptance bar only requires correctness "for a seeded change record," which does not exercise this relationship type; if the planner decides otherwise, a new junction table (mirroring `change_affects`) would need to be added |

## Open Questions

1. **Should `graph_nodes.node_id` be type-prefixed to guarantee cross-table PK uniqueness?**
   - What we know: Current seed data uses disjoint ID prefixes per domain table (confirmed), so no collision exists today.
   - What's unclear: Whether that discipline is guaranteed to hold for all future seed/demo data, or whether the planner wants defensive type-prefixing now.
   - Recommendation: Decide explicitly in planning (Pitfall 4); either is defensible, but it should be a stated decision, not an implicit one, since `graph_nodes`'s `PRIMARY KEY` constraint means a silent collision is a silent data-loss bug, not a loud error.

2. **Exact `change_affects` seed content for `CR-2026-089`.**
   - What we know: The junction table's shape is locked (D-03: `change_affects(change_id, entity_type, entity_id)`); the change record itself (`CR-2026-089`, "Database migration", CLOSED, with one OPEN `change_actions` row) is already seeded.
   - What's unclear: Which specific entities the demo should show as downstream-affected — a migration plausibly touches requirements, test cases, or design elements, but nothing in the current seed narrative names a specific one.
   - Recommendation: Planner picks 2-3 concrete target rows (mixing at least one already-seeded entity and, if design-element coverage is wanted, one newly-seeded `design_elements` row) so the Blast Radius demo shows a non-trivial multi-type downstream set (Pitfall 3).

3. **Route naming for the new backend endpoints beyond the two the Bible/CONTEXT.md name explicitly.**
   - What we know: `/api/systems/{id}/evidence-graph` (Bible §12, existing API table) and `/api/systems/{id}/evidence-graph/rebuild` (CONTEXT.md D-02, directional) are anchored. A Blast Radius endpoint and a finding-detail (Assurance Card data) endpoint are needed but have no Bible-literal name — Bible §12's table has no Blast Radius or per-finding row at all.
   - What's unclear: Exact path/verb for Blast Radius (`GET /api/systems/{id}/blast-radius/{node_id}` used in this research's examples is a reasonable guess, not a locked contract) and for the Assurance Card data source (`GET /api/findings/{finding_id}` used above, same caveat).
   - Recommendation: CONTEXT.md already delegates this to "Claude's Discretion" — the planner should pick and document these two route shapes explicitly in PLAN.md, following Bible §12's existing REST conventions (`/api/{resource}/{id}/{sub-resource}`).

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Postgres (local, via docker-compose) | Graph build/read, Blast Radius, Assurance Card data source | Established (Phase 1/2/3 dependency; not re-verified live this session, but `backend/app/db.py`'s `acquire_pool_or_none()` pattern already handles unreachable-DB degradation) | 16.15 (per `infra/README.md`, Phase 1) | None needed — same degrade-don't-raise pattern C1/A2 already use; a rebuild call with no DB simply fails the request, an acceptable failure mode for an explicit admin-triggered action |
| `networkx` | Graph construction (GRAPH-01), Blast Radius traversal (GRAPH-02) | **Not installed** — `pip show networkx` returns not-found in `backend/.venv` this session | 3.6.1 (latest, confirmed via `pip index versions`) | None — must be installed; no fallback library exists in this codebase for graph traversal |
| `@xyflow/react` | Evidence graph rendering (GRAPH-03), Blast Radius UI | Installed — confirmed in `frontend/package.json` | ^12.11.3 | None needed |

**Missing dependencies with no fallback:**
- `networkx` — must be added to `backend/requirements.txt` and installed before any Phase 4 backend graph code can run (Pitfall 2).

**Missing dependencies with fallback:**
- None.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework (backend) | pytest 9.1.1, config at `backend/pytest.ini` [VERIFIED: backend/requirements.txt, backend/pytest.ini existence confirmed this session] |
| Framework (frontend) | vitest 4.1.11, config in `frontend/vite.config.ts` (no separate `vitest.config.*` file exists — confirmed this session) [VERIFIED: frontend/package.json, file existence check this session] |
| Quick run command (backend) | `cd backend && .venv/Scripts/python -m pytest tests/test_evidence_graph.py -q` (new test module, planner names it) |
| Quick run command (frontend) | `cd frontend && npm run test` (runs `vitest run`, per `package.json`'s `"test"` script) |
| Full suite command (backend) | `cd backend && .venv/Scripts/python -m pytest -q` (requires Postgres + OPA up + seed applied, per `backend/README.md`'s existing convention for `test_hero_loop.py`) |
| Full suite command (frontend) | `cd frontend && npm run test` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| GRAPH-01 | `build_graph()`/`persist_graph()` produce nodes/edges matching live seeded Postgres rows | unit + integration (real DB, per this codebase's established convention — no DB mocking anywhere in Phase 3's test suite) | `pytest tests/test_evidence_graph.py -k build_graph -q` | ❌ Wave 0 — new file |
| GRAPH-02 | `blast_radius()`/`find_downstream_impacts()` returns the correct downstream set for `CR-2026-089`, written directly from Bible §14.3's Graph Questions (per Build-Map SENT-3-03's own contract: "test cases written directly from those questions") | unit + negative (missing node) + edge-case (empty graph, node with zero edges) + integration (real seeded DB) — Critical-review bar per SENT-3-03 | `pytest tests/test_evidence_graph.py -k blast_radius -q` | ❌ Wave 0 — new file |
| GRAPH-03 | `GET .../evidence-graph` returns valid JSON; the React page renders a `<ReactFlow>` element from it | backend: integration (route + TestClient); frontend: component render test (vitest + `@testing-library/react`, already a devDependency) | `pytest tests/test_routes_evidence_graph.py -q` / `npm run test -- EvidenceGraph` | ❌ Wave 0 — new files both sides |
| EVID-03 | Assurance Card renders CLAIM/EVIDENCE/RULE/CHECK/CONFIDENCE from a real `verification_results` entry, with no field synthesized client-side | frontend: component render test asserting all five fields present and matching fixture data; backend: integration test on the new finding-detail route | `npm run test -- AssuranceCard` / `pytest tests/test_routes_findings.py -q` | ❌ Wave 0 — new files both sides |

### Sampling Rate
- **Per task commit:** the relevant quick-run command above (module-scoped `-k` filter)
- **Per wave merge:** full backend suite (`pytest -q`, Postgres + OPA + seed up) and full frontend suite (`npm run test`)
- **Phase gate:** Full suite green (both backend and frontend) before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `backend/tests/test_evidence_graph.py` — covers GRAPH-01, GRAPH-02
- [ ] `backend/tests/test_routes_evidence_graph.py` (or folded into the above) — covers GRAPH-03's backend half
- [ ] `backend/tests/test_routes_findings.py` — covers EVID-03's backend half
- [ ] `frontend/src/__tests__/EvidenceGraph.test.tsx` (or co-located, matching `frontend/src/__tests__/routes.test.tsx`'s existing convention) — covers GRAPH-03's frontend half
- [ ] `frontend/src/__tests__/AssuranceCard.test.tsx` — covers EVID-03's frontend half
- [ ] `infra/postgres/seed/003_change_affects_fixture.sql` — not a test file, but a required Wave-0-equivalent fixture gap: no test above can pass without seeded `change_affects` rows for `CR-2026-089`
- [ ] Framework install: `pip install networkx==3.6.1` (backend) — no frontend framework install needed (`@xyflow/react` and `vitest`/`@testing-library/react` already present)

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | RBAC/auth is Phase 5 (SAFE-01, C2) — no authenticated user model exists yet anywhere in this codebase (confirmed: `main.py` registers only `/api/health` and the WS route, no auth middleware) |
| V3 Session Management | No | Same as above — deferred to Phase 5 |
| V4 Access Control | No | Same as above — Phase 4's new routes are unauthenticated, matching every other route in the codebase today; this is a known, accepted gap until Phase 5, not a Phase 4 regression |
| V5 Input Validation | **Yes** | `system_id` and `node_id`/`finding_id` path parameters must reach every SQL statement exclusively via `asyncpg`'s `$1`-style placeholders — never string-formatted — exactly matching `backend/app/agents/c1_verifier.py`'s and `backend/app/agents/a2_compliance.py`'s established, already-tested convention (both read in full this session) |
| V6 Cryptography | No | Not applicable to this phase's scope — no new cryptographic operation is introduced |

### Known Threat Patterns for this stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| SQL injection via `system_id`/`node_id`/`finding_id` path parameters | Tampering | Parameterized queries exclusively (`asyncpg` `$1` placeholders) — this codebase already has zero f-string-built SQL anywhere in `backend/app/agents/`; Phase 4's new graph/route modules must hold that line |
| Table-name injection in dynamically-built SQL (mirroring C1's own documented risk) | Tampering | `c1_verifier.py`'s own docstring (read this session) states: *"Table and column names used to build SQL statements come exclusively from the frozen allowlists below... never from request data... concatenated into the query string rather than f-string-interpolated, so an unrecognised rule id returns no record instead of building a statement (ASVS V5)."* Phase 4's `entity_type`-to-table resolution for `change_affects` (if any dynamic query ever branches on `entity_type`) must follow this exact allowlist pattern — never build a table name from user/request input. |
| Unbounded/expensive graph rebuild as a denial-of-service vector | Denial of Service | The rebuild endpoint (D-02) recomputes an entire system's graph on every call with no rate limiting in this phase's scope (no auth exists yet to attribute calls to a caller) — acceptable for a hackathon-scale demo dataset (Bible-seeded systems have single-digit-to-low-double-digit rows per table), but should be noted as a known limitation, not silently assumed safe at production scale |

## Sources

### Primary (HIGH confidence — all verified this session by direct file read)
- `AegisX-AI-Project-Bible-v6.md` §10.1 (NetworkX Graph Definition, lines 1331-1362), §10.3 (React Flow Visualization, lines 1364-1366), §11.2 (Assurance Card field list, lines 1376-1378), §14.1-14.3 (Design Principle / Deterministic Verification Centre / Blast Radius, lines 1581-1780), §1.3 (Deterministic-First Decision Table, lines 198-228), §12 (API Endpoints, lines 1404-1420)
- `AegisX-Build-Map.md` SENT-3-01 through SENT-3-05 ticket contracts (lines 68-77)
- `infra/postgres/initdb/001_schema.sql` (full file, 249 lines) — `graph_nodes`/`graph_edges` DDL, absence of `changes`→`requirements`/`design_elements`/`test_cases` FKs
- `infra/postgres/seed/001_seed.sql` (full file, 96 lines) — confirms `CR-2026-089`/`CA-2026-089-1` is the seeded change record, confirms `design_elements` is unseeded
- `infra/postgres/seed/002_urs_fixture.sql` (full file) — the additive-seed-fixture pattern precedent
- `backend/app/agents/c1_verifier.py` (full file, 287 lines) — `verify_finding()`/`run_c1()` return shape, the allowlist-not-f-string SQL pattern
- `backend/app/agents/a2_compliance.py`, `backend/app/agents/minimal_specialists.py`, `backend/app/graph/state.py`, `backend/app/db.py`, `backend/app/main.py`, `backend/app/schemas.py` (all read in full this session)
- `backend/README.md` — "AgentFinding conventions (Phase 3)" table (lines 157-171) and confirmation that "`verification_results` is the shape Phase 4's Assurance Card UI reads its data from" (line 224)
- `frontend/src/routes.tsx`, `frontend/src/components/AgentTopologyCanvas.tsx`, `frontend/src/lib/ws.ts`, `frontend/package.json` (all read in full this session)
- `backend/requirements.txt` (full file, 10 lines) — confirms no `networkx` entry
- `.planning/config.json` — `nyquist_validation: true`, `security_enforcement: true`, `security_asvs_level: 1`

### Secondary (MEDIUM confidence)
- `pip index versions networkx` (run this session) — confirms 3.6.1 is current on PyPI
- NetworkX official docs — `descendants`/`dfs_preorder_nodes` reference pages (networkx.org/documentation/stable) [CITED]
- React Flow (`@xyflow/react`) official docs — `useNodesState`, custom node types, `onNodeClick` (reactflow.dev) [CITED]

### Tertiary (LOW confidence)
- None — every claim in this document is either a direct file read this session (HIGH) or an official-docs citation (MEDIUM); no claim rests on unverified training-data recall alone. The one `[SUS]`-flagged package (`networkx`) has its verdict reasoning fully disclosed in the Package Legitimacy Audit rather than silently upgraded.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — `networkx` version verified live via `pip index versions`; `@xyflow/react` version verified by direct `package.json` read (already installed, in use)
- Architecture: HIGH — every schema/code claim (table shapes, existing FK graph, existing agent/route patterns) verified by direct file read this session, not recalled from training data
- Pitfalls: HIGH — all five pitfalls are grounded in specific, quoted/cited file contents (missing `networkx` install, missing FKs, empty `design_elements`, closed schema file, undeclared relationship type) confirmed this session, not speculative

**Research date:** 2026-08-21
**Valid until:** 2026-09-04 (14 days — this research is tightly coupled to the current, actively-changing state of the backend/frontend codebase; re-verify file-read claims if significant Phase-4-adjacent work lands before planning begins)
