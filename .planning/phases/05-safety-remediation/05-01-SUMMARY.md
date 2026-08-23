---
phase: 05-safety-remediation
plan: 01
subsystem: safety-remediation
tags: [postgres, migrations, fastapi, audit-trail, rbac, action-proposals]

# Dependency graph
requires:
  - phase: 04-evidence-impact
    provides: C1 evidence verification (c1_verifier.py), findings route, evidence graph read patterns
provides:
  - No code shipped yet — plan halted at its first task, a blocking-human schema decision checkpoint
affects: [05-02, 05-03, 05-04, 05-05, 05-06]

actuals:
  tokens: 0
  tasks: 0
  commits: 1

tech-stack:
  added: []
  patterns: []

key-files:
  created: []
  modified: []

key-decisions:
  - "No decision recorded — Task 1 is an unresolved checkpoint:decision (gate=blocking-human). See 'Schema decision' below."

patterns-established: []

requirements-completed: []

coverage: []

duration: 5min
completed: 2026-08-23
status: halted
---

# Phase 5 Plan 1: Safety & Remediation Tracer Summary

**Halted at Task 1 — the `action_proposals` schema-shape decision is a one-way door and requires an explicit human choice before any code in this plan can be written.**

## Performance

- **Duration:** 5 min (checkpoint reached immediately; no implementation tasks executed)
- **Started:** 2026-08-23T17:00:00Z (approx)
- **Completed:** N/A — plan not complete
- **Tasks:** 0 of 3 completed (Task 1 presented, not resolved; Tasks 2-3 not started)
- **Files modified:** 0

## Accomplishments

None yet. This plan's first task (`Task 1: Decide the action_proposals workflow-column shape`) is `type="checkpoint:decision"` with `gate="blocking-human"`. Per the executor's checkpoint protocol, `gate="blocking-human"` is **never** auto-approved, in any mode — the project's own `.planning/config.json` also has `mode: "interactive"` and `workflow.auto_advance: false`, so this checkpoint would have stopped for a human either way. No production code, migration, or test was written; Tasks 2 and 3 both depend directly on the outcome of this decision (Task 2's migration action targets whichever option is chosen; Task 3's queries reference the resulting columns) and per the plan's own `<action>` instruction, "Do not begin Task 2 until the option is chosen."

## Schema decision

**Status: PENDING — awaiting human input. No option has been selected.**

**Decision needed:** How should the `action_proposals` table store the workflow facts REM-03 (server-trusted approval dialog with a `justification`) and REM-04 (approval provenance: who approved, when, execution result, and queue ordering) need?

**Why this matters (context from the plan):** The live `action_proposals` table (`infra/postgres/initdb/001_schema.sql:174-180`) has only `id, action_type, target_system, payload, status` — confirmed by direct read during this halted run. The Bible's own Section 4.1 DDL never declared `justification`, `approved_by`, `approved_at`, etc. either; it exists only on the Pydantic `ActionProposal` model. This is a pre-existing gap, not something Phases 1-4 introduced. The choice is a **one-way door**: every later plan's SQL (05-03, 05-04, 05-05), both new route response models, and the frontend `ActionProposalData` TypeScript interface will be written against whichever shape is picked. Reversing it after 05-05 ships means rewriting queries, response models, and TypeScript interfaces together.

**Options presented (verbatim from 05-01-PLAN.md):**

