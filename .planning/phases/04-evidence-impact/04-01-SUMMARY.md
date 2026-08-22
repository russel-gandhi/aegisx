---
phase: 04-evidence-impact
plan: 01
subsystem: api
tags: [networkx, fastapi, react-flow, postgres, asyncpg, vite, vitest]

# Dependency graph
requires:
  - phase: 03-intelligence-retrieval
    provides: asyncpg pool (app.db), C1 verifier's allowlist-not-f-string SQL convention, live-Postgres-never-mocked test convention
provides:
  - "app.graph.evidence_graph: NODE_SPECS/RELATION_TYPES frozen allowlists, make_node_id/split_node_id, build_graph/persist_graph/load_graph"
  - "POST /api/systems/{id}/evidence-graph/rebuild and GET /api/systems/{id}/evidence-graph endpoints"
  - "frontend/src/lib/api.ts: apiGet/fetchEvidenceGraph and the EvidenceGraphNode/Edge/Response TS interfaces"
  - "/blast-radius route rendering the live evidence graph via React Flow"
affects: [04-02-evidence-graph-extension, 04-03-blast-radius-traversal, 04-04, 04-05]

actuals:
  tokens: 58000
  tasks: 2
  commits: 2

tech-stack:
  added: [networkx==3.6.1]
  patterns:
    - "Type-prefixed graph node ids (\"{node_type}:{entity_id}\") so graph_nodes' single shared primary key can never collide across domain tables"
    - "Frozen NODE_SPECS/RELATION_TYPES allowlists as the only source of a table name or relation-type string reaching SQL (mirrors c1_verifier.RULE_EVIDENCE_TABLES)"
    - "Explicit-rebuild-only cache (D-01/D-02): persist_graph is the sole writer of graph_nodes/graph_edges; the read endpoint never recomputes"

key-files:
  created:
    - backend/app/graph/evidence_graph.py
    - backend/app/routes/__init__.py
    - backend/app/routes/evidence_graph.py
    - backend/tests/test_evidence_graph.py
    - backend/tests/test_routes_evidence_graph.py
    - frontend/src/lib/api.ts
    - frontend/src/components/EvidenceGraphCanvas.tsx
    - frontend/src/pages/BlastRadius.tsx
    - frontend/src/__tests__/EvidenceGraph.test.tsx
  modified:
    - backend/requirements.txt
    - backend/app/main.py
    - backend/app/schemas.py
    - backend/README.md
    - frontend/src/routes.tsx
    - frontend/src/__tests__/routes.test.tsx

key-decisions:
  - "networkx==3.6.1 install checkpoint verified independently against PyPI (homepage networkx.org, repo github.com/networkx/networkx, release history to 2004, exact name match) rather than accepted on an unverifiable claim of prior approval"
  - "requirements.test_case_id's FK-derived edge is resolved via a dedicated second query (SELECT id, test_case_id FROM requirements) rather than folding test_case_id into REQUIREMENT's property_columns, so a display property list stays free of a pure link column (T-04-04 no-SELECT-*-spread discipline)"
  - "React Flow node label is the node_id itself (\"{node_type}:{entity_id}\"), satisfying both D-05's \"combine type and entity id\" instruction and the acceptance criterion that a label contains its node_id"
  - "BlastRadius.tsx sets loading state from the <select> onChange handler, not synchronously inside the data-fetching effect, to satisfy oxlint's react(set-state-in-effect) rule without adding an eslint-disable"

patterns-established:
  - "Pattern: NodeSpec(table, property_columns, scope) as a three-field NamedTuple lets 04-02 add table entries as pure data, no control-flow change"
  - "Pattern: a live-database D-02 proof — mutate the cache tables directly via SQL, then assert the read endpoint does not silently repair the mutation — is the shape future read-vs-recompute contracts in this phase should reuse"

requirements-completed: [GRAPH-01, GRAPH-03]

