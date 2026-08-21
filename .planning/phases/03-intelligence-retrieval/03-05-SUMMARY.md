---
phase: 03-intelligence-retrieval
plan: 05
subsystem: api
tags: [c1-verifier, opa, postgres, pytest, critical-review, sent-2-12]

requires:
  - phase: 03-intelligence-retrieval
    provides: "03-02's C1 tracer (calculate_confidence, RULE_EVIDENCE_TABLES, RULE_OPA_INPUT, fetch_evidence_record, build_opa_payload, verify_finding, run_c1) and 03-04's additive DOC-2026-URS-01 APPROVED URS fixture used as the EVID-02 contradiction fixture"
provides:
  - "backend/tests/test_c1_verifier.py — 20 tests across UNIT/NEGATIVE/EDGE/INTEGRATION sections meeting CLAUDE.md Rule 6 / SENT-2-12's Critical-review bar"
  - "A fixed build_opa_payload() in c1_verifier.py: RULE_OPA_INPUT's new id_source element (evidence_ids / via / by_column) resolves multi-input-key rules (5, 10) via the correct foreign-key linkage instead of the finding's own evidence_ids"
  - "backend/README.md '## C1 Critical-review coverage (SENT-2-12)' section recording the four coverage classes, the EVID-02 fixtures, the fail-closed rationale, and the non-claim about live-LLM narration"
  - ".planning/WINDOWS.md id 1 marked fixed — the build_opa_payload multi-input-key defect discovered in 03-04 is closed"
affects: [03-06, future-c1-work]

actuals:
  tokens: 11200
  tasks: 2
  commits: 2

tech-stack:
  added: []
  patterns:
    - "RULE_OPA_INPUT's id_source element (evidence_ids / (\"via\", source_key, column) / (\"by_column\", column)) keeps build_opa_payload() a single data-driven loop with no per-rule branching, even for rules needing a second, differently-keyed table"
    - "Poison-pool test double (fetchrow/fetch raise if called) to prove a code path never touches Postgres, not merely that its result happens to be None"
    - "Call-counting wrapper installed on the module's own evaluate_opa_policy reference to prove the OPA client is never invoked on the missing-record short-circuit path, rather than asserting via source inspection"

key-files:
  created:
    - backend/tests/test_c1_verifier.py
  modified:
    - backend/app/agents/c1_verifier.py
    - backend/tests/test_hero_tracer.py
    - backend/README.md
    - .planning/WINDOWS.md

key-decisions:
  - "Fixed the build_opa_payload() multi-input-key defect (.planning/WINDOWS.md id 1, discovered in 03-04) rather than leaving it open. 03-05-PLAN.md's own Task 2 acceptance criteria explicitly required rule 5's verification to corroborate and at least 8/10 seeded gap records to corroborate — both are only achievable by fixing the defect, so it was in-scope by the plan's own stated bar, not a silent scope expansion. Fixed generally (not special-cased to rule 5) since the module's own design principle is one data-driven loop with no per-rule branching, and the WINDOWS.md entry itself flagged rule 10 as the same shape."
  - "Updated test_hero_tracer.py's two assertions that had recorded the pre-fix (buggy) INSUFFICIENT_EVIDENCE/opa_corroborated=False behavior for the traceability finding to the corrected MEDIUM/True outcome, since the fix changes real, observed behavior the existing suite asserted on. This file is not in 03-05-PLAN.md's declared files_modified, but leaving it unmodified would leave the full backend suite red, which the plan's own <verification> block requires to be green. Same pattern 03-04 used for the same file (see its SUMMARY.md deviation 1)."
  - "Marked .planning/WINDOWS.md id 1 as fixed (manually, following its documented JSON+table schema — gsd-tools was not present in this worktree/environment) rather than leaving it open, since the underlying defect it tracks is now closed and test-proven."

requirements-completed: [EVID-01, EVID-02]

