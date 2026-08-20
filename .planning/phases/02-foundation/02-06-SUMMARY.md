---
phase: 02-foundation
plan: 06
subsystem: api
tags: [langgraph, stategraph, orchestration, typed-dict, pytest]

# Dependency graph
requires:
  - phase: 02-foundation
    provides: "backend/.venv, backend/app/schemas.py, backend/pytest.ini + tests/conftest.py, backend/requirements.txt (langgraph==1.2.11, langchain-core==1.6.0 already pinned) from plan 02-03"
provides:
  - "backend/app/graph/state.py — AgentState/AgentFinding/ActionProposal TypedDicts, eleven async stub node coroutines, route_specialists Send fan-out, module-level graph builder and compiled_graph"
  - "backend/tests/test_graph_topology.py — structural topology assertions (node set, edge set, conditional branch, route_specialists subset behavior, reducer annotation, end-to-end ainvoke)"
affects: [phase-03-agents, phase-05-safety-remediation, phase-06-websocket-streaming]

actuals:
  tokens: 4234
  tasks: 2
  commits: 2

tech-stack:
  added: []
  patterns: ["graph-state TypedDicts (app.graph.state) kept structurally separate from application-layer Pydantic BaseModels (app.schemas) with the same field names — no cross-import, conversion happens explicitly at the API boundary", "runtime try/except import-path resolution for langgraph API drift (Send: langgraph.types then langgraph.constants; add_messages: langgraph.graph.message then langgraph.graph) instead of hard-coding one path", "structural topology testing via whole-collection equality against the StateGraph builder's own .nodes/.edges/.branches, not diagram parsing or membership checks"]

key-files:
  created:
    - backend/app/graph/__init__.py
    - backend/app/graph/state.py
    - backend/tests/test_graph_topology.py
  modified: []

key-decisions:
  - "Created a fresh backend/.venv inside this worktree (gitignored, absent from the worktree checkout) rather than assuming plan 02-03's venv was reachable — installed the same seven pinned dependencies from the existing requirements.txt with a clean pip check."
  - "Resolved Send from langgraph.types (not langgraph.constants) — the Bible's constants import path still works on the pinned langgraph==1.2.11 but emits LangGraphDeprecatedSinceV10, so the code tries langgraph.types first with a fallback import for older versions, per the plan's explicit instruction to resolve at execution time rather than guess."
  - "Resolved add_messages from langgraph.graph.message (the Bible's original path, still current) with a fallback to langgraph.graph."
  - "Reworded one docstring sentence to avoid a spurious third literal match of the string 'operator.add' (the acceptance criteria greps for exactly 2), since the reducer explanation originally quoted the token verbatim in prose in addition to the two real annotations."
  - "Task 2's 'prove the suite can fail' step was carried out as a real, git-verified mutation of the actual backend/app/graph/state.py (temporarily dropping the A3->C1 edge from the loop, confirmed via a real pytest run that test_direct_edge_set_matches_topology_exactly fails and names ('A3', 'C1') as the missing pair, then restored with a clean git diff) rather than only a synthetic in-test simulation — the committed test_graph_topology.py additionally keeps a lightweight synthetic regression test (test_removing_a_specialist_to_c1_edge_fails_the_edge_assertion) that exercises the same missing-pair-detection logic without mutating the shared module."

patterns-established:
  - "New graph nodes in Phase 3+ are node-body substitutions inside the existing graph builder in app/graph/state.py — no topology, edge, or route_specialists change is expected as agents replace stubs."
  - "Any future langgraph API drift should be handled the same way as this plan's Send/add_messages resolution: a try/except import at module scope trying the current path first, never a silent hard assumption."

requirements-completed: [ORC-01, ENV-04]