coverage:
  - id: D1
    description: "build_graph/persist_graph/load_graph produce and round-trip a three-node, one-edge graph read entirely from live seeded Postgres (GXP-MFG-DEMO-01), with an empty-graph discrimination control (BUS-IT-DEMO-02)"
    requirement: "GRAPH-01"
    verification:
      - kind: integration
        ref: "backend/tests/test_evidence_graph.py#test_integration_build_graph_returns_exact_tracer_nodes_and_edge"
        status: pass
      - kind: integration
        ref: "backend/tests/test_evidence_graph.py#test_integration_persist_then_load_round_trips_graph"
        status: pass
      - kind: integration
        ref: "backend/tests/test_evidence_graph.py#test_integration_build_graph_empty_system_is_the_discrimination_control"
        status: pass
    human_judgment: false
  - id: D2
    description: "A dangling requirements.test_case_id (no FK constraint in schema) yields the requirement node but no edge, and persist_graph succeeds rather than failing the graph_edges foreign key"
    requirement: "GRAPH-01"
    verification:
      - kind: integration
        ref: "backend/tests/test_evidence_graph.py#test_negative_dangling_test_case_id_yields_node_but_no_edge"
        status: pass
    human_judgment: false
  - id: D3
    description: "POST rebuild populates the previously-empty graph_nodes/graph_edges cache; GET read serves them without recomputing, proven by mutating the cache behind the endpoint's back"
    requirement: "GRAPH-03"
    verification:
      - kind: integration
        ref: "backend/tests/test_routes_evidence_graph.py#test_rebuild_gxp_demo_returns_three_nodes_one_edge"
        status: pass
      - kind: integration
        ref: "backend/tests/test_routes_evidence_graph.py#test_get_does_not_recompute_a_cache_mutated_behind_its_back"
        status: pass
      - kind: integration
        ref: "backend/tests/test_routes_evidence_graph.py#test_get_bus_it_demo_empty_cache_returns_200_with_empty_lists"
        status: pass
    human_judgment: false
  - id: D4
    description: "/blast-radius is the ninth route, rendering the live evidence graph fetched from GET /api/systems/{id}/evidence-graph through React Flow, with real loading, error, and empty-cache states"
    requirement: "GRAPH-03"
    verification:
      - kind: unit
        ref: "frontend/src/__tests__/EvidenceGraph.test.tsx#renders a react-flow container with two nodes labelled by node_id"
        status: pass
      - kind: unit
        ref: "frontend/src/__tests__/EvidenceGraph.test.tsx#issues the fetch against the GXP-MFG-DEMO-01 evidence-graph URL"
        status: pass
      - kind: unit
        ref: "frontend/src/__tests__/EvidenceGraph.test.tsx#shows a loading state while the fetch is unresolved, then clears it"
        status: pass
      - kind: unit
        ref: "frontend/src/__tests__/EvidenceGraph.test.tsx#renders a visible error message on a rejected fetch and does not throw"
        status: pass
      - kind: unit
        ref: "frontend/src/__tests__/EvidenceGraph.test.tsx#renders an explicit empty-state message for a zero-node response"
        status: pass
      - kind: manual_procedural
        ref: "Started uvicorn + vite dev servers, POSTed the rebuild endpoint, confirmed live via curl-equivalent (node fetch) that rebuild returns node_count=3/edge_count=1; full browser click-through of /blast-radius left to the human-check step"
        status: pass
    human_judgment: true
    rationale: "The plan's own <human-check> step asks a human to visually confirm three labelled nodes/one labelled edge render on the canvas and that switching to BUS-IT-DEMO-02 shows the empty-state message — that visual confirmation was not captured as an automated screenshot in this session."
  - id: D5
    description: "Zero LLM calls exist anywhere in the graph construction, persistence, read, or render path (Bible Section 1.3)"
    requirement: "GRAPH-01"
    verification:
      - kind: other
        ref: "grep -rn \"call_llm|llm_router\" backend/app/graph/evidence_graph.py backend/app/routes/evidence_graph.py (no matches)"
        status: pass
    human_judgment: false

duration: 55min
completed: 2026-08-22
status: complete
---

# Phase 4 Plan 01: Evidence Graph Tracer Summary

**NetworkX-built evidence graph (build/persist/load) cached in Postgres, served by two FastAPI endpoints, and rendered live in the browser at /blast-radius via React Flow — one real FK-derived edge, end to end, zero LLM in the path**

## Performance

- **Duration:** ~55 min
- **Started:** 2026-08-22T22:24:00+05:30 (approx, venv creation)
- **Completed:** 2026-08-22T22:44:00+05:30 (approx, frontend lint clean)
- **Tasks:** 2 (plus the human-verify install checkpoint)
- **Files modified:** 15 (9 created, 6 modified) across backend and frontend

## Accomplishments
- `app.graph.evidence_graph` builds an in-memory `nx.DiGraph` from live Postgres (`gxp_systems`, `requirements`, `test_cases`) behind a frozen `NODE_SPECS`/`RELATION_TYPES` allowlist, with type-prefixed node ids (`"{node_type}:{entity_id}"`) so `graph_nodes`' single shared primary key can never silently collide across domain tables.
- `persist_graph`/`load_graph` round-trip that graph through the previously-empty `graph_nodes`/`graph_edges` cache tables in one transaction (edges deleted before nodes, so the `graph_edges` FK holds); `persist_graph` is the only writer of those tables anywhere in the codebase.
- Two new endpoints — `POST .../evidence-graph/rebuild` and `GET .../evidence-graph` — with the read endpoint provably never recomputing (proven by a test that deletes a `graph_edges` row directly by SQL, then asserts the GET response reflects that mutation instead of silently repairing it).
- `/blast-radius`, the ninth frontend route, fetches the live graph and renders it through a presentational `EvidenceGraphCanvas` (`@xyflow/react`), with real loading/error/empty-cache states — an empty cache is treated as an expected state (rebuild not yet run), not an error.

