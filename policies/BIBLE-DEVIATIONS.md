# Bible Deviations — Rego Policy Bundle (SENT-1-03)

This file records every point where `policies/gxp_rules.rego` and
`policies/gxp_rules_test.rego` depart from the literal text of
`AegisX-AI-Project-Bible-v6.md` Section 3.3 (lines 406-546).

**Per CLAUDE.md ("when bible content and a ticket contract disagree, the
bible wins" / "drift is reconciled explicitly"), this file is input to
the final bible-reconciliation review, ticket `SENT-7-05`.** It exists so
that no deviation is silent — every difference between the shipped policy
and Section 3.3 is written down, with its reason, before that review
happens.

**What was NOT changed, in any deviation below:** no rule ID, no
severity, no `# Source:` regulatory citation, no description string, and
no threshold constant (30, 365, 7, 0, 365) was altered from Section 3.3.
Every deviation is either a syntax-compatibility fix or a single field
reference correction forced by the actual database schema (Bible Section
4.1) — never a change to what a rule asserts.

---

## Deviation 1 — Rego v0 partial-set syntax rewritten to Rego v1 (`contains`/`if`)

**Bible says:** All 10 rules use the v0 partial-set rule-head form,
e.g. `violation[{...}] { ... }`.

**Implemented:** `violation contains {...} if {...}` — the Rego v1
rule-head form, applied identically to all 10 rules.

**Why:** `docker-compose.yml` runs `openpolicyagent/opa:1.19.1-debug`
(certified healthy in Phase 1). OPA 1.0+ parses Rego v1 by default, and
v1 requires the `contains` and `if` keywords on partial-set rules.
Transcribing the Bible's v0 syntax verbatim fails `opa test` and
`opa check` with `"contains" keyword is required for partial set rules`.

**Evidence:** 02-RESEARCH.md lines 445-468 (verified against OPA's own
v0-upgrade guide, openpolicyagent.org/docs/v0-upgrade). Confirmed live in
this session: `opa test policies/` passes 42/42 with the v1 form; the
verbatim v0 form was not separately re-tested here because the syntax
incompatibility is already documented and cited in RESEARCH.md.

**Scope:** Mechanical, rule-head syntax only. No rule body, condition,
field name, severity, or citation was changed.

---

## Deviation 2 — `days_elapsed(ts)` replaces `time.diff(time.now_ns(), ts)[2]`

**Bible says:** Rules 2, 3, 4, 6, 7, and 8 gate on
`time.diff(time.now_ns(), ts)[2] > N` (or `> 0` for rules 6/7).

**Implemented:** A shared helper,
`days_elapsed(ts) := (time.now_ns() - ts) / 86400000000000`, used by all
six rules in place of the `time.diff(...)[2]` expression. Every threshold
constant (30, 365, 7, 0, 365) is unchanged.

**Why:** `time.diff` returns `[years, months, days, hours, minutes,
seconds]` — a *calendar breakdown* of the difference between two
timestamps. Index `[2]` is the day-of-month remainder within that
breakdown, not a total elapsed-day count. Concretely: `[2] > 365` can
never be true (a calendar day-remainder cannot exceed ~30), and
`[2] > 30` is true on at most a single boundary day per month. Applied
literally, rules 2, 3, 4, 6, 7, and 8 never fire against any real record
— including the seeded gap records (`AR-2026-05`, `RSK-2024-11`,
`INC-849201`, `SUP-2026-01`, `PE-2024-01`, `GXP-MFG-DEMO-01`'s
`last_backup_test_ns`) that exist specifically to trigger them.
Additionally, `time.diff` normalises to a non-negative magnitude
regardless of which timestamp is earlier, so the Bible's `> 0` form
(rules 6 and 7) would also fire on records that are not yet due — a
false positive in the opposite direction.

POL-01 requires a passing *positive* fixture for every rule, which is
structurally impossible under the literal `time.diff(...)[2]` form for
six of the ten rules — the correction is forced by the requirement
itself, not a design preference.

`days_elapsed` is deliberately **signed**: a future-dated `ts` yields a
negative value and therefore fails every `> N` threshold, which is what
makes rules 6 and 7's "not yet due" fixtures behave correctly and closes
the false-positive direction above.

**Evidence:** 02-RESEARCH.md's `<critical_findings>` Finding B (also
carried into 02-02-PLAN.md `<critical_findings>`). Confirmed live in this
session:
- `opa test` passes a positive fixture for all six affected rules (e.g.
  `test_rule2_pending_review_98_days_overdue_violates`,
  `test_rule8_system_backup_test_400_days_stale_violates`).
- Boundary fixtures (`test_rule2_exactly_30_days_overdue_does_not_violate`
  / `test_rule2_fraction_past_30_days_overdue_violates`, and equivalents
  for rules 3, 4, 8) prove the division has no off-by-one.
