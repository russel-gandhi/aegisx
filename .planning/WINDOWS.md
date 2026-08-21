---
schema_version: 1
open_count: 0
waived_count: 0
fixed_count: 1
total_count: 1
last_updated: 2026-08-21T11:06:34.000Z
---

# Broken Windows Ledger

> Cross-phase defect register. With `workflow.windows_enforce` enabled, `/gsd-ship` blocks while `open_count > 0`.
> Waive with `gsd-tools windows waive <id> "<reason>"` (reason required).
> Mark fixed with `gsd-tools windows fixed <id>`.

| id | phase | kind | file | line | description | status | reason | recorded_at | resolved_at |
|----|-------|------|------|------|-------------|--------|--------|-------------|-------------|
| 1 | 03 | deviation | backend/app/agents/c1_verifier.py |  | build_opa_payload() queries every rule-input table using the finding's own evidence_ids; for ANNEX11-S4-TRC-001 (rule 5) this fetches test_cases by the requirement id instead of the linked test_case_id, so the traceability finding never corroborates against OPA (scores INSUFFICIENT_EVIDENCE, not MEDIUM). Discovered in 03-04, out of its file-boundary scope to fix; likely also affects ANNEX11-S10-CHG-001 (rule 10, same multi-input-key shape). | fixed | Fixed in plan 03-05: RULE_OPA_INPUT gained a fourth id_source element (evidence_ids / via / by_column) so build_opa_payload() resolves the correct linked table for both ANNEX11-S4-TRC-001 (test_cases via requirements.test_case_id) and ANNEX11-S10-CHG-001 (change_actions by change_actions.change_id), still with no per-rule branching. Verified against live Postgres + live OPA: both rules now corroborate. See backend/tests/test_c1_verifier.py::test_integration_rule_5_payload_test_cases_object_shape_and_corroborates and ::test_integration_rule_10_payload_carries_both_changes_and_change_actions_keys, and backend/README.md's "C1 Critical-review coverage (SENT-2-12)" section. | 2026-08-21T10:29:53.485Z | 2026-08-21T11:06:34.000Z |

````json
[
  {
    "id": 1,
    "kind": "deviation",
    "phase": "03",
    "file": "backend/app/agents/c1_verifier.py",
    "line": null,
    "description": "build_opa_payload() queries every rule-input table using the finding's own evidence_ids; for ANNEX11-S4-TRC-001 (rule 5) this fetches test_cases by the requirement id instead of the linked test_case_id, so the traceability finding never corroborates against OPA (scores INSUFFICIENT_EVIDENCE, not MEDIUM). Discovered in 03-04, out of its file-boundary scope to fix; likely also affects ANNEX11-S10-CHG-001 (rule 10, same multi-input-key shape).",
    "status": "fixed",
    "reason": "Fixed in plan 03-05: RULE_OPA_INPUT gained a fourth id_source element (evidence_ids / via / by_column) so build_opa_payload() resolves the correct linked table for both ANNEX11-S4-TRC-001 (test_cases via requirements.test_case_id) and ANNEX11-S10-CHG-001 (change_actions by change_actions.change_id), still with no per-rule branching. Verified against live Postgres + live OPA: both rules now corroborate. See backend/tests/test_c1_verifier.py::test_integration_rule_5_payload_test_cases_object_shape_and_corroborates and ::test_integration_rule_10_payload_carries_both_changes_and_change_actions_keys, and backend/README.md's \"C1 Critical-review coverage (SENT-2-12)\" section.",
    "recorded_at": "2026-08-21T10:29:53.485Z",
    "resolved_at": "2026-08-21T11:06:34.000Z"
  }
]
````
