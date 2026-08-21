---
phase: 03-intelligence-retrieval
plan: 04
subsystem: api
tags: [postgres, asyncpg, langgraph, compliance-agent, opa, seed-data, pytest]

requires:
  - phase: 03-intelligence-retrieval
    provides: "03-02's hero tracer — real A2/C1 wired end to end, db.py, llm_router.py, one deterministic check (verify_periodic_eval_current)"
provides:
  - "All three Bible-named A2 deterministic checks (verify_urs_approved, verify_periodic_eval_current, verify_test_traceability), A2_CHECKS tuple, multi-gap finding assembly in run_a2"
  - "Additive, idempotent infra/postgres/seed/002_urs_fixture.sql seeding a real APPROVED URS document (DOC-2026-URS-01) for GXP-MFG-DEMO-01 (D-05)"
  - "Glob-driven infra/apply-seed.sh applying every seed script in sorted order"
  - "backend/tests/test_a2_compliance.py — 11 tests covering all three checks' pass/fail paths"
  - "A discovered, documented pre-existing defect in c1_verifier.py's build_opa_payload() for multi-input-key Rego rules, recorded in .planning/WINDOWS.md"
affects: [03-03, 03-05, 03-06, future-c1-hardening]

actuals:
  tokens: 11258
  tasks: 2
  commits: 3

tech-stack:
  added: []
  patterns:
    - "A2_CHECKS data-driven iteration: run_a2 loops a tuple of check functions in the Bible's own listed order rather than repeating call sites, so a future check has exactly one registration point"
    - "Transaction-insert-then-rollback test fixtures (asyncpg conn.transaction(), manual tr.start()/tr.rollback()) for exercising positive/negative paths the committed seed data doesn't provide, without ever mutating the shared demo database"

key-files:
  created:
    - infra/postgres/seed/002_urs_fixture.sql
    - backend/tests/test_a2_compliance.py
  modified:
    - infra/apply-seed.sh
    - infra/verify-seed.sh
    - infra/README.md
    - backend/app/agents/a2_compliance.py
    - backend/tests/test_hero_tracer.py

key-decisions:
  - "Seeded one additive APPROVED URS document (DOC-2026-URS-01) rather than accepting negative-only coverage for verify_urs_approved's positive path (D-05, resolves 03-RESEARCH.md Open Question 1) — a Critical-adjacent agent should not ship an untested positive path when a one-row fixture closes the gap cheaply."
  - "verify_urs_approved reuses rule 1's ANNEX11-S4-DOC-001 citation, generalized from doc_type='O&M' to doc_type='URS' — same regulatory citation, narrower doc-type scope than the closed Rego rule fires on, so C1 correctly returns INSUFFICIENT_EVIDENCE for it. Documented as an intentional deterministic-first outcome, not patched by editing the closed Phase-2 policy bundle."
  - "build_finding's null-record path now yields empty evidence_ids and a NO-RECORD finding_id marker instead of the tracer's original 'unknown' placeholder — the plan's <behavior> spec required this and it applies retroactively to verify_periodic_eval_current's own no-record case too."
  - "Discovered a pre-existing c1_verifier.py defect (build_opa_payload queries every rule-input table by the finding's own evidence_ids, which breaks any multi-input-key rule) during this plan's execution. Documented and test-asserted as real behavior rather than fixed, because c1_verifier.py is explicitly out of this plan's Rule 10 file boundary; routed to .planning/WINDOWS.md and a future C1-hardening plan."

patterns-established:
  - "Seed directory is glob-applied in sorted filename order (001_seed.sql, 002_*, ...) rather than a single hardcoded filename, so later plans can add NNN_*.sql fixtures without touching apply-seed.sh again."

requirements-completed: [ORC-03]