coverage:
  - id: D1
    description: "calculate_confidence() grade ladder and all three threshold boundaries (80 exclusive, 50 inclusive, 0 exclusive) proven via direct unit tests"
    requirement: "EVID-01"
    verification:
      - kind: unit
        ref: "backend/tests/test_c1_verifier.py#test_unit_grade_ladder_full_sweep"
        status: pass
      - kind: unit
        ref: "backend/tests/test_c1_verifier.py#test_unit_boundary_exclusive_above_80_seven_true_dims_grades_medium_not_high"
        status: pass
      - kind: unit
        ref: "backend/tests/test_c1_verifier.py#test_unit_boundary_inclusive_at_50_four_true_dims_grades_medium_not_low"
        status: pass
      - kind: unit
        ref: "backend/tests/test_c1_verifier.py#test_unit_boundary_exclusive_above_0_nine_true_dims_policy_false_grades_insufficient_not_low"
        status: pass
      - kind: unit
        ref: "backend/tests/test_c1_verifier.py#test_unit_policy_contradiction_dominates_across_all_dimension_counts"
        status: pass
    human_judgment: false
  - id: D2
    description: "An LLM-shaped claim contradicting the real DOC-2026-URS-01 Postgres row and the real OPA evaluation returns INSUFFICIENT_EVIDENCE, proven against live Postgres and the live OPA sidecar in the same suite that scores a truthful claim MEDIUM (EVID-02, D-04)"
    requirement: "EVID-02"
    verification:
      - kind: integration
        ref: "backend/tests/test_c1_verifier.py#test_negative_evid02_contradiction_against_real_approved_urs_row"
        status: pass
      - kind: integration
        ref: "backend/tests/test_c1_verifier.py#test_negative_positive_control_truthful_claim_against_real_row_scores_medium"
        status: pass
    human_judgment: false
  - id: D3
    description: "A finding whose evidence_ids name a record that does not exist returns INSUFFICIENT_EVIDENCE without the policy engine being consulted, asserted via a call-counting wrapper (not source inspection)"
    requirement: "EVID-02"
    verification:
      - kind: integration
        ref: "backend/tests/test_c1_verifier.py#test_negative_evid02_fabricated_evidence_short_circuits_before_opa_call"
        status: pass
    human_judgment: false
  - id: D4
    description: "Every one of the ten rule ids in policies/gxp_rules.rego resolves through C1 against live Postgres and the live OPA sidecar to a real confidence grade, including rule 5's object-keyed test_cases payload and rule 10's two-key payload"
    requirement: "EVID-01"
    verification:
      - kind: integration
        ref: "backend/tests/test_c1_verifier.py#test_integration_ten_rules_resolve_real_record_and_payload_shape_matches_documented_input"
        status: pass
      - kind: integration
        ref: "backend/tests/test_c1_verifier.py#test_integration_ten_rules_verify_finding_grades_and_at_least_eight_corroborate"
        status: pass
      - kind: integration
        ref: "backend/tests/test_c1_verifier.py#test_integration_rule_5_payload_test_cases_object_shape_and_corroborates"
        status: pass
      - kind: integration
        ref: "backend/tests/test_c1_verifier.py#test_integration_rule_10_payload_carries_both_changes_and_change_actions_keys"
        status: pass
    human_judgment: false
  - id: D5
    description: "C1 fails closed on both an OPA-sidecar outage and a Postgres outage — nothing is corroborated and every finding scores INSUFFICIENT_EVIDENCE rather than defaulting to trusted"
    requirement: "EVID-01"
    verification:
      - kind: integration
        ref: "backend/tests/test_c1_verifier.py#test_integration_fail_closed_opa_unreachable_all_ten_grade_insufficient_evidence"
        status: pass
      - kind: integration
        ref: "backend/tests/test_c1_verifier.py#test_integration_fail_closed_postgres_unreachable_run_c1_all_insufficient_evidence"
        status: pass
    human_judgment: false
  - id: D6
    description: "SENT-2-12's Critical-review bar is met and documented: unit, negative, edge-case, and integration coverage all exist and are named in the repository"
    requirement: "EVID-01"
    verification:
      - kind: other
        ref: "backend/README.md '## C1 Critical-review coverage (SENT-2-12)' section"
        status: pass
    human_judgment: false

