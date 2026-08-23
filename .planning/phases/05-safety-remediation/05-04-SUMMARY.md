---
phase: 05-safety-remediation
plan: 04
subsystem: safety-remediation
tags: [c3-action-gateway, a7-remediation, fastapi, rbac, ast-gates, tdd, capa]

# Dependency graph
requires:
  - phase: 05-safety-remediation
    provides: "05-01: c3_gateway.py (ACTION_CATEGORIES/QUEUED_CATEGORIES/route_action/persist_proposal), a7_remediation.py (A7_ELIGIBLE_CONFIDENCE/synthesize_capa), routes/actions.py (generate-capa/GET/approve), identity.py, audit_trail.py"
provides:
  - "c3_gateway.py: BLOCKED_CATEGORIES, CATEGORY_DISPOSITIONS, describe_category — all five Bible categories now provably reachable and asserted"
  - "a7_remediation.py: structured payload['capa'] carrying all six CAPAProposal fields; due_date/owner computed server-side; JSON-narrative request with malformed-output fallback"
  - "routes/actions.py: POST /api/actions/{proposal_id}/reject — mirrors approve's exact guard order, mutually terminal with approve (HTTP 409)"
  - "AST gates proving C3 has zero model dependency, A7 never imports the verifier, A7 does import call_llm (deterministic-first boundary, both sides)"
affects: [05-05, 05-06]

actuals:
  tokens: 13252
  tasks: 3
  commits: 5

tech-stack:
  added: []
  patterns:
    - "AST-based no-model-dependency / no-verifier-dependency gates: parse the module's own source with `ast`, walk Import/ImportFrom nodes, assert on literal import names — proves the constraint from the module's actual source rather than its current runtime import graph"
    - "Structural/date fields (CAPAProposal.due_date, .owner) computed in Python server-side; only the narrative sub-fields (root_cause, corrective_action, preventive_action, effectiveness_check) come from the model, requested as `json_output=True` JSON with a malformed-output fallback identical to a degraded router"
    - "Injecting a fail-closed category through the real frozen allowlist (`monkeypatch.setitem(c3_gateway.ACTION_CATEGORIES, ...)`) rather than monkeypatching the routing function itself, so the negative test still exercises the real `route_action`"

key-files:
  created:
    - backend/tests/test_c3_gateway.py
    - backend/tests/test_a7_remediation.py
  modified:
    - backend/app/agents/c3_gateway.py
    - backend/app/agents/a7_remediation.py
    - backend/app/routes/actions.py
    - backend/tests/test_routes_actions.py

key-decisions:
  - "A7_DEFAULT_OWNER = \"IT System Manager\": the Bible's own permission matrix names IT System Manager as the only role that can both trigger A7 and approve its output, making it the reasoned deterministic default CAPAProposal.owner. Not a literal Bible value — routed to SENT-7-05."
  - "A7's JSON-structured narrative request (json_output=True, four fixed keys) mirrors a0_orchestrator.classify_intent's already-shipped pattern rather than inventing a new one; a JSON-parse or missing-key failure is treated identically to a degraded router — this system never persists a CAPA built from unparseable model output."
  - "approve/reject reuse approved_by/approved_at for decision provenance rather than adding rejected_by/rejected_at — one decision-provenance pair per proposal, not two half-populated ones. Routed to SENT-7-05."

patterns-established:
  - "Pattern: a Critical-review module's fail-closed default is proven both positively (all named categories reachable, asserted against an independently transcribed literal set) and negatively (a parametrised sweep of empty/whitespace/wrong-case/plausible-but-unmapped inputs all resolve to the same safe default)."

requirements-completed: [REM-01, REM-02, REM-03]