coverage:
  - id: D1
    description: "verify_urs_approved and verify_test_traceability run as parameterized Postgres queries with both pass and fail paths tested"
    requirement: "ORC-03"
    verification:
      - kind: unit
        ref: "backend/tests/test_a2_compliance.py#test_verify_urs_approved_passes_against_seeded_approved_row"
        status: pass
      - kind: unit
        ref: "backend/tests/test_a2_compliance.py#test_verify_urs_approved_fails_with_null_record_when_no_urs_document"
        status: pass
      - kind: unit
        ref: "backend/tests/test_a2_compliance.py#test_verify_urs_approved_fails_when_urs_document_not_approved"
        status: pass
      - kind: unit
        ref: "backend/tests/test_a2_compliance.py#test_verify_test_traceability_fails_naming_urs_042_draft_test_case"
        status: pass
      - kind: unit
        ref: "backend/tests/test_a2_compliance.py#test_verify_test_traceability_passes_when_every_requirement_resolves_non_draft"
        status: pass
    human_judgment: false
  - id: D2
    description: "run_a2 assembles one AgentFinding per failed check, conventions-compliant, against the live seeded database"
    requirement: "ORC-03"
    verification:
      - kind: unit
        ref: "backend/tests/test_a2_compliance.py#test_run_a2_emits_exactly_two_findings_for_seeded_system"
        status: pass
      - kind: unit
        ref: "backend/tests/test_a2_compliance.py#test_run_a2_findings_conform_to_phase3_agentfinding_conventions"
        status: pass
      - kind: unit
        ref: "backend/tests/test_a2_compliance.py#test_run_a2_narration_mocked_vs_degraded_same_two_checks_fail"
        status: pass
      - kind: unit
        ref: "backend/tests/test_a2_compliance.py#test_run_a2_postgres_unreachable_returns_bible_failure_behavior"
        status: pass
      - kind: integration
        ref: "backend/tests/test_hero_tracer.py#test_success_path_real_finding_verified_medium_confidence"
        status: pass
    human_judgment: false
  - id: D3
    description: "verify_urs_approved's positive path is exercised against a real seeded APPROVED URS row (D-05)"
    requirement: "ORC-03"
    verification:
      - kind: unit
        ref: "backend/tests/test_a2_compliance.py#test_verify_urs_approved_passes_against_seeded_approved_row"
        status: pass
    human_judgment: false
  - id: D4
    description: "apply-seed.sh applies every seed script in sorted order and stays idempotent; verify-seed.sh asserts the new fixture"
    requirement: "ORC-03"
    verification:
      - kind: manual_procedural
        ref: "Applied both seed files twice via asyncpg (docker CLI unavailable in this worktree shell — see Environment Note) and re-ran the equivalent of verify-seed.sh's checks directly; both idempotent and SEED OK"
        status: pass
    human_judgment: true
    rationale: "docker CLI is not on PATH in this worktree's shell, so infra/apply-seed.sh and infra/verify-seed.sh themselves could not be invoked directly this session — verified via an equivalent asyncpg-driven re-implementation of the same SQL/queries instead. A human with docker available should run the actual scripts once to confirm the shell-level wiring (dc exec, PGPASSWORD, ON_ERROR_STOP) is correct, not just the SQL."

duration: 55min
completed: 2026-08-21
status: complete
---

# Phase 3 Plan 4: A2's Remaining Deterministic Checks + URS Seed Fixture Summary

**A2 now runs all three Bible-named checks (URS approval, periodic evaluation, test traceability) against live Postgres, backed by an additive APPROVED-URS seed fixture that exercises verify_urs_approved's positive path for the first time.**

## Performance

- **Duration:** 55 min
- **Started:** 2026-08-21T10:05:00Z (approx, first Read call)
- **Completed:** 2026-08-21T11:00:00Z (approx)
- **Tasks:** 2
- **Files modified:** 7 (2 created, 5 modified)

## Accomplishments

- `verify_urs_approved` and `verify_test_traceability` implemented as parameterized asyncpg queries, joining the tracer's existing `verify_periodic_eval_current` into a single `A2_CHECKS` tuple in the Bible's own listed order.
- `run_a2` rewritten to iterate `A2_CHECKS`, narrate every failing check, and return one finding per failure — against the seeded `GXP-MFG-DEMO-01` this now produces exactly two findings (periodic-evaluation gap, traceability gap) and none for the now-passing URS check.
- `infra/postgres/seed/002_urs_fixture.sql` seeds one real `APPROVED` URS document (`DOC-2026-URS-01`), closing the one testability gap 03-RESEARCH.md flagged (D-05) — `verify_urs_approved`'s positive path is now exercised against a genuine row instead of assumed by inspection.
- `infra/apply-seed.sh` now applies every `*.sql` file under `infra/postgres/seed/` in sorted order (was hardcoded to `001_seed.sql`), still idempotent and still fails fast on the first erroring script; `infra/verify-seed.sh` gained two Phase-3 fixture assertions.
- `backend/tests/test_a2_compliance.py`: 11 tests, all ten `<behavior>` cases plus one extra ordering check, run against the live seeded database with test-only rows inserted-and-rolled-back inside explicit transactions for the two paths the committed seed doesn't cover.
- Discovered, documented, and test-asserted (rather than silently patched) a pre-existing `c1_verifier.py` defect that prevents the traceability finding from corroborating against OPA — out of this plan's Rule 10 file boundary to fix; recorded in `.planning/WINDOWS.md`.

## Task Commits

Each task was committed atomically:

1. **Task 1: Additive URS seed fixture (D-05) and a glob-driven apply-seed** - `8b0f46a` (feat)
2. **Task 2: A2's remaining two deterministic checks and multi-gap finding assembly** - `a71c75f` (feat)