duration: 55min
completed: 2026-08-21
status: complete
---

# Phase 3 Plan 5: C1 Critical-Review Hardening (SENT-2-12) Summary

**20 unit/negative/edge/integration tests proving C1 fails correctly (EVID-02) as well as succeeds, plus a fix to `build_opa_payload()`'s pre-existing multi-input-key defect that was blocking rules 5 and 10 from ever corroborating.**

## Performance

- **Duration:** 55 min (approx)
- **Completed:** 2026-08-21T11:07:14Z
- **Tasks:** 2
- **Files modified:** 4 (1 created, 3 modified) + `.planning/WINDOWS.md` ledger update

## Accomplishments

- `backend/tests/test_c1_verifier.py` (new, 20 tests, 4 clearly commented sections matching CLAUDE.md Rule 6's four coverage classes): `calculate_confidence()`'s full grade ladder and all three threshold boundaries (80 exclusive, 50 inclusive, 0 exclusive) proven directly; the `-100` policy-contradiction penalty proven to dominate across every ALCOA dimension count 0-9; an EVID-02 contradiction fixture asserting the opposite of the real, genuinely `APPROVED` `DOC-2026-URS-01` row, run against live Postgres and the live OPA sidecar with neither mocked; a fabricated-evidence-id fixture proving the OPA client is never invoked (call-counting wrapper, not source inspection); a positive-control truthful claim proving the two negative results are discrimination, not blanket refusal; an unrecognised-rule-id guard proven via a poison-pool double that raises if Postgres is touched at all; an empty-`evidence_ids` guard; `run_c1`'s driver over a 3-finding mixed list; all ten `policies/gxp_rules.rego` rule ids resolving through C1 end to end with at least 8/10 (in practice all 10, post-fix) corroborating; and both fail-closed outage paths (OPA unreachable, Postgres unreachable).
- Fixed a real, pre-existing defect in `c1_verifier.py`'s `build_opa_payload()` (`.planning/WINDOWS.md` id 1, discovered in plan 03-04, out of that plan's file-boundary scope to fix): it queried every `RULE_OPA_INPUT` table using the finding's own `evidence_ids`, which silently broke OPA corroboration for the two multi-input-key rules (`ANNEX11-S4-TRC-001`'s `test_cases`, `ANNEX11-S10-CHG-001`'s `change_actions`). `RULE_OPA_INPUT` gained a fourth `id_source` element (`"evidence_ids"` / `("via", source_key, column)` / `("by_column", column)`) so both rules now resolve via the correct foreign-key linkage, still with zero per-rule branching in `build_opa_payload()` itself.
- Updated `test_hero_tracer.py`'s two assertions that had recorded the pre-fix (buggy) behavior — the traceability finding now correctly scores `MEDIUM`/`opa_corroborated=True` in both the success and degraded paths, matching what `03-04-PLAN.md`'s `<critical_findings>` originally predicted before the defect was discovered.
- `backend/README.md` gained `## C1 Critical-review coverage (SENT-2-12)`: names every test per Rule 6 coverage class, documents the two EVID-02 fixtures and the exact real-world facts each contradicts, explains the fail-closed rationale for both outage directions, records the `build_opa_payload()` fix, cross-references Deviation 7 for the fixed (non-tunable) `calculate_confidence()` constants, and states plainly that no live LLM produced any of the graded claims this phase (no provider key configured) — the operator re-run remains the outstanding follow-up.
- `.planning/WINDOWS.md` id 1 marked `fixed` (manually — `gsd-tools` was not present in this environment), closing the cross-phase defect register entry this plan's fix resolves.

## Task Commits

Each task was committed atomically:

1. **Task 1: Unit, negative, and edge-case coverage — the confidence ladder and the engineered contradiction fixture** - `bdc8424` (test) — also fixed `build_opa_payload()`'s multi-input-key defect and updated `test_hero_tracer.py`'s two now-stale assertions (see Deviations).
2. **Task 2: Integration coverage across all ten rules, the fail-closed policy-outage path, and the SENT-2-12 review record** - `10bbe37` (test)

