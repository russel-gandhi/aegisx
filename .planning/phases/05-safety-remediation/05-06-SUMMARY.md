---
phase: 05-safety-remediation
plan: 06
subsystem: safety-remediation
tags: [langgraph, c2-gateway, a7-remediation, c3-gateway, rbac, injection-detection, checkpoint]

# Dependency graph
requires:
  - phase: 05-safety-remediation
    provides: "05-02: c2_gateway.py detect_injection/PERMISSION_MATRIX; 05-04: c3_gateway.py BLOCKED_CATEGORIES/describe_category, a7_remediation.py structured CAPA payload; 05-05: WebSocket push, Action/Approval Centre UI"
provides:
  - "a0_orchestrator.py: extract_user_query (public, renamed from _extract_user_query); run_a0 short-circuits on state['blocked']"
  - "c2_gateway.py: run_c2 -- node adapter, RBAC + injection detection, fail-closed on absent/unrecognised role, publishes permitted_agents"
  - "a7_remediation.py: run_a7 -- node adapter, D-03 gate (nothing unless remediation_requested is explicitly true)"
  - "c3_gateway.py: run_c3 -- node adapter, categorises proposed_actions, composes final_synthesis"
  - "graph/state.py: safety_gateway_c2/remediation_a7/action_gateway_c3 delegate to run_c2/run_a7/run_c3; AgentState gains user_id/user_role/permitted_agents/blocked/blocked_reason/remediation_requested; route_specialists intersects active_agents against permitted_agents"
affects: []

actuals:
  tokens: 9973
  tasks: 2
  commits: 2

tech-stack:
  added: []
  patterns:
    - "Node adapter shape (run_c2/run_a7/run_c3) mirrors the already-shipped run_c1/run_a2/run_a0: takes the graph state dict, performs no I/O of its own beyond what its delegate needs, returns a partial-state dict, never raises to the graph."
    - "RBAC reaches the fan-out as a data change through an unchanged conditional edge (route_specialists intersects active_agents against permitted_agents), the same pattern this module's docstring already established for A0's Phase 3 subset routing -- no topology edit."
    - "A blocked-request short-circuit lives at the top of run_a0 (the first node after C2 that would otherwise call a model), making 'blocked before it reaches an agent' mechanically true rather than merely narrated."

key-files:
  created:
    - backend/tests/test_graph_gateways.py
  modified:
    - backend/app/agents/a0_orchestrator.py
    - backend/app/agents/c2_gateway.py
    - backend/app/agents/a7_remediation.py
    - backend/app/agents/c3_gateway.py
    - backend/app/graph/state.py
    - backend/tests/test_graph_topology.py
    - backend/tests/test_hero_loop.py
    - backend/tests/test_hero_tracer.py

key-decisions:
  - "route_specialists' permitted_agents intersection defaults to state['active_agents'] itself (no restriction) when the permitted_agents key is entirely absent from state -- this only matters for a direct, C2-bypassing unit call to route_specialists (test_graph_topology.py's own three route_specialists tests call it standalone). Every real compiled_graph.ainvoke() runs C2 first, which always sets permitted_agents (to the RBAC set, or [] when blocked), so this default never masks a real RBAC decision. Without it, the plan's literal instruction (intersect against state.get('permitted_agents', [])) would silently zero out test_route_specialists_all_six_active_returns_six_sends and its two siblings, which the plan's own acceptance criterion requires to keep passing unedited."
  - "run_c3's zero-queued/zero-blocked case returns the exact pre-Phase-5 stub literal ('Execution complete. Actions queued for approval.') rather than a counts-naming sentence with zero in it -- required to keep test_graph_topology.py::test_ainvoke_completes_through_all_eleven_stub_nodes passing unedited (an explicit plan acceptance criterion), and defensible on its own terms: that path (a plain question, no remediation requested) genuinely has nothing to name. Routed to SENT-7-05."