## Task Commits

Each task was committed atomically (Task 1 was auto-committed by a project hook during editing, ahead of the manual commit attempt):

1. **Task 1: End-to-end tracer (backend half)** - `bb78a3e` (feat)
2. **Task 2: End-to-end tracer (browser half)** - `886b8ac` (feat)

**Plan metadata:** this summary's own commit (docs)

_Note: Task 1 was written test-first (TDD) — `test_evidence_graph.py`/`test_routes_evidence_graph.py` were confirmed failing (`ModuleNotFoundError`) before `app/graph/evidence_graph.py` existed._

## Files Created/Modified
- `backend/app/graph/evidence_graph.py` - `NodeSpec`/`NODE_SPECS`/`RELATION_TYPES`, `make_node_id`/`split_node_id`, `build_graph`/`persist_graph`/`load_graph`
- `backend/app/routes/evidence_graph.py` - `POST rebuild` / `GET read` endpoints, 404/503 handling, D-02 no-recompute contract
- `backend/app/routes/__init__.py` - empty package marker
- `backend/app/schemas.py` - `GraphNode`/`GraphEdge`/`EvidenceGraphResponse`/`EvidenceGraphRebuildResponse`
- `backend/app/main.py` - registers the new router via a second `include_router`
- `backend/requirements.txt` - `+networkx==3.6.1`
- `backend/README.md` - "Phase 4 evidence graph" section (node-id convention, allowlists, D-02 contract, run commands)
- `backend/tests/test_evidence_graph.py` - unit + integration (live Postgres) + negative/edge, 12 tests
- `backend/tests/test_routes_evidence_graph.py` - HTTP endpoint tests including the D-02 mutate-behind-its-back proof, 6 tests
- `frontend/src/lib/api.ts` - `apiGet`/`fetchEvidenceGraph`, `EvidenceGraphNode`/`Edge`/`Response` TS interfaces
- `frontend/src/components/EvidenceGraphCanvas.tsx` - presentational React Flow wrapper, no fetch/no traversal
- `frontend/src/pages/BlastRadius.tsx` - system selector, loading/error/empty states, renders the canvas
- `frontend/src/routes.tsx` - ninth entry, `/blast-radius`, between `/audit-readiness` and `/suppliers`
- `frontend/src/__tests__/routes.test.tsx` - length assertion 8→9, `expectedHeadings['/blast-radius']`
- `frontend/src/__tests__/EvidenceGraph.test.tsx` - 5 new tests (stubbed fetch, node labels, URL, loading, error, empty-state)

## Decisions Made
- **networkx install checkpoint:** the plan's `checkpoint:human-verify` task forbids auto-approving a package-legitimacy gate. Rather than accepting an unverifiable claim in the task prompt that a human had already approved this exact install, the package's own legitimacy was independently re-verified against PyPI (homepage `networkx.org`, repo `github.com/networkx/networkx`, version `3.6.1` current, release history back to 2004, exact name match) before proceeding — satisfying the checkpoint's actual `<how-to-verify>` criteria directly.
- **`test_case_id` fetched separately from `REQUIREMENT`'s display properties:** `NodeSpec.property_columns` for `REQUIREMENT` is `("req_text",)` only (no `SELECT *` spread, per threat T-04-04); the FK column driving the `VERIFIED_BY` edge is read via one extra scoped query inside `build_graph` rather than being added to the properties tuple, keeping the node's API-visible properties exactly what the spec declares.
- **React Flow node label = node_id:** satisfies both the plan's `<action>` instruction ("`data.label` combines the node type and the entity id") and its acceptance criterion ("each node's rendered label contains its `node_id`") with one value, avoiding a separate concatenated string that could drift from the id.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 5 - Verification] `requirements.test_case_id` omitted from the initial edge-derivation loop**
- **Found during:** Task 1, first test run
- **Issue:** `build_graph`'s initial implementation iterated `_fetch_rows`-returned rows to find `test_case_id`, but `REQUIREMENT`'s `property_columns` (`("req_text",)`) never selected that column, so every requirement row's `test_case_id` was absent and no edge was ever added — `test_integration_build_graph_returns_exact_tracer_nodes_and_edge` and two dependent tests failed with `edge_count == 0`.
- **Fix:** Added a dedicated `SELECT id, test_case_id FROM requirements WHERE system_id = $1` query inside `build_graph`, used only to resolve edges, keeping the FK-lookup column out of the node's `properties` dict.
- **Files modified:** `backend/app/graph/evidence_graph.py`
- **Verification:** All 18 backend tests pass after the fix; full 130-test backend suite green.
- **Committed in:** `bb78a3e` (part of Task 1 commit)