**Plan metadata:** _pending — added in the final metadata commit alongside this SUMMARY.md_

## Files Created/Modified

- `backend/tests/test_c1_verifier.py` - New: 20 tests across UNIT/NEGATIVE/EDGE/INTEGRATION sections.
- `backend/app/agents/c1_verifier.py` - `RULE_OPA_INPUT` gained a fourth `id_source` tuple element; `build_opa_payload()` rewritten to resolve `"evidence_ids"` / `"via"` / `"by_column"` id sources in one data-driven loop; new `_select_many_by_column_query()` helper. `calculate_confidence()`'s constants unchanged.
- `backend/tests/test_hero_tracer.py` - Module docstring and two assertions updated from the pre-fix buggy `INSUFFICIENT_EVIDENCE`/`False` outcome to the corrected `MEDIUM`/`True` outcome for the traceability finding.
- `backend/README.md` - New `## C1 Critical-review coverage (SENT-2-12)` section.
- `.planning/WINDOWS.md` - id 1 marked `fixed` with resolution detail and test references.

## Decisions Made

- Fixed the `build_opa_payload()` multi-input-key defect rather than leaving it open — see `key-decisions` in frontmatter for the full reasoning (the plan's own Task 2 acceptance criteria required it).
- Updated `test_hero_tracer.py`'s stale assertions to match the corrected, now-observed behavior — see `key-decisions`.
- Marked `.planning/WINDOWS.md` id 1 fixed manually (no `gsd-tools` binary present in this worktree/environment) rather than leaving the ledger stale.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1/2 - Bug, plan-required] Fixed `build_opa_payload()`'s multi-input-key defect**
- **Found during:** Task 1, while designing the EVID-02 positive-control and Task 2's ten-rule table (both explicitly require rule 5 to corroborate).
- **Issue:** `build_opa_payload()` queried every `RULE_OPA_INPUT` table using the finding's own `evidence_ids`, which is only correct for the finding's own record. For `ANNEX11-S4-TRC-001` (rule 5), the `test_cases` table needs the requirement's linked `test_case_id`, not the requirement's own id; for `ANNEX11-S10-CHG-001` (rule 10), `change_actions` needs to be filtered by its own `change_id` foreign key, not looked up by `id`. Pre-existing, discovered in 03-04, recorded in `.planning/WINDOWS.md` id 1, explicitly out of 03-04's file-boundary scope.
- **Fix:** `RULE_OPA_INPUT` gained a fourth tuple element (`id_source`) naming how each table resolves (`"evidence_ids"`, `("via", source_key, column)`, or `("by_column", column)`); `build_opa_payload()` reads this data-driven, with no new per-rule branching.
- **Files modified:** `backend/app/agents/c1_verifier.py`
- **Verification:** `test_integration_rule_5_payload_test_cases_object_shape_and_corroborates`, `test_integration_rule_10_payload_carries_both_changes_and_change_actions_keys`, manual live-infra spot check (both rules verified `opa_corroborated: True` before writing the automated tests).
- **Committed in:** `bdc8424` (Task 1 commit)

**2. [Rule 1 - Bug, plan-sanctioned pattern] Updated `test_hero_tracer.py`'s stale assertions**
- **Found during:** Task 1, running the full suite after the `build_opa_payload()` fix — `test_success_path_real_finding_verified_medium_confidence` and `test_degraded_path_no_provider_key_same_finding_and_score` failed because they asserted the pre-fix buggy `INSUFFICIENT_EVIDENCE`/`opa_corroborated=False` outcome for the traceability finding.
- **Issue:** These two tests were written in 03-04 to document the *observed* (buggy) behavior at that time, with an explicit comment noting the discrepancy from the originally-predicted `MEDIUM`. Fixing the underlying bug this plan makes those assertions describe behavior that no longer occurs.
- **Fix:** Updated both assertions to `MEDIUM`/`opa_corroborated=True`, and updated the module docstring to record the fix and point at this plan's SUMMARY. `test_hero_tracer.py` is not in 03-05-PLAN.md's declared `files_modified`, but this update is the direct, necessary consequence of a fix the plan's own acceptance criteria required, and leaving it unmodified would leave the full suite red — which the plan's `<verification>` block requires to be green.
- **Files modified:** `backend/tests/test_hero_tracer.py`
- **Verification:** `pytest tests/test_hero_tracer.py -q` → 3 passed; full suite `pytest -q` → 103 passed.
- **Committed in:** `bdc8424` (Task 1 commit)