**Plan metadata:** _pending — added in the same commit as this summary_

## Files Created/Modified

- `infra/postgres/seed/002_urs_fixture.sql` - Additive Phase-3 fixture: one `APPROVED` URS document row for `GXP-MFG-DEMO-01`, idempotent `ON CONFLICT (id) DO NOTHING`, adds no Rego gap (rule 1 is O&M-scoped).
- `infra/apply-seed.sh` - Iterates every `*.sql` in `infra/postgres/seed/` in sorted order instead of naming `001_seed.sql` literally; fails fast on the first erroring script; echoes each applied filename.
- `infra/verify-seed.sh` - Two new Phase-3 fixture assertions (`DOC-2026-URS-01` doc_type/status) alongside the unchanged ten gap checks.
- `infra/README.md` - Wording updated from "the seed file" (singular) to directory-wide, sorted-order application.
- `backend/app/agents/a2_compliance.py` - Adds `verify_urs_approved`, `verify_test_traceability`, `A2_CHECKS`, generalizes `narrate_gap`/`_deterministic_gap_sentence` across all three checks, extends `build_finding`'s null-record handling, records the policy-coverage asymmetry in the module docstring.
- `backend/tests/test_a2_compliance.py` - New: 11 tests over all three checks' pass/fail paths, `run_a2` assembly, AgentFinding conventions, null-record finding shape, narration-cannot-alter-result, and the Postgres-unreachable failure path.
- `backend/tests/test_hero_tracer.py` - Updated for A2 now emitting two findings against the seeded state; documents and asserts the discovered `c1_verifier.py` defect's real (not originally-predicted) outcome for the traceability finding.

## Decisions Made

- Seeded a real APPROVED URS document rather than accepting negative-only coverage (D-05) — see `key-decisions` in frontmatter.
- `verify_urs_approved` reuses `ANNEX11-S4-DOC-001` (rule 1's citation), generalized to `doc_type='URS'`; documented as an intentionally uncorroborated finding rather than editing the closed Rego bundle.
- `build_finding`'s null-record path changed to empty `evidence_ids` + `NO-RECORD` marker (previously `"unknown"` as a literal evidence id) — a correctness fix the plan's `<behavior>` spec required, applying to all three checks' no-record case.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug, plan-sanctioned] Updated `test_hero_tracer.py`'s single-finding assertions to two findings**
- **Found during:** Task 2 verification (`pytest tests/test_hero_tracer.py`)
- **Issue:** 03-02's tracer test asserted exactly one finding (`_one_finding` helper). Against the seeded state, A2 now correctly fails two of its three checks (periodic-evaluation and traceability), so the assertion was stale, not wrong logic.
- **Fix:** Replaced `_one_finding` with `_finding_by_id`, asserting exactly two findings and picking each by id. This exact update path is explicitly sanctioned by 03-04-PLAN.md's own acceptance criteria ("If the tracer asserted exactly one finding, update that assertion to the two findings the seeded state now produces, and record the change in the summary").
- **Files modified:** `backend/tests/test_hero_tracer.py`
- **Verification:** `pytest tests/test_hero_tracer.py -x -q` → 3 passed.
- **Committed in:** `a71c75f` (Task 2 commit)

**2. [Rule 1/discovered-defect, out-of-boundary — documented not fixed] `c1_verifier.py` never corroborates the traceability finding against OPA**
- **Found during:** Task 2 verification, running the full graph to check `verification_results` shape for both A2 findings.
- **Issue:** `03-04-PLAN.md`'s `<critical_findings>` predicted the traceability finding (rule 5, `ANNEX11-S4-TRC-001`) would score `MEDIUM` like the periodic-evaluation finding. In reality it scores `INSUFFICIENT_EVIDENCE`. Root cause: `c1_verifier.py`'s `build_opa_payload()` queries every `RULE_OPA_INPUT` table using the finding's own `evidence_ids` (`["URS-042"]`, a *requirement* id). For rule 5's two-input shape, the `test_cases` input must instead be keyed by the requirement's linked `test_case_id` (`"TC-2026-042"`) — `evidence_ids` never contains that id, so the `test_cases` payload OPA receives is always empty, rule 5's body (`input.test_cases[req.test_case_id]`) is undefined, and no violation is ever emitted for this rule regardless of how correct A2's own DRAFT detection is.
- **Fix:** NOT applied. `c1_verifier.py` is explicitly outside this plan's Rule 10 file boundary (owned by 03-02, and this plan's `<critical_findings>` names it as a file that "must not" be touched). Instead: (a) `verify_test_traceability`'s own docstring documents this asymmetry precisely; (b) `test_hero_tracer.py`'s docstring and assertions were updated to match the real, observed behavior rather than the plan's predicted behavior; (c) recorded in `.planning/WINDOWS.md` as an open `deviation` entry routed to a future C1-hardening plan. This bug likely also affects `ANNEX11-S10-CHG-001` (rule 10), which has the same two-differently-keyed-input-table shape (`changes` + `change_actions`) — not verified this plan, flagged for the same future fix.
- **Files modified:** None (documentation/test-assertion only — `a2_compliance.py`'s own check logic is correct and unaffected).
- **Verification:** `backend/tests/test_hero_tracer.py::test_success_path_real_finding_verified_medium_confidence` explicitly asserts `opa_corroborated is False` / `confidence == "INSUFFICIENT_EVIDENCE"` for the traceability finding, with an inline comment explaining why.
- **Committed in:** `a71c75f` (Task 2 commit); WINDOWS.md entry recorded separately (uncommitted at end of this plan's execution — see Next Phase Readiness).

---

**Total deviations:** 2 (1 plan-sanctioned test update, 1 discovered pre-existing defect documented but not fixed due to explicit file-boundary constraint)
**Impact on plan:** No scope creep. Both deviations keep this plan's own deliverable (A2's three checks, correctly implemented and tested) intact; the second deviation is a genuine finding about a sibling module this plan is contractually forbidden from editing.

## Known Stubs

None — every check function and finding-assembly path is fully wired against live Postgres, no hardcoded/empty placeholder values.

## Threat Flags

None beyond what 03-04-PLAN.md's own `<threat_model>` already anticipated (T-03-18 through T-03-22, all mitigated/accepted as designed — see file diffs for the `$1`-placeholder-only queries satisfying T-03-18's grep gate).