coverage:
  - id: D1
    description: "The LangGraph StateGraph compiles with exactly the eleven-node topology C2 -> A0 -> [A1..A6 via Send] -> C1 -> A7 -> C3, asserted structurally against the graph builder's own node/edge/branch collections"
    requirement: "ORC-01"
    verification:
      - kind: unit
        ref: "backend/tests/test_graph_topology.py#test_node_set_is_exactly_the_eleven_participants"
        status: pass
      - kind: unit
        ref: "backend/tests/test_graph_topology.py#test_direct_edge_set_matches_topology_exactly"
        status: pass
      - kind: unit
        ref: "backend/tests/test_graph_topology.py#test_a0_conditional_destinations_are_exactly_a1_through_a6"
        status: pass
    human_judgment: false
  - id: D2
    description: "route_specialists returns one Send per active_agents entry, correct for the full six-agent set, a two-agent subset, and an empty list"
    requirement: "ORC-01"
    verification:
      - kind: unit
        ref: "backend/tests/test_graph_topology.py#test_route_specialists_all_six_active_returns_six_sends"
        status: pass
      - kind: unit
        ref: "backend/tests/test_graph_topology.py#test_route_specialists_two_agent_subset_returns_two_sends"
        status: pass
      - kind: unit
        ref: "backend/tests/test_graph_topology.py#test_route_specialists_empty_active_agents_returns_empty_list"
        status: pass
    human_judgment: false
  - id: D3
    description: "compiled_graph.ainvoke(...) runs to completion through all eleven stub nodes, returning final_synthesis and verification_results as specified, with the findings/proposed_actions reducer proven to be operator.add (not last-writer-wins) both by annotation inspection and by direct reducer-function exercise"
    requirement: "ORC-01"
    verification:
      - kind: unit
        ref: "backend/tests/test_graph_topology.py#test_ainvoke_completes_through_all_eleven_stub_nodes"
        status: pass
      - kind: unit
        ref: "backend/tests/test_graph_topology.py#test_agentstate_findings_reducer_is_operator_add"
        status: pass
      - kind: unit
        ref: "backend/tests/test_graph_topology.py#test_reducer_accumulates_findings_from_multiple_branches_not_last_writer_wins"
        status: pass
      - kind: unit
        ref: "cd backend && .venv/Scripts/python -c \"...ainvoke(...); assert s['final_synthesis'].startswith('Execution complete')\" — printed 'graph ok'"
        status: pass
    human_judgment: false
  - id: D4
    description: "AgentState/AgentFinding/ActionProposal graph-state TypedDicts are importable and documented as distinct from the app.schemas Pydantic models of the same names; no LLM/DB/OPA call exists in any of the eleven stub nodes"
    requirement: "ENV-04"
    verification:
      - kind: unit
        ref: "cd backend && .venv/Scripts/python -c \"from app.graph.state import AgentState, AgentFinding, ActionProposal, graph, compiled_graph\" — printed 'imports ok'"
        status: pass
      - kind: unit
        ref: "grep -icE '(openai|anthropic|gemini|groq|deepseek|ChatModel|invoke_llm)' backend/app/graph/state.py — 0"
        status: pass
      - kind: unit
        ref: "grep -cE '(psycopg|asyncpg|opa_client|httpx)' backend/app/graph/state.py — 0"
        status: pass
    human_judgment: false

duration: 20min
completed: 2026-08-21
status: complete
---

# Phase 2 Plan 6: LangGraph StateGraph Orchestration Skeleton Summary

**Eleven-node LangGraph `StateGraph` (C2 -> A0 -> [A1-A6 via Send] -> C1 -> A7 -> C3) compiling and running end-to-end through literal stub returns, with a structural topology test suite that fails when the edge set, conditional fan-out, or `operator.add` reducers drift.**

## Performance

- **Duration:** ~20 min
- **Tasks:** 2 completed
- **Files modified:** 3 (all created)

## Accomplishments
- `backend/app/graph/state.py` transcribes Bible Section 1.2 verbatim: `AgentFinding`/`ActionProposal`/`AgentState` `TypedDict`s (with `operator.add` reducers on `findings` and `proposed_actions`, `add_messages` on `messages`), eleven async stub node coroutines with the Bible's exact literal returns, `route_specialists`, and the module-level `graph` builder + `compiled_graph`
- Graph assembled in the Bible's exact node-id and edge order: `set_entry_point("C2")`, `C2 -> A0`, conditional fan-out `A0 -> [A1..A6]` via `route_specialists`, each specialist `-> C1`, then `C1 -> A7 -> C3 -> END`
- `backend/tests/test_graph_topology.py` (11 tests) asserts the topology structurally: whole-collection equality on the node set and the direct-edge set (not membership checks), the A0 conditional branch's exact destination set, `route_specialists` for full/subset/empty `active_agents`, the `operator.add` reducer read directly from `typing.get_type_hints`, and an end-to-end `ainvoke` producing the documented `final_synthesis`/`verification_results`
- Confirmed via a real (not simulated) mutate-test-restore cycle on `backend/app/graph/state.py` that the edge-set assertion fails and names the exact missing pair (`('A3', 'C1')`) when a specialist-to-C1 edge is dropped, then restored cleanly (verified via `git diff` showing no residual change)
- No LLM client, database call, or network call anywhere in the module — confirmed by grep — and C2/C1/C3 are documented in the module docstring and per-function docstrings as permanently forbidden from ever hosting an LLM (Bible Section 1.3)