patterns-established:
  - "Pattern: a node adapter's own docstring records why the graph-level gate (here, C2's RBAC) is defence in depth, not the only gate -- the graph is an in-process path with no HTTP identity of its own, and every write-capable HTTP route already enforces RBAC independently at the request boundary."

requirements-completed: [SAFE-01, SAFE-02, REM-01, REM-02]

coverage:
  - id: D1
    description: "run_c2 blocks a jailbreak query with a regex_match: reason and empty permitted_agents; a benign Auditor query permits exactly A1/A2; a benign IT System Manager query permits all seven; an unrecognised or absent role fails closed"
    requirement: SAFE-01
    verification:
      - kind: unit
        ref: "backend/tests/test_graph_gateways.py::test_run_c2_jailbreak_query_is_blocked_with_regex_reason, ::test_run_c2_benign_query_from_auditor_permits_a1_a2_only, ::test_run_c2_benign_query_from_it_system_manager_permits_all_seven, ::test_run_c2_unrecognised_role_fails_closed, ::test_run_c2_absent_role_key_fails_closed"
        status: pass
    human_judgment: false
  - id: D2
    description: "Through the real compiled graph: a jailbreak query is blocked before A0 attempts classification and before any specialist Send fires (guarded by a zero-route respx.mock context that fails loudly on any escaped call); an absent role is blocked the same way; an Auditor's query cannot fan out beyond A1/A2 even when A0's own classification names all six specialists"
    requirement: SAFE-01
    verification:
      - kind: integration
        ref: "backend/tests/test_graph_gateways.py::test_jailbreak_query_is_blocked_at_c2_and_no_specialist_runs, ::test_absent_role_is_blocked, ::test_auditor_role_cannot_fan_out_beyond_a1_a2"
        status: pass
    human_judgment: false
  - id: D3
    description: "run_a0 returns {'active_agents': [], 'user_intent': 'blocked'} without ever calling classify_intent when state['blocked'] is true, proven by a classifier stub that raises if called"
    requirement: SAFE-01
    verification:
      - kind: unit
        ref: "backend/tests/test_graph_gateways.py::test_run_a0_short_circuits_on_blocked_without_calling_classifier"
        status: pass
    human_judgment: false
  - id: D4
    description: "run_a7 produces no proposed_actions unless remediation_requested is explicitly true and the state is unblocked; synthesizes a real CREATE_CAPA_RECORD proposal when both conditions hold and an eligible (HIGH/MEDIUM/LOW) finding exists; drops a non-eligible finding without a placeholder -- proven both as a direct function call and through the wired graph"
    requirement: REM-01
    verification:
      - kind: unit
        ref: "backend/tests/test_graph_gateways.py::test_run_a7_produces_nothing_without_remediation_requested, ::test_run_a7_produces_nothing_when_blocked_even_with_remediation_requested, ::test_run_a7_synthesizes_when_remediation_requested_and_finding_eligible, ::test_run_a7_drops_non_eligible_findings_without_a_placeholder"
        status: pass
      - kind: integration
        ref: "backend/tests/test_graph_gateways.py::test_a7_does_not_synthesize_without_an_explicit_request"
        status: pass
    human_judgment: false
  - id: D5
    description: "run_c3 categorises proposed_actions via route_action and names queued/blocked counts, names blocked_reason when state is blocked, and returns the pre-Phase-5 stub literal for the zero/zero case"
    requirement: REM-02
    verification:
      - kind: unit
        ref: "backend/tests/test_graph_gateways.py::test_run_c3_zero_proposals_returns_legacy_stub_sentence, ::test_run_c3_counts_queued_and_blocked_categories, ::test_run_c3_blocked_state_names_the_blocked_reason"
        status: pass
    human_judgment: false
  - id: D6
    description: "The eleven-node topology and edge list are byte-identical to Phase 2's after wiring -- node set, edge set, and every pre-existing test_graph_topology.py assertion (unedited) all still pass"
    verification:
      - kind: unit
        ref: "backend/tests/test_graph_gateways.py::test_topology_is_unchanged_after_wiring; backend/tests/test_graph_topology.py (all 11 tests, unedited)"
        status: pass
    human_judgment: false