---

**Total deviations:** 2 (1 required bug fix per the plan's own acceptance criteria, 1 direct consequence update to a sibling test file)
**Impact on plan:** No scope creep beyond what the plan's own Task 2 acceptance criteria required (rule 5 corroboration, ≥8/10 corroborating). Both deviations were necessary to keep the full backend suite green, as `<verification>` requires.

## Issues Encountered

**Environment: `docker` CLI unavailable in this worktree's shell.** Same situation prior Phase-3 plans recorded: `docker`/`docker-compose` are not on `PATH` in this session's shell, so `infra/verify-seed.sh` could not be invoked literally. Postgres (5432) and OPA (8181) were confirmed live and reachable directly, already seeded. Verified equivalently by re-running every one of `verify-seed.sh`'s checks (including the two Phase-3 fixture assertions and the nanosecond-magnitude guard) directly via `asyncpg` against the live database — all PASS, equivalent to `SEED OK`. `backend/.venv` also does not exist inside this git worktree (gitignored); resolved by invoking the main checkout's `backend/.venv/Scripts/python.exe` interpreter directly with the worktree's `backend/` as the working directory, matching prior plans' established workaround.

**`gsd-tools` binary not present in this worktree/environment.** `.planning/WINDOWS.md` id 1 was marked `fixed` by direct edit to the ledger's documented YAML-frontmatter + Markdown-table + JSON-block schema, rather than via `gsd-tools windows fixed 1`, since no `gsd-tools.cjs`/binary could be located anywhere under this worktree, `.claude/`, or common install paths.

## User Setup Required

None — no external service configuration required. The pre-existing credential gap for live LLM narration quality (noted in every prior Phase-3 plan's summary) is unchanged and explicitly disclaimed in this plan's new README section: no live LLM provider key is configured, so every fixture in `test_c1_verifier.py` is a finding dict built directly rather than narrated by a real model call. Setting a provider key and re-running the hero tracer remains the outstanding operator follow-up (03-01's `user_setup`).

## Next Phase Readiness

- SENT-2-12's Critical-review bar is met: unit, negative, edge-case, and integration coverage all exist, are named in `backend/README.md`, and are independently selectable via `-k contradiction`, `-k boundary`, and `-k "ten_rules or fail_closed"`.
- `.planning/WINDOWS.md` is now empty of open items (`open_count: 0`) — the one defect it tracked is fixed and test-proven.
- `build_opa_payload()`'s `id_source` mechanism is documented and general — a future rule needing a similar foreign-key-linked secondary table can add a `("via", ...)` or `("by_column", ...)` entry to `RULE_OPA_INPUT` without further `build_opa_payload()` changes.
- Full backend suite: 103/103 passing (`pytest -q` from `backend/`, live Postgres + OPA required).
- Plan 03-06 (the full hero-loop integration test) can now assume the traceability finding genuinely corroborates, not the pre-fix `INSUFFICIENT_EVIDENCE` outcome.

STATE.md and ROADMAP.md were not modified — left for the orchestrator, per this plan's instruction.

---
*Phase: 03-intelligence-retrieval*
*Completed: 2026-08-21*

## Self-Check: PASSED

All claimed files found on disk (`backend/tests/test_c1_verifier.py`, `backend/app/agents/c1_verifier.py`, `backend/tests/test_hero_tracer.py`, `backend/README.md`, `.planning/WINDOWS.md`, this SUMMARY.md). Both task commits (`bdc8424`, `10bbe37`) confirmed present in `git log`.