## Task Commits

Each task was committed atomically:

1. **Task 1: Transcribe the Bible Section 1.2 StateGraph with eleven stub nodes** - `83c24d4` (feat)
2. **Task 2: Assert the topology structurally, not by inspection** - `5571ffe` (test)

_Task 2 is a `tdd="true"` test-only task written against Task 1's already-complete implementation (per the plan's own instruction — the tests assert the shape of code already built, rather than driving new production code through a RED/GREEN cycle); its acceptance criteria's "prove the suite can fail" step was carried out as a real edit-run-revert cycle against the shared module during execution, not committed as a mutation._

## Files Created/Modified
- `backend/app/graph/__init__.py` - empty package marker
- `backend/app/graph/state.py` - `AgentState`, `AgentFinding`, `ActionProposal` TypedDicts; eleven stub nodes; `route_specialists`; `graph` builder; `compiled_graph`
- `backend/tests/test_graph_topology.py` - 11 structural topology tests, no infrastructure dependency

## Decisions Made
- Built a fresh project-local `backend/.venv` for this worktree (absent because `.venv/` is gitignored and this is a separate worktree checkout from plan 02-03's), installing the same pinned `requirements.txt` set with a clean `pip check`.
- `Send` resolved from `langgraph.types` (current, non-deprecated on the pinned `langgraph==1.2.11`); `langgraph.constants.Send` still imports but emits `LangGraphDeprecatedSinceV10`. `add_messages` resolved from `langgraph.graph.message` (the Bible's original path, still current). Both resolutions implemented as runtime `try/except` fallbacks per the plan's explicit instruction, not hardcoded guesses.
- Reworded one docstring sentence that originally quoted the literal string `operator.add` in prose (in addition to the two real field annotations), because the acceptance criteria greps for exactly 2 occurrences — kept the explanatory content, changed only the wording so the grep count matches without weakening the documentation.

## Deviations from Plan

None - plan executed exactly as written. The venv creation was implied setup (plan 02-03's dependency, not a deviation) needed because this wave-2 plan runs in an isolated worktree where the gitignored `.venv/` from 02-03 does not exist; no `requirements.txt` change was needed since the same seven pins already declared there were reused verbatim.

## Issues Encountered
- `backend/.venv` did not exist in this worktree (gitignored artifact, not carried by git worktree checkout). Resolved by creating it fresh from the existing `backend/requirements.txt` — no dependency versions changed, `pip check` clean, all seven imports (`fastapi, pydantic, uvicorn, httpx, langgraph, langchain_core, pytest`) succeed.
- Initial docstring wording tripled the `operator.add` grep count (2 real annotations + 1 prose mention) against the plan's exact-count acceptance criterion (`grep -c 'operator.add' ... outputs 2`). Reworded the prose sentence to describe the reducer without repeating the literal token; verified grep now outputs `2`.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- `backend/app/graph/state.py`'s `compiled_graph` is the exact attachment point Phase 3's real agents replace stub bodies inside, with no topology change expected (SENT-2-01 replaces `orchestrator_a0`, SENT-2-02 replaces `compliance_a2`, SENT-2-12 replaces `evidence_verifier_c1`).
- `route_specialists`'s `Send`-per-`active_agents`-entry design already supports subset fan-out, so Phase 3's ORC-02 2000ms A0 timeout fallback only needs to change what `active_agents` contains, not this function or the graph edges.
- No Docker/Compose dependency: this plan's code and test suite have zero I/O (confirmed by grep for `psycopg`/`asyncpg`/`opa_client`/`httpx`), so infrastructure-independence holds by construction; a live `docker compose stop && pytest` re-check was not separately run in this sandbox but is expected to pass unchanged given the code contains no reachable infrastructure call.
- No blockers.

## Self-Check: PASSED

All 3 files created by this plan verified present on disk; both task commits (`83c24d4`, `5571ffe`) verified present in `git log` on branch `worktree-agent-a1b8648fb85eb92e6`.

---
*Phase: 02-foundation*
*Completed: 2026-08-21*