coverage:
  - id: D1
    description: "C3: all five Bible action categories reachable and asserted as a literal set; unknown action_type fails closed to PROHIBITED across empty/whitespace/wrong-case/unmapped shapes; describe_category transcribes Bible Section 2's dispositions verbatim, KeyError on unknown category"
    requirement: REM-02
    verification:
      - kind: unit
        ref: "backend/tests/test_c3_gateway.py (26 tests, all pass)"
        status: pass
    human_judgment: false
  - id: D2
    description: "C3 has zero model dependency (AST gate) and persist_proposal binds every value through a $N placeholder — proven with a live SQL-metacharacter round-trip, not just believed"
    requirement: REM-02
    verification:
      - kind: unit
        ref: "backend/tests/test_c3_gateway.py::test_c3_module_has_no_model_dependency"
        status: pass
      - kind: integration
        ref: "backend/tests/test_c3_gateway.py::test_persist_proposal_binds_every_value"
        status: pass
    human_judgment: false
  - id: D3
    description: "A7 synthesizes CAPA proposals only from C1-eligible confidence grades (HIGH/MEDIUM/LOW), fails closed on INSUFFICIENT_EVIDENCE and every unrecognised grade including the UNVERIFIED adjacent-field trap; never imports the verifier (AST gate); does import call_llm (positive counterpart AST gate)"
    requirement: REM-01
    verification:
      - kind: unit
        ref: "backend/tests/test_a7_remediation.py (18 tests, all pass, including test_a7_never_imports_the_verifier and test_a7_is_the_only_module_permitted_a_model_call_in_this_phase)"
        status: pass
    human_judgment: false
  - id: D4
    description: "A7's CAPA payload is structurally complete: payload['capa'] carries exactly the six CAPAProposal field names; due_date is computed server-side, exactly 30 days from synthesis; a degraded router or malformed JSON narrative both fall back to the same deterministic CAPA with model_id='deterministic-fallback'; the prompt labels the finding's claim as untrusted data"
    requirement: REM-01
    verification:
      - kind: unit
        ref: "backend/tests/test_a7_remediation.py::test_capa_payload_has_exactly_the_six_capa_proposal_field_names, ::test_capa_due_date_is_exactly_thirty_days_out, ::test_degraded_router_still_produces_a_proposal_with_fallback_attribution, ::test_malformed_json_narrative_falls_back_to_deterministic_capa, ::test_prompt_labels_finding_text_as_untrusted"
        status: pass
      - kind: integration
        ref: "backend/tests/test_routes_actions.py::test_full_approval_loop (re-verified green against the new CAPA structure)"
        status: pass
    human_judgment: false
  - id: D5
    description: "A human can reject a pending proposal (POST /api/actions/{id}/reject); reject reaches REJECTED and is audit-logged (ACTION_REJECTED); approve and reject are mutually terminal (each returns 409 after the other decided); reject is RBAC-gated identically to approve"
    requirement: REM-03
    verification:
      - kind: integration
        ref: "backend/tests/test_routes_actions.py::test_reject_moves_proposal_to_rejected_and_audits, ::test_approve_after_reject_returns_409, ::test_reject_after_approve_returns_409, ::test_reject_denied_for_auditor_role"
        status: pass
    human_judgment: false
  - id: D6
    description: "A PROHIBITED routing decision is never queued to action_proposals and is instead recorded as a PROPOSAL_BLOCKED audit event, proven by injecting PROHIBITED through the real c3_gateway.ACTION_CATEGORIES allowlist (not by monkeypatching route_action itself); every ActionProposalRecord response field traces to a database column or to route_action's derived category — no field is generated at render time"
    requirement: REM-03
    verification:
      - kind: integration
        ref: "backend/tests/test_routes_actions.py::test_prohibited_proposal_is_never_queued, ::test_approval_response_is_server_trusted"
        status: pass
    human_judgment: false

duration: 32min
completed: 2026-08-23
status: complete
---

# Phase 5 Plan 4: C3/A7 Critical-Review Coverage + Reject Path Summary

**All five Bible action categories are now provably reachable with a fail-closed default, A7's CAPA proposals carry a complete six-field structured payload with a server-computed 30-day due date, and a human can reject a pending proposal exactly as they can approve one — REJECTED is audit-logged and mutually terminal with APPROVED.**

## Performance

- **Duration:** ~32 min
- **Started:** 2026-08-23T23:06:00+05:30 (after worktree base recovery, see Issues Encountered)
- **Completed:** 2026-08-23T23:38:29+05:30
- **Tasks:** 3 of 3 completed
- **Files modified:** 6 (2 created, 4 modified)

## Accomplishments

