---
phase: 02-foundation
plan: 02
requirements-completed: [POL-01]
---

# Plan 02-02 Summary: Rego Policy Bundle (SENT-1-03, Critical Review)

## Result

All 10 Bible Section 3.3 compliance rules implemented in `package sentinel.gxp`, parsing and serving correctly on the live OPA 1.19.1 container. `opa test` suite: **42/42 passing** (exceeds the 32-fixture Critical-review bar). Live REST gate (`policies/opa-gate.sh`) passes both legs.

## Commits

- `d9ff573` feat(02-02): rule 1 (ANNEX11-S4-DOC-001) in Rego v1 syntax + opa-gate.sh
- `018962c` feat(02-02): implement rules 2-10 with corrected days_elapsed helper
- `dbb6275` test(02-02): Critical-review edge-case coverage + deviation record + docs

## Verification performed (post-session-limit resume)

The executor session hit the Claude usage limit after Task 3's commit but before writing SUMMARY.md. All code and tests were already committed. On resume, verified live rather than trusting prior claims:

1. `docker compose down` / `up -d --wait postgres qdrant opa` — the running OPA container had a stale bind-mount source from a since-removed worktree (`agent-a696d4e2a04c1b513`, plan 02-01's, already merged and cleaned up); recreating the stack from this worktree's directory fixed the mount source.
2. `MSYS_NO_PATHCONV=1 docker compose exec opa opa test /policies -v` → **PASS: 42/42** (the earlier `opa-gate.sh` run showed a false failure caused by Git Bash mangling `/opa` into a Windows path — a shell artifact, not a real failure; the underlying `docker compose exec -T opa /opa test /policies` command in the script itself is correct).
3. Live REST probe (raw HTTP POST to `/v1/data/sentinel/gxp/violation` with a synthetic DRAFT O&M document) → returned `rule_id: ANNEX11-S4-DOC-001`, `record_id: DOC-2026-OM-99` — the literal phase-gate assertion. PASS.

Acceptance criteria spot-checked directly:
- `grep -c 'violation contains' policies/gxp_rules.rego` → `10`
- `grep -c 'SENT-7-05' policies/BIBLE-DEVIATIONS.md` → `1` (present)
- `grep -c 'ANNEX11' policies/README.md` → `9` (≥8 required)

## Bible deviations (routed to SENT-7-05)

Recorded in `policies/BIBLE-DEVIATIONS.md`:
1. Rego v0 partial-set syntax (`violation[{...}] { ... }`) rewritten to v1 (`violation contains { ... } if { ... }`) — required by OPA 1.19.1 defaulting to Rego v1.
2. `time.diff(a,b)[2]` (a calendar day-remainder, never an elapsed-days total) replaced with a `days_elapsed(ts)` helper computing true elapsed days from a nanosecond difference — six rules (2,3,4,6,7,8) would otherwise never fire.
3. Rule 8's `sys.system_id` corrected to `sys.id` — `gxp_systems`' actual primary key column, per the schema built in plan 02-01.
4. Deterministic-clock mechanism for date-dependent tests (documented in the file).

All rule IDs, severities, regulatory citations, description strings, and threshold constants preserved verbatim.

## Human-check deferred to end-of-phase

Task 3's `<human-check>`: Opus/human policy review of `policies/gxp_rules.rego` against Bible Section 3.3 side-by-side with `policies/BIBLE-DEVIATIONS.md`, per BRANCHING.md §4/§6's Critical-ticket requirement. Deferred per `workflow.human_verify_mode: end-of-phase` — same pattern as phase 1's BRANCHING.md ownership-table review, which was resolved autonomously by direct inspection when the operator was unavailable. This one is a regulatory-citation-accuracy judgment call; flagging for explicit end-of-phase review rather than self-certifying, since it is the phase's one Critical-review gate.

## No deviations from files_modified

Only the plan's declared files touched: `policies/gxp_rules.rego`, `policies/gxp_rules_test.rego`, `policies/opa-gate.sh`, `policies/BIBLE-DEVIATIONS.md`, `policies/README.md`. `docker-compose.yml`, `.env.example`, root `README.md`, `BRANCHING.md` untouched.

STATE.md and ROADMAP.md not modified — left for the orchestrator.