duration: 55min
completed: 2026-08-25
status: complete
---

# Phase 5 Plan 6: Wire C2/A7/C3 into the Compiled Graph Summary

**Tasks 1 and 2 are complete: the compiled LangGraph's last three stub nodes (C2, A7, C3) now delegate to the real Phase 5 modules, RBAC and injection detection are enforced before any specialist or model call, the eleven-node topology is unchanged, and 18 new tests prove it. Task 3 (human browser verification) is a `gate="blocking"` checkpoint — this plan STOPS here awaiting the developer's walkthrough; see "Human verification" below.**

## Performance

- **Duration:** ~55 min (including worktree fast-forward recovery)
- **Started:** 2026-08-25
- **Completed (Tasks 1-2):** 2026-08-25
- **Tasks:** 2 of 3 completed (Task 3 is the pending checkpoint)
- **Files modified:** 9 (1 created, 8 modified)

## Accomplishments

- `a0_orchestrator.py`: `_extract_user_query` renamed to the public `extract_user_query` (no other module referenced the private name); `run_a0` now returns immediately (`{"active_agents": [], "user_intent": "blocked"}`) when `state["blocked"]` is true, before attempting any classification — the first node after C2 and the first place this graph would otherwise call a model.
- `c2_gateway.py` gained `run_c2`: reads `user_role`/the user query, fails closed (`blocked=True`) on an absent or unrecognised role, runs `detect_injection` on a recognised role's query, and on success publishes `permitted_agents = sorted(PERMISSION_MATRIX[role])`.
- `a7_remediation.py` gained `run_a7`: returns `{"proposed_actions": []}` unless `state["remediation_requested"]` is explicitly true and the state is unblocked (D-03); otherwise iterates findings, looks each one's verdict up in `verification_results` by `finding_id`, and calls `synthesize_capa`, keeping only the proposals it actually returns.
- `c3_gateway.py` gained `run_c3`: categorises `proposed_actions` via `route_action`, counts `QUEUED_CATEGORIES`/`BLOCKED_CATEGORIES` membership, and composes a server-trusted `final_synthesis` sentence — naming `blocked_reason` when the state is blocked, and returning the pre-Phase-5 stub literal verbatim for the zero-queued/zero-blocked case (a deliberate backward-compatible decision — see Deviations).
- `graph/state.py`: `safety_gateway_c2`/`remediation_a7`/`action_gateway_c3` now delegate to `run_c2`/`run_a7`/`run_c3`, in the same one-line style `compliance_a2`/`evidence_verifier_c1` already established. `AgentState` gained six new fields (`user_id`, `user_role`, `permitted_agents`, `blocked`, `blocked_reason`, `remediation_requested`), none reduced (exactly one node writes each). `route_specialists` now intersects `active_agents` against `permitted_agents` — RBAC reaches the fan-out as a data change through the same unchanged conditional edge, no topology edit. The graph-assembly block (`add_node`/`add_edge`/`set_entry_point`/`compile`) was not touched.
- `test_graph_topology.py`/`test_hero_loop.py`/`test_hero_tracer.py`: each `_initial_state()` helper gained `user_id`/`user_role: "IT System Manager"` (C2 now fails closed on an absent role) — no other change to any of the three files; every pre-existing assertion in all three still passes unedited.
- `test_graph_gateways.py` (new, 18 tests): Task 1's adapter-level coverage (`run_c2`'s five behaviors, `run_a0`'s blocked short-circuit, `run_a7`'s three gate behaviors, `run_c3`'s three summary behaviors) plus Task 2's five wired-graph tests (`test_jailbreak_query_is_blocked_at_c2_and_no_specialist_runs`, `test_absent_role_is_blocked`, `test_auditor_role_cannot_fan_out_beyond_a1_a2`, `test_a7_does_not_synthesize_without_an_explicit_request`, `test_topology_is_unchanged_after_wiring`).
- Full backend suite: 312 passed, the same 13 pre-existing failures already logged in `deferred-items.md` (OPA-corroboration path, unrelated to this plan's scope) — confirmed identical before and after this plan's edits, 0 new failures, 0 fewer.

## Task Commits

1. **Task 1: Node adapters for C2, A7, C3, and A0's blocked short-circuit** — `c26a134` (feat)
2. **Task 2: Wire the three stub nodes, prove the topology is unchanged** — `86d8579` (feat)

**Plan metadata:** (this commit) — `docs(05-06): record Task 1/2 completion and Task 3 checkpoint`

## Files Created/Modified

- `backend/app/agents/a0_orchestrator.py` — `extract_user_query` (public rename), `run_a0`'s blocked short-circuit
- `backend/app/agents/c2_gateway.py` — `run_c2`
- `backend/app/agents/a7_remediation.py` — `run_a7`
- `backend/app/agents/c3_gateway.py` — `run_c3`
- `backend/app/graph/state.py` — three real delegates, six new `AgentState` fields, `route_specialists`' RBAC intersection
- `backend/tests/test_graph_gateways.py` — 18 new tests (adapter-level + wired-graph)
- `backend/tests/test_graph_topology.py` / `test_hero_loop.py` / `test_hero_tracer.py` — `_initial_state()` gains `user_id`/`user_role`

## Decisions Made

- **`route_specialists`' default-to-unrestricted when `permitted_agents` is absent.** See Deviations — required to keep `test_graph_topology.py`'s own three `route_specialists` unit tests passing unedited (an explicit plan acceptance criterion) while still enforcing RBAC correctly on every real `compiled_graph.ainvoke()`, since C2 always sets `permitted_agents` before `route_specialists` is ever reached in a real invocation.
- **`run_c3`'s zero-case legacy sentence.** See Deviations — required by the same "unedited pre-existing assertions" acceptance criterion, applied to `test_ainvoke_completes_through_all_eleven_stub_nodes`'s literal `final_synthesis` check.
- **`test_a7_does_not_synthesize_without_an_explicit_request` fakes `app.graph.state.run_c1`** rather than relying on the live OPA sidecar's corroboration to produce a HIGH/MEDIUM/LOW-graded real finding. See Deviations.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking issue] Worktree fast-forwarded to `main` before any edit**
- **Found during:** environment setup, before Task 1 could start
- **Issue:** This worktree (`worktree-agent-ad2ccdb106316c157`) forked from `f27e9bd`, an ancestor of `main` predating 05-01 through 05-05's merges — `backend/app/agents/c2_gateway.py`, `c3_gateway.py`, `a7_remediation.py` (all three of this plan's `depends_on` targets) did not exist on disk in this worktree.
- **Fix:** Verified `git merge-base --is-ancestor HEAD main` (clean fast-forward, no divergence, working tree clean) before running `git merge --ff-only main`. Adds commits only; nothing discarded. Matches the exact recovery pattern 05-02/05-04/05-05's own summaries each independently documented for the identical situation.
- **Files modified:** none directly (pure fast-forward, brought in 41 files from 05-01 through 05-05's already-merged commits)
- **Verification:** the full backend suite (294 passed, 13 pre-existing failures) matched the exact baseline 05-05-SUMMARY.md documented, immediately after the fast-forward and before any of this plan's own edits.
- **Committed in:** N/A (fast-forward merge, not a new commit on this branch)

**2. [Rule 4-adjacent, resolved without a checkpoint — see reasoning] `route_specialists` defaults to `active_agents` (no restriction) when `permitted_agents` is absent from state**
- **Found during:** Task 2, running `test_graph_topology.py`'s pre-existing `test_route_specialists_all_six_active_returns_six_sends`/`test_route_specialists_two_agent_subset_returns_two_sends`/`test_route_specialists_empty_active_agents_returns_empty_list` against the plan's literal instruction (`state.get("permitted_agents", [])`)
- **Issue:** The plan's literal instruction — default the intersection set to `[]` when `permitted_agents` is absent — would zero out every `Send` for these three pre-existing tests, which call `route_specialists(state)` directly with a state built by `test_graph_topology.py`'s own `_initial_state()` helper (which the plan explicitly instructs to add only `user_id`/`user_role`, not `permitted_agents`). This directly contradicts the plan's own acceptance criterion ("Every pre-existing test in `backend/tests/test_graph_topology.py` still passes with its assertions unedited").
- **Fix:** `permitted_agents` defaults to `state["active_agents"]` itself (i.e. no restriction) only when the key is entirely absent from `state`. This is inert for every real graph invocation — C2 always runs before `route_specialists` and always sets `permitted_agents` (to the RBAC-permitted set, or `[]` on a blocked request) — so the default only ever activates for a direct, C2-bypassing unit call, which is exactly the pre-existing tests' own calling convention. RBAC is not weakened by this default in any code path that actually reaches a human or a model call.
- **Files modified:** `backend/app/graph/state.py` (`route_specialists`, with the reasoning recorded in its own docstring)
- **Verification:** all three pre-existing `route_specialists` tests pass unedited; `test_auditor_role_cannot_fan_out_beyond_a1_a2` (this plan's own new graph-level test) independently proves the intersection still holds through a real `compiled_graph.ainvoke()`.
- **Committed in:** `86d8579`

**3. [Rule 1-adjacent — same class as Deviation 2] `run_c3`'s zero-queued/zero-blocked case returns the pre-Phase-5 stub literal verbatim**
- **Found during:** Task 2, running `test_ainvoke_completes_through_all_eleven_stub_nodes` (asserts `result["final_synthesis"] == "Execution complete. Actions queued for approval."`) against a first draft of `run_c3` that always composed a counts-naming sentence
- **Issue:** That test invokes the real graph with no `remediation_requested`, so `proposed_actions` is always empty — a counts-naming sentence for the zero case (e.g. "0 action(s) queued, 0 blocked") would not match this pre-existing, explicitly-required-to-stay-unedited literal assertion.
- **Fix:** `run_c3` returns the module's own pre-Phase-5 stub literal verbatim for the zero/zero case, and only composes a counts-naming sentence when there is something to name (queued or blocked > 0). Documented in `c3_gateway.py`'s module docstring and routed to SENT-7-05 (see Bible reconciliation below).
- **Files modified:** `backend/app/agents/c3_gateway.py`
- **Verification:** `test_ainvoke_completes_through_all_eleven_stub_nodes` passes unedited; `test_run_c3_counts_queued_and_blocked_categories` (this plan's own new test) independently proves the non-zero case composes a real counts sentence.
- **Committed in:** `c26a134`

**4. [Rule 3 - Blocking issue] `test_a7_does_not_synthesize_without_an_explicit_request` fakes `app.graph.state.run_c1` instead of relying on the live OPA sidecar**
- **Found during:** Task 2, first draft of this test invoking the real graph end to end against the live (seeded) `GXP-MFG-DEMO-01` system
- **Issue:** The live OPA policy bundle in this environment is already documented as stale/drifted (`.planning/phases/05-safety-remediation/deferred-items.md`, discovered during 05-05): `evaluate_opa_policy()` returns zero violations where the seeded Rego bundle should flag one, which drops `calculate_confidence`'s score by 100 for every real finding, grading every one `INSUFFICIENT_EVIDENCE` instead of `MEDIUM` — exactly the same root cause behind the 13 pre-existing failures in `test_hero_loop.py`/`test_hero_tracer.py`/`test_c1_verifier.py`/`test_opa_client.py`/`test_routes_findings.py`. Without a workaround, this plan's own new test would never see an eligible finding to prove A7's D-03 gate through the wired graph, purely because of this pre-existing, out-of-scope infra defect — not because of anything this plan's own code does.
- **Fix:** `app.graph.state.run_c1` is monkeypatched to a deterministic fake that grades every real finding `MEDIUM` with `opa_corroborated=True`, decoupling this test from the live OPA bundle's current state while still proving the thing this plan is actually responsible for (A7's gate holding through the real wired graph, reached via a real A2 check against real seeded Postgres data). `run_a7`'s own unit-level eligibility gate (`test_run_a7_synthesizes_when_remediation_requested_and_finding_eligible`) is unaffected and needs no such fake.
- **Files modified:** `backend/tests/test_graph_gateways.py` (test-only; no source-code workaround for the OPA bundle issue itself, which remains out of this plan's declared `<files>` scope, per the same executor scope-boundary rule 05-05 already applied)
- **Verification:** the test passes deterministically, independent of the live OPA container's current bundle state; the OPA drift itself remains logged in `deferred-items.md`, unchanged and unfixed by this plan (correctly — it is out of scope).
- **Committed in:** `86d8579`

---

**Total deviations:** 4 (1 recurring worktree-recovery pattern, 2 design decisions required by the plan's own literal "unedited pre-existing assertions" acceptance criteria, 1 test-isolation fix decoupling a new test from an already-logged, out-of-scope OPA infra defect). **Impact:** None touched files outside this plan's declared scope. Deviations 2 and 3 are the executor's own reasoned resolution of an internal contradiction in the plan text (the literal `state.get("permitted_agents", [])` instruction vs. the "pre-existing assertions pass unedited" acceptance criterion) — both are documented in the affected module's own docstring, not silently smoothed over.

### Bible reconciliations (collected across Phase 5, routed to SENT-7-05, per this plan's `<output>` requirement)

From 05-01:
1. **Canonical-field-list correction (`audit_trail.py`)** — `verify_chain()`'s read-side/write-side `canonical_data` construction is driven off one fixed `CANONICAL_FIELDS` tuple instead of the Bible's two different key-set constructions, which produced a false `TAMPERED` verdict for an event omitting an optional key.
2. **A7 deterministic fallback (`a7_remediation.py`)** — Bible Section 2's "Returns an empty array of proposed actions" failure behaviour is preserved for the no-C1-eligible-finding case; a router-degrade on an otherwise-eligible finding instead falls back to `_deterministic_capa`, a template-narrative proposal.
3. **`GXP_RELEVANT_WRITE` queue reconciliation (`c3_gateway.py`)** — reconciles Bible Section 2's two conflicting statements ("Blocked. Requires out-of-band execution" vs. the C3 Workflow's `PENDING -> Approve -> Executes` line); both queued categories are inserted `PENDING_APPROVAL`, with `GXP_RELEVANT_WRITE` stopping at `APPROVED` (execution out of band) and `MOCK_WRITE_LOW_RISK` reaching `EXECUTED` via mock execution.

From 05-03:
4. **`demonstrate_tamper`'s `NO_SUCH_EVENT` correction (`audit_trail.py`)** — the Bible's own reference implementation returns a false `VERIFIED` for a tamper attempt against a nonexistent `event_id` (zero rows affected, chain genuinely untouched); this plan's implementation parses asyncpg's own command tag to detect the zero-row case and reports `NO_SUCH_EVENT` instead of calling `verify_chain` at all.

From 05-04:
5. **`A7_DEFAULT_OWNER = "IT System Manager"`** — the Bible's `CAPAProposal.owner` field has no Bible-specified default; reasoned from the Bible's own permission matrix (the only role that can both trigger A7 and approve its output).
6. **`approved_by`/`approved_at` reuse for rejection** — one decision-provenance pair per proposal, not a second half-populated `rejected_by`/`rejected_at` pair; the reject route itself was not Bible-specified.
7. **`PROPOSAL_BLOCKED` audit logging for a PROHIBITED attempt** — the Bible states only "Blocked immediately" for PROHIBITED, without stating the attempt is logged; this project's reading of 21 CFR 11.10(e) (05-01's Assumption A5, extended by 05-04's `describe_category` citation in the audit row's `output_summary`).

From 05-06 (this plan):
8. **`run_c3`'s zero-queued/zero-blocked case returns the pre-Phase-5 stub literal verbatim** — see Deviation 3 above. Not a Bible-text contradiction so much as an internal-consistency choice this plan's own acceptance criteria forced; recorded here per this plan's own `<output>` instruction to collect every Phase 5 deviation in one place.

(05-02 and 05-05 introduced no Bible reconciliations of their own — both summaries confirmed with no `SENT-7-05`-routed section.)

## Issues Encountered

- **Worktree base mismatch (recovered non-destructively), same recurring pattern every wave-2/wave-3/wave-4 plan in this phase has independently hit and documented.** See Deviation 1.
- **Executor self-correction, no lasting effect:** partway through initial exploration, several `Read`/`Bash` calls were mistakenly issued against the main checkout's absolute path (`...\Sentinel_AI\backend`) instead of this worktree's own path (`...\Sentinel_AI\.claude\worktrees\agent-ad2ccdb106316c157\backend`) — caught before any `Edit`/`Write` was attempted (the `Edit` tool itself refused a main-checkout path outright), and before any commit. The venv and baseline test run performed against the main checkout were re-run correctly against the worktree once caught; no file in the main checkout was touched, and no worktree state was lost.
- **Live OPA sidecar corroboration is currently broken in this shared demo environment** (documented in `deferred-items.md` since 05-05, unchanged by this plan) — every real finding against the seeded `GXP-MFG-DEMO-01` system currently grades `INSUFFICIENT_EVIDENCE` instead of `MEDIUM`. This plan's own new graph-level A7 test works around it (Deviation 4) rather than fixing it, since the fix belongs to `app/opa_client.py`/`infra/opa/*`, outside this plan's declared `<files>`.

## User Setup Required

None for Tasks 1-2 — no external service configuration required (Postgres/OPA/Qdrant were already running via `docker compose` from a prior session; confirmed healthy before this plan's work began).

**For Task 3 (see "Human verification" below):** the checkpoint's own `<what-built>` instructs the executor to bring the stack up (`docker compose up -d postgres qdrant opa`, `bash infra/apply-migrations.sh`, start the backend on port 8000 and the frontend on port 3000) before presenting the checklist. `postgres`/`opa`/`qdrant` are already confirmed running and healthy in this shared environment, and migrations are already applied (the `action_proposals` table 05-01 added is already in active use by every passing integration test in this and prior Phase 5 plans). Starting a long-running backend/frontend dev server was deliberately **not** done from inside this ephemeral worktree — this worktree is removed once this plan returns, and the code a human needs to verify against is this plan's own commits (`c26a134`, `86d8579`), which only become durably reachable once merged. The backend/frontend startup step should be run from the merged checkout (`main`, once this wave's merge lands) immediately before the human walks the checklist.

## Human verification

**Status: PENDING — Task 3 is a `gate="blocking"` checkpoint. This plan STOPS here.**

Per the standard checkpoint protocol (`workflow.auto_advance` is `false` in `.planning/config.json`, and no `_auto_chain_active` override is set), this is not an auto-approvable checkpoint. Tasks 1 and 2 are fully complete, committed, and verified (18 new tests, 0 regressions across the full backend suite). Task 3 requires a human to walk the following nine items in a real browser at `http://localhost:3000`, once the stack is running against this plan's merged code:

1. The role selector is visible in the app chrome on every page and shows `IT System Manager`, `QA/Compliance`, `Auditor`.
2. As `Auditor`, open `/findings` and click Generate CAPA — the permission sentence from the UI contract appears inline, and no proposal is created.
3. Switch to `IT System Manager` and click Generate CAPA on the same finding — a confirmation naming a proposal id appears.
4. With `/actions` open in a second tab during step 3, the new proposal appears there with no manual refresh and the live indicator shows connected.
5. On `/actions`, the card shows ACTION TYPE, CATEGORY, TARGET SYSTEM, JUSTIFICATION, PAYLOAD and a `PENDING_APPROVAL` badge; a large payload scrolls inside its box rather than stretching the page.
6. Click Reject on one proposal — the confirmation names that proposal's own action type and target system, and after confirming, the badge reads `REJECTED`.
7. Click Approve on another — the button reads `Approving...` while in flight and the badge lands on `APPROVED` or `EXECUTED`.
8. `curl -s http://127.0.0.1:8000/api/audit/verify` reports `VERIFIED`; then run the tamper demo against one of the event ids just created and confirm it reports `TAMPERED` with a `broken_at_index`.
9. Nothing on `/`, `/copilot`, `/blast-radius`, or `/findings` regressed visually from Phase 4.

**Resume signal:** Type "approved" or describe which of the nine items failed and what you saw.

## Next Phase Readiness

- Once Task 3's checkpoint clears, Phase 5 (Safety & Remediation) is fully complete across all six plans: C2 RBAC + injection detection (05-01/05-02, now wired into both the HTTP routes and the compiled graph), the hash-chained audit trail with tamper detection (05-01/05-03), C3 five-category routing + A7 CAPA synthesis with reject path (05-01/05-04), the live WebSocket-pushed Action/Approval Centre (05-05), and this plan's graph-level RBAC/injection/D-03 wiring (05-06).
- No blockers for a continuation agent picking up after the checkpoint: Tasks 1 and 2 are committed on this worktree's branch (`c26a134`, `86d8579`), ready to merge.

## Self-Check: PASSED

- `backend/app/agents/a0_orchestrator.py` contains `extract_user_query` (public): **FOUND**
- `backend/app/agents/c2_gateway.py` contains `run_c2`: **FOUND**
- `backend/app/agents/a7_remediation.py` contains `run_a7`: **FOUND**
- `backend/app/agents/c3_gateway.py` contains `run_c3`: **FOUND**
- `backend/app/graph/state.py` delegates all three via `run_c2`/`run_a7`/`run_c3`: **FOUND**
- `backend/tests/test_graph_gateways.py` exists on disk with 18 tests: **FOUND**
- Commit `c26a134` exists in `git log`: **FOUND**
- Commit `86d8579` exists in `git log`: **FOUND**
- Plan `<verification>` items 1-3 re-run: `cd backend && .venv/Scripts/python.exe -m pytest` — 312 passed, 13 pre-existing failures (unchanged from baseline, see Deviations) — **PASS** (no regression); `python -c "from app.graph.state import graph; print(len(graph.nodes))"` — `11` — **PASS**; `test_topology_is_unchanged_after_wiring` passes and every pre-existing `test_graph_topology.py` assertion passes unedited — **PASS**
- Plan `<verification>` item 4 (human verification checklist answered and recorded): **PENDING — Task 3 checkpoint not yet reached by a human**
- Plan `<must_haves><truths>` re-checked (Tasks 1-2 scope): jailbreak query blocked, no specialist/model call reaches it — **PASS**; Auditor cannot fan out to A3-A6 even when A0 selects them — **PASS**; A7 does not synthesize inside the graph unless remediation was explicitly requested (D-03) — **PASS**; eleven-node topology/edge list byte-identical to Phase 2's, existing topology assertions pass unchanged — **PASS**; "the full Monitor-to-Audit Phase 5 surface is walkable by a human in the browser end to end" — **PENDING (Task 3)**

---
*Phase: 05-safety-remediation*
*Tasks 1-2 completed: 2026-08-25*
*Task 3: awaiting human checkpoint*