- `c3_gateway.py` gained `BLOCKED_CATEGORIES`, `CATEGORY_DISPOSITIONS`, and `describe_category` — the Bible's five one-line category dispositions are now transcribed verbatim and served through a function that raises `KeyError` rather than returning a placeholder for an unknown category. `set(ACTION_CATEGORIES.values())` already covered all five categories from 05-01; a full unit suite (26 tests) now asserts this as a literal fact plus an AST gate proving the module imports no model client.
- `a7_remediation.py`'s `synthesize_capa` now returns a structurally complete CAPA: `payload["capa"]` carries exactly the six `CAPAProposal` field names (`root_cause`, `corrective_action`, `preventive_action`, `effectiveness_check`, `due_date`, `owner`). `due_date`/`owner` are computed in Python, never parsed from model prose; the four narrative fields are requested as `json_output=True` JSON (mirroring `a0_orchestrator.classify_intent`'s already-shipped pattern) and a malformed or missing-key response degrades to the exact same deterministic fallback as a degraded router. 18 tests cover this, including two AST gates (never imports the verifier; does import `call_llm`).
- `routes/actions.py` gained `POST /api/actions/{proposal_id}/reject`, sharing `approve_action`'s exact guard order (RBAC → pool → row lookup → status guard) and reusing `approved_by`/`approved_at` for decision provenance. The blocked-attempt audit path in `generate_capa` (already present from 05-01) now cites `describe_category`'s Bible text in its `output_summary`. 6 new integration tests cover the reject path, mutual-terminal 409s, RBAC denial, a real PROHIBITED routing decision never reaching the queue, and every `ActionProposalRecord` response field tracing to a database column or to `route_action`'s derived category.
- Full backend suite: 272 passed, 0 regressions.

## Task Commits

Tasks 1 and 2 (`tdd="true"`) each produced a RED test commit followed by a GREEN implementation commit; Task 3 (`type="auto"`, no TDD gate) produced a single commit with tests and implementation together.

1. **Task 1, RED** - `66315ae` (test: add failing test for C3 Critical-review coverage)
2. **Task 1, GREEN** - `cc373ed` (feat: BLOCKED_CATEGORIES, describe_category)
3. **Task 2, RED** - `41b185f` (test: add failing test for A7 Critical-review coverage)
4. **Task 2, GREEN** - `d1e46b7` (feat: structured CAPA, thirty-day due_date)
5. **Task 3** - `27b3f9c` (feat: reject path and server-trusted approval-response guarantee)

**Plan metadata:** (this commit) - `docs(05-04): complete C3/A7 Critical-review coverage plan`

## Files Created/Modified