| Option | Name | Pros | Cons |
|--------|------|------|------|
| **option-a** (recommended by the plan) | Additive migration (`003_action_proposals_workflow.sql`), category derived at read time | `ORDER BY created_at` works natively; approval provenance sits in first-class, inspectable columns; follows the exact shipped `002_change_affects.sql` precedent (confirmed identical pattern on read during this session) and `infra/apply-migrations.sh` mechanism; `ADD COLUMN IF NOT EXISTS` keeps it re-runnable; `category` stays derived from the single frozen `ACTION_CATEGORIES` allowlist rather than becoming a second source of truth. Columns added: `justification TEXT`, `finding_id VARCHAR(100)`, `session_id VARCHAR(100)`, `model_id VARCHAR(50)`, `created_at TIMESTAMP DEFAULT now()`, `approved_by VARCHAR(100)`, `approved_at TIMESTAMP`, `execution_result TEXT`. | Adds a migration file the Bible's Section 4.1 DDL does not contain, so it is a deviation that must be routed to SENT-7-05. |
| option-b | Pack the workflow fields into the existing `payload JSONB` | Zero schema change and zero Bible deviation; the queue orders by a timestamp-embedded id (`AP-{YYYYmmddHHMMSSffffff}`), mirroring the `EVT-` convention `audit_events` already uses. | `ORDER BY` and `WHERE` on approval fields need JSONB expression indexes; `approved_by` becomes invisible to a plain `SELECT`, which is exactly the provenance an inspector would ask to see first. |
| option-c | Option A plus a persisted `category VARCHAR(50)` column | `WHERE category = 'GXP_RELEVANT_WRITE'` works directly in SQL. | Two sources of truth for category — the column and `ACTION_CATEGORIES` — which can drift apart silently; violates the cache-holds-no-underivable-fact principle `graph_nodes`/`graph_edges` already follow. |

**Executor's recommendation: option-a.** It matches the shipped `002_change_affects.sql` precedent exactly (same additive-migration mechanism, same header-comment discipline, same `IF NOT EXISTS` re-runnability, same SENT-7-05 deviation routing), keeps `category` as a single derived source of truth (avoiding option-c's drift risk), and gives approval provenance (`approved_by`, `approved_at`) first-class inspectable columns rather than burying them in JSONB (avoiding option-b's query/audit-visibility cost). This is also the plan author's own stated recommendation.

**Resume signal:** Select `option-a`, `option-b`, or `option-c` (recommended: `option-a`). Once selected, a continuation executor should record the choice and rationale here (replacing this PENDING section), then proceed to Task 2 with Task 2's migration action adjusted if `option-b` or `option-c` was chosen instead of the plan's default (`option-a`).

## Task Commits

No task commits — no code was written. This SUMMARY documents the halted state only.

**Plan metadata:** (this commit) — `docs(05-01): halt at blocking schema-decision checkpoint`

## Files Created/Modified

None.

## Decisions Made

None — this is the open decision itself. See "Schema decision" above.

## Deviations from Plan

None - no implementation work was attempted. The plan's `<output>` section anticipates three deviations to be recorded once Tasks 2-3 execute (canonical-field-list correction, A7 deterministic fallback, GXP_RELEVANT_WRITE queue reconciliation) — those remain to be documented by the continuation executor after this checkpoint resolves.

## Issues Encountered

The plan's first task is a `checkpoint:decision` with `gate="blocking-human"`, which by design (see `gsd-core/references/checkpoints.md`) is never auto-approved in any mode, including auto-advance. This is expected behavior, not a bug — Task 1's own `<action>` instructs the executor to "Present the three options with the recommendation (Option A) and wait for a choice" and explicitly forbids starting Task 2 before the option is recorded. This executor stopped as designed.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

**Not ready — this plan is not complete.** A human (or an authorized continuation run) must select `option-a`, `option-b`, or `option-c` before Task 2 (migration, identity, audit trail) or Task 3 (C2/C3/A7 gateways, actions routes) can begin. Once the decision is recorded, a continuation executor should:
1. Update this SUMMARY's "Schema decision" section with the chosen option and rationale.
2. Execute Task 2 (adjusting the migration if option-b or option-c was chosen instead of the recommended option-a).
3. Execute Task 3.
4. Re-run this plan's full `<verification>` block and finalize this SUMMARY with `status: complete`, real `actuals`, task commits, and the coverage block.

Every downstream plan in Phase 5 (05-02 through 05-06) depends on this tracer plan's Task 3 modules (`c2_gateway.py`, `c3_gateway.py`, `a7_remediation.py`, `identity.py`, `audit_trail.py`) existing, so the phase cannot progress past this checkpoint.

---
*Phase: 05-safety-remediation*
*Halted: 2026-08-23*