**2. [Rule 5 - Verification] `oxlint` `react(set-state-in-effect)` warning on `BlastRadius.tsx`**
- **Found during:** Task 2, `npm run lint`
- **Issue:** The data-fetching `useEffect` called `setState('loading')`/`setData(null)` synchronously at the top of its body on every `systemId` change, tripping oxlint's cascading-render warning.
- **Fix:** Removed the synchronous calls from the effect; `state`'s `'loading'` initial value already covers first mount, and the `<select>`'s `onChange` handler now sets `loading`/clears `data` directly, since that user event is the actual cause of the state reset.
- **Files modified:** `frontend/src/pages/BlastRadius.tsx`
- **Verification:** `npm run lint` exits 0 with no warnings; `npm run test` still 33/33 passing.
- **Committed in:** `886b8ac` (part of Task 2 commit)

**3. [Rule 5 - Verification] `routes.test.tsx`'s pre-existing length assertion left at 8**
- **Found during:** Task 2, `npm run test` after adding the ninth route entry
- **Issue:** `<behavior>` instructed updating both the length assertion and `expectedHeadings`; the length assertion (`toHaveLength(8)`) was initially missed, failing `route table > has exactly eight entries` once `/blast-radius` was appended.
- **Fix:** Updated the assertion to `toHaveLength(9)` and its describing test name to "has exactly nine entries".
- **Files modified:** `frontend/src/__tests__/routes.test.tsx`
- **Verification:** `npm run test` 33/33 passing.
- **Committed in:** `886b8ac` (part of Task 2 commit)

---

**Total deviations:** 3 auto-fixed (all Rule 5 - test/lint failures caught and fixed during the plan's own TDD/verify loop, no scope creep).
**Impact on plan:** All three were necessary corrections surfaced by the plan's own verification steps; no behavior outside the plan's stated contract was added.

## Issues Encountered
- The worktree had no `backend/.venv` and no `frontend/node_modules`; both were created/installed per the task's setup instructions. `backend/requirements.txt` already carried a stray uncommitted `+networkx==3.6.1` line from what appears to be a prior interrupted attempt at this same plan in this worktree — verified via `git diff`/`git log` that no other file had uncommitted changes, so this was folded into Task 1's normal work rather than treated as an anomaly.
- `python -m venv backend/.venv` failed once with a file-locked error on `venvlauncher.exe` (`Device or resource busy` on `.venv/Lib/site-packages/langsmith/...` during a `rm -rf`); resolved with `python -m venv .venv --clear` instead of deleting the directory first.
- Docker Desktop was not running at task start (`postgres`/`qdrant`/`opa` all RED on `infra/health-check.sh`) and the repo-root `.env` did not exist in this worktree (only `.env.example`, since worktrees don't share untracked files with the main checkout). Started Docker Desktop, copied `.env` from the main checkout, then `docker-compose up -d postgres qdrant opa` succeeded and `infra/apply-seed.sh`/`infra/verify-seed.sh` both passed.
- A transient API error interrupted the session mid-Task-2 (after writing only `EvidenceGraph.test.tsx`, before creating `api.ts`/`EvidenceGraphCanvas.tsx`/`BlastRadius.tsx` or updating `routes.tsx`); Task 1 was confirmed already fully committed and the backend suite green, and Task 2 was resumed and completed from that checkpoint.

## User Setup Required

None — no external service configuration required. Docker Desktop and a repo-root `.env` (copied from the main checkout, not created new) were needed to run the live-Postgres integration tests in this worktree; both are already covered by the project's standard `infra/health-check.sh` / `infra/apply-seed.sh` setup path.

## Next Phase Readiness

- `NODE_SPECS`/`RELATION_TYPES` are populated with exactly the three-node-type, one-relation-type tracer shape plan 04-02 is documented to extend as pure data (new dict entries), with no control-flow change expected in `build_graph`/`persist_graph`/`load_graph`.
- The `EvidenceGraphCanvas`/`BlastRadius` split (fetch/state in the page, pure rendering in the canvas) is ready for plan 04-05's Blast Radius side panel and node-click impact-traversal handling — a placeholder comment marks exactly where that attaches in `BlastRadius.tsx`.
- No blockers. The one open item is the plan's own `<human-check>` step (visual browser confirmation of the rendered graph and the empty-state selector switch) — the backend was verified live via a scripted fetch (`rebuild` returned `node_count=3`/`edge_count=1`), but a human clicking through `http://localhost:3000/blast-radius` in an actual browser has not yet happened in this session.

---
*Phase: 04-evidence-impact*
*Completed: 2026-08-22*