## Issues Encountered

**Environment: docker CLI unavailable in this worktree's shell.** Same situation 03-02's summary recorded: `docker`/`docker-compose`/`psql` are not on `PATH` in this session's shell, so `infra/apply-seed.sh` and `infra/verify-seed.sh` could not be invoked as literal `bash` commands. Postgres (5432) and OPA (8181) were confirmed live and reachable directly (`node -e "require('net')..."`), already seeded from a prior `apply-seed.sh` run (started in an earlier session/host context). Verification was performed by re-implementing the exact same SQL/queries `apply-seed.sh`/`verify-seed.sh` run, via `asyncpg` directly against the live container — applied both seed files twice in a row (idempotency confirmed), and re-ran every `verify-seed.sh` check including the two new fixture assertions (all PASS, `SEED OK` equivalent). `backend/.venv` also does not exist inside this git worktree (gitignored, not part of the worktree checkout) — resolved by invoking the main checkout's `backend/.venv/Scripts/python.exe` interpreter directly with the worktree's `backend/` as the working directory, which correctly resolves `app` from the worktree while reusing the already-installed `asyncpg`/`respx`/`pydantic` etc. from the shared venv.

**Discovered `c1_verifier.py` defect.** See Deviations section above.

## User Setup Required

None - no external service configuration required. (The pre-existing credential gap for live LLM quality verification, noted in 03-01/03-02's summaries, is unchanged — this plan's LLM calls are proven via respx-mocked wire-contract tests plus the degraded-mode fallback, same as 03-02.)

## Next Phase Readiness

- All three Bible-named A2 checks are implemented, tested, and wired; `run_a2` correctly assembles multi-gap findings; ORC-03 is satisfied.
- `.planning/WINDOWS.md` was created and populated with one open `deviation` entry (the `c1_verifier.py` corroboration defect) via `gsd-tools query windows append` — **this file is new and was left uncommitted at the end of this plan's task work**, to be picked up in the final metadata commit alongside this SUMMARY.md, per this plan's instruction not to touch STATE.md/ROADMAP.md directly.
- A future C1-hardening plan should fix `build_opa_payload()`'s input-table lookup for multi-input-key rules (5 and, likely, 10) — this is now a tracked, open item, not a silent gap.
- Recommend running `bash infra/apply-seed.sh` / `bash infra/verify-seed.sh` literally (with docker available) once, to confirm the shell-level script wiring this plan changed (glob loop, `ON_ERROR_STOP=1` fail-fast) behaves identically to the asyncpg-based verification performed this session.

---
*Phase: 03-intelligence-retrieval*
*Completed: 2026-08-21*

## Self-Check: PASSED

All claimed files found on disk (`infra/postgres/seed/002_urs_fixture.sql`, `backend/app/agents/a2_compliance.py`, `backend/tests/test_a2_compliance.py`, `backend/tests/test_hero_tracer.py`, `.planning/WINDOWS.md`, this SUMMARY.md). Both task commits (`8b0f46a`, `a71c75f`) confirmed present in `git log`.