- `backend/tests/test_c3_gateway.py` - 26 tests: five-category routing, fail-closed default, `describe_category`, AST no-model-dependency gate, live-Postgres SQL-binding proof
- `backend/tests/test_a7_remediation.py` - 18 tests: confidence-eligibility fail-closed gate, six-field CAPA payload, thirty-day due_date, deterministic-fallback attribution, untrusted-prompt labelling, two AST gates
- `backend/app/agents/c3_gateway.py` - `BLOCKED_CATEGORIES`, `CATEGORY_DISPOSITIONS`, `describe_category`
- `backend/app/agents/a7_remediation.py` - `CAPA_NARRATIVE_FIELDS`, `A7_DEFAULT_OWNER`, `_capa_due_date`, `_compose_justification`, `_build_capa_payload`; `synthesize_capa` now requests JSON-structured narrative and falls back on malformed output
- `backend/app/routes/actions.py` - `reject_action` route; blocked-attempt `output_summary` now cites `describe_category`
- `backend/tests/test_routes_actions.py` - 6 new tests (extends 05-01's suite): reject/approve mutual-terminal 409s, auditor-denied reject, PROHIBITED-never-queued (injected through the real allowlist), server-trusted response field audit

## Decisions Made

- `A7_DEFAULT_OWNER = "IT System Manager"`: reasoned from the Bible's own permission matrix (only role that can both trigger A7 and approve), not a literal Bible value. Routed to SENT-7-05.
- A7's narrative request uses `json_output=True` with four fixed keys, mirroring `a0_orchestrator.classify_intent`'s already-shipped structured-output pattern rather than inventing a new one for this module.
- `approve`/`reject` reuse `approved_by`/`approved_at` rather than adding a second `rejected_by`/`rejected_at` pair — one decision-provenance pair per proposal. Routed to SENT-7-05.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Test payload exceeded `action_type VARCHAR(50)` before it could prove the SQL-binding claim**
- **Found during:** Task 1, first `pytest tests/test_c3_gateway.py` run against the real implementation
- **Issue:** `test_persist_proposal_binds_every_value`'s original SQL-metacharacter payload (`"CREATE_CAPA_RECORD'; DROP TABLE action_proposals; --"`) was longer than the real `action_type VARCHAR(50)` column, raising `asyncpg.exceptions.StringDataRightTruncationError` instead of proving the binding claim.
- **Fix:** Shortened the payload to `"X'; DROP TABLE action_proposals; --"` (36 chars), which still exercises the same metacharacter-round-trip proof without hitting the column's own length constraint.
- **Files modified:** `backend/tests/test_c3_gateway.py`
- **Verification:** `test_persist_proposal_binds_every_value` passes; full `test_c3_gateway.py` suite green (26/26).
- **Committed in:** `cc373ed` (part of Task 1's GREEN commit)

**2. [Rule 1 - Bug] Plan's own `app.routes` acceptance-criteria check does not work against this repo's installed FastAPI/Starlette version**
- **Found during:** Task 3, running the plan's literal acceptance command `python -c "from app.main import app; print('/api/actions/{proposal_id}/reject' in {getattr(r,'path','') for r in app.routes})"`
- **Issue:** The command printed `False` even though the route exists and is fully functional (proven by 18 passing `TestClient`-level tests hitting it directly). `fastapi==0.141.1`'s `app.routes` wraps each `include_router()`-registered router in an `_IncludedRouter` object that does not expose `.path` the way a flattened `APIRoute` list historically did — this is a version-specific FastAPI internal-representation change, not a defect in `routes/actions.py`.
- **Fix:** No code fix needed (nothing was actually wrong). Verified the route is registered via `app.openapi()['paths']`, which correctly lists `/api/actions/{proposal_id}/reject` alongside `/api/actions` and `/api/actions/{proposal_id}/approve`. Documented here so a future re-run of the plan's literal command is not mistaken for a regression.
- **Files modified:** none (verification-method finding only)
- **Verification:** `app.openapi()['paths']` contains the route; all reject-path `TestClient` tests pass.
- **Committed in:** N/A (no code change; recorded here for the audit trail)

**3. [Rule 2 - Missing critical] A7 never persists a CAPA built from unparseable model output**
- **Found during:** Task 2, designing the JSON-structured narrative request
- **Issue:** The plan's behavior list only names "when the router degrades" as the fallback trigger. A router response that is nominally successful (HTTP 200) but whose text is not valid JSON, or is missing one of the four required narrative keys, would otherwise flow through as a broken CAPA structure — a correctness gap the plan did not explicitly rule out but that REM-01's "never unverified/malformed claims reach a write" thesis clearly forbids.
- **Fix:** A JSON-decode or missing-key failure is caught and routed to the exact same `_deterministic_capa` fallback as a degraded router, with the same `model_id = "deterministic-fallback"` attribution.
- **Files modified:** `backend/app/agents/a7_remediation.py`
- **Verification:** `test_malformed_json_narrative_falls_back_to_deterministic_capa` passes.
- **Committed in:** `d1e46b7` (Task 2's GREEN commit)

---

**Total deviations:** 3 (1 self-contained test-authoring bug fix, 1 verification-method finding with no code change, 1 Rule 2 missing-critical addition). **Impact:** None touched files outside this plan's declared scope; the Rule 2 addition is necessary for REM-01's own correctness guarantee, not scope creep.

### Bible reconciliations (routed to SENT-7-05)

1. **`CATEGORY_DISPOSITIONS` / `describe_category`** — new symbols, not a reconciliation of conflicting Bible text, but worth noting: the five disposition strings are transcribed verbatim from Bible Section 2's C3 "Categories" list.
2. **`A7_DEFAULT_OWNER`** — the Bible's `CAPAProposal.owner` field has no Bible-specified default value; `"IT System Manager"` is this project's reasoned default (see Decisions Made above).
3. **`approved_by`/`approved_at` reuse for rejection** — a `reject_action` route was not itself specified by the Bible (05-RESEARCH.md Open Question 3); reusing the existing approval-provenance columns rather than adding a second pair is this plan's own schema-economy choice.
4. **PROHIBITED-blocked audit logging** (`PROPOSAL_BLOCKED`) — already implemented in 05-01 as 05-RESEARCH.md Assumption A5 (Bible Section 2 says only "Blocked immediately" for PROHIBITED, without stating the attempt is logged); this plan's Task 3 extends that existing path's `output_summary` to cite `describe_category`'s Bible text, and re-records the reconciliation here per this plan's own `<output>` instruction.

## Issues Encountered

- **Worktree base mismatch (recovered non-destructively).** This worktree's branch (`worktree-agent-a595071da2063f492`) forked from `f27e9bd`, an ancestor of `main` that predates 05-01's merge (`550a218`) — the exact plan this plan depends on. `git merge-base --is-ancestor HEAD main` confirmed a clean fast-forward relationship (no divergence, no discarded work), so `git merge --ff-only main` was used to catch up before any implementation work began. This is a pure catch-up (adds commits, discards nothing) and is explicitly distinct from the prohibited `git reset --hard`/`git update-ref` self-recovery patterns. Recorded here per the worktree-safety guidance: a future orchestrator run should confirm the wave-2 dispatch's pre-dispatch base-check (#2649) is firing correctly so this recovery step is not needed again.
- **Shared-Postgres password contention across parallel wave-2 agents.** The live `sentinel` Postgres role's password intermittently mismatched the shared root `.env`'s documented `POSTGRES_PASSWORD` value during this session — consistent with sibling worktree agents (05-02/05-03) also running against the same single Docker container and independently discovering/fixing the same 05-01-documented password gap. Resolved non-destructively each time via `ALTER USER sentinel WITH PASSWORD 'replace_me_local_dev_only'` (matching the shared root `.env`'s own declared value, never a value only this worktree would know) and by re-running the affected test module. No data was touched; only the role's password was reset to the value the shared config file already declares. This is an environment-contention artifact of three worktrees sharing one Docker Postgres instance, not a defect in this plan's code — flagged for `/gsd-execute-phase`'s wave-cleanup awareness.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- C3 and A7 now meet the Critical-review bar CLAUDE.md Rule 6 requires (unit + negative + edge-case + integration coverage, both AST-verified deterministic-first boundaries), and 05-RESEARCH.md Open Question 3 (reject path) is resolved.
- `routes/actions.py` now exposes the full decision surface (`generate-capa`, `GET /api/actions`, `approve`, `reject`) that 05-05 (WS push + frontend Approval Centre) and 05-06 (graph node wiring) can build against — the reject button 05-UI-SPEC.md already styles can now be wired live rather than hidden.
- No blockers.

## Self-Check: PASSED

- `backend/tests/test_c3_gateway.py` exists on disk: **FOUND**
- `backend/tests/test_a7_remediation.py` exists on disk: **FOUND**
- `backend/tests/test_routes_actions.py` exists on disk: **FOUND**
- Commit `66315ae` exists in `git log`: **FOUND**
- Commit `cc373ed` exists in `git log`: **FOUND**
- Commit `41b185f` exists in `git log`: **FOUND**
- Commit `d1e46b7` exists in `git log`: **FOUND**
- Commit `27b3f9c` exists in `git log`: **FOUND**
- Plan `<verification>` block re-run: (1) `cd backend && python -m pytest tests/test_c3_gateway.py tests/test_a7_remediation.py tests/test_routes_actions.py -x` — 62 passed — **PASS**; (2) `cd backend && python -m pytest` — 272 passed — **PASS**; (3) `set(ACTION_CATEGORIES.values())` equals the five Bible categories — **PASS**
- Plan `<must_haves><truths>` re-checked: all five categories reachable, unknown fails closed to PROHIBITED — **PASS**; PROHIBITED never reaches `action_proposals`, recorded as `PROPOSAL_BLOCKED` — **PASS**; A7 produces no proposal for `INSUFFICIENT_EVIDENCE`, produces one for HIGH/MEDIUM/LOW — **PASS**; A7 never calls C1's verifier (AST-proven) — **PASS**; reject reaches REJECTED, is audit-logged, and can never afterwards be approved — **PASS**; every approval-queue response field traces to a DB column or the frozen allowlist — **PASS**

---
*Phase: 05-safety-remediation*
*Completed: 2026-08-23*