- Future-dated regression fixtures
  (`test_rule6_future_due_date_does_not_violate_finding_b_regression`,
  `test_rule7_future_due_date_does_not_violate_finding_b_regression`)
  prove the sign correction closes the false-positive direction that
  `time.diff`'s magnitude-only behaviour would have produced.

**Scope:** Only the elapsed-time computation changed. The `[years,
months, ...]` calendar-breakdown builtin is no longer used; the
comparison operators, field names, and every threshold constant are
unchanged from Section 3.3.

---

## Deviation 3 — Rule 8 emits `sys.id` for `system_id`, not `sys.system_id`

**Bible says:** Rule 8 (`ANNEX11-S16-BCK-001`) emits
`"system_id": sys.system_id, "record_id": sys.id`.

**Implemented:** `"system_id": sys.id, "record_id": sys.id` — both keys
resolve to the same field.

**Why:** Bible Section 4.1's actual `gxp_systems` DDL has no
`system_id` column; its primary key is `id`
(`CREATE TABLE gxp_systems (id VARCHAR(50) PRIMARY KEY, ...)`). Rule 8's
own `# Input shape:` comment in Section 3.3 confirms this:
`{"gxp_systems": [{"id": "...", "last_backup_test_ns": ...}]}` — no
`system_id` key is present in the shape the Bible itself documents for
this rule. Referencing `sys.system_id` against that shape is undefined in
Rego, which makes the entire rule body undefined and silently suppresses
every violation — the rule would parse, load, serve over REST, and always
report zero findings for a stale backup. For a system-level finding, the
system record *is* the record being flagged, so both `system_id` and
`record_id` are correctly the same value: `sys.id`.

**Evidence:** Bible Section 4.1 (`gxp_systems` DDL, no `system_id`
column) cross-checked against Bible Section 3.3's own rule-8 input-shape
comment. Confirmed live in this session:
`test_rule8_system_backup_test_400_days_stale_violates` supplies an input
containing no `system_id` key anywhere and asserts the violation's
`record_id` and `system_id` both equal `GXP-MFG-DEMO-01`.

**Scope:** Field reference only. Rule ID, severity, citation, threshold
(365), and description string are unchanged.

---

## Deviation 4 — Deterministic-clock mechanism: built-in `time.now_ns` mocking

**Bible says:** Nothing — the Bible's rules call `time.now_ns()`
directly with no test-mocking mechanism specified, since the Bible does
not include an `opa test` fixture suite.

**Implemented:** All six date-dependent rules read the reference clock
through `time.now_ns()` inside the shared `days_elapsed(ts)` helper.
Tests pin that clock deterministically using OPA's built-in `with`
keyword: `... with time.now_ns as PINNED_NOW_NS`. Production callers
(the live OPA server, `evaluate_opa_policy()` in Phase 3) make no such
substitution and get the real wall clock.

**Why:** Task 1 required proving a deterministic-clock mechanism before
writing the six date-dependent rules in Task 2, per the plan's stated
fallback order: prefer built-in `time.now_ns` mocking, and only fall back
to an `input.now_ns` override field if that mocking is rejected by this
OPA build.

**Evidence:** Confirmed live in this session against OPA 1.19.1 (via a
throwaway probe test in Task 1, since deleted per the plan's own
instruction once the mechanism was settled): `time.now_ns() == N with
time.now_ns as N` evaluates true. All 42 fixtures in
`policies/gxp_rules_test.rego` use this mechanism; none reads
`time.now_ns()` unmocked, so the suite's pass/fail result cannot drift as
real wall-clock time passes.

**Scope:** Test-suite mechanism only. No production rule logic changed;
`days_elapsed(ts)` calls the real, unmocked `time.now_ns()` in
production.

---

## Verification method note (parallel-worktree execution)

This plan (02-02) executed in an isolated git worktree, in parallel with
sibling plans 02-01/02-03/02-04 on disjoint files. The long-running
`opa` container from `docker-compose.yml` (already healthy from Phase 1)
has its `./policies:/policies:ro` bind mount resolved against the main
repository checkout, not this worktree — confirmed by inspection
(`docker compose exec -T opa ls -la /policies` from inside the worktree
showed only the pre-existing `README.md`, not this plan's new `.rego`
files). Editing files in this worktree therefore cannot be observed by
that shared container until this branch merges back to the main
checkout.

All `opa test` and live-REST verification described above (and the 42/42
pass count, the boundary fixtures, and the constant-break regression
check) was instead performed against a disposable, ephemeral OPA server
container (`docker run` with the worktree's `policies/` directory bind
mounted, same `gxp-sentinel-opa` image, same `opa run --server` command)
so the rules were exercised on the exact OPA 1.19.1 binary this repo
runs, without touching or disrupting the shared Phase-1 container or any
concurrently-running sibling plan. The plan's literal verification
sequence (`docker compose restart opa && bash infra/health-check.sh opa
&& bash policies/opa-gate.sh` against `127.0.0.1:8181`) should be (and
was designed to be) re-run once this branch is merged into the main
checkout, at which point the shared container's bind mount will actually
reflect these files.
