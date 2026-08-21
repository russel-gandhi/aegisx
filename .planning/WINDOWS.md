---
schema_version: 1
open_count: 1
waived_count: 0
fixed_count: 0
total_count: 1
last_updated: 2026-08-21T10:29:53.485Z
---

# Broken Windows Ledger

> Cross-phase defect register. With `workflow.windows_enforce` enabled, `/gsd-ship` blocks while `open_count > 0`.
> Waive with `gsd-tools windows waive <id> "<reason>"` (reason required).
> Mark fixed with `gsd-tools windows fixed <id>`.

| id | phase | kind | file | line | description | status | reason | recorded_at | resolved_at |
|----|-------|------|------|------|-------------|--------|--------|-------------|-------------|
| 1 | 03 | deviation | backend/app/agents/c1_verifier.py |  | build_opa_payload() queries every rule-input table using the finding's own evidence_ids; for ANNEX11-S4-TRC-001 (rule 5) this fetches test_cases by the requirement id instead of the linked test_case_id, so the traceability finding never corroborates against OPA (scores INSUFFICIENT_EVIDENCE, not MEDIUM). Discovered in 03-04, out of its file-boundary scope to fix; likely also affects ANNEX11-S10-CHG-001 (rule 10, same multi-input-key shape). | open |  | 2026-08-21T10:29:53.485Z |  |

````json
[
  {
    "id": 1,
    "kind": "deviation",
    "phase": "03",
    "file": "backend/app/agents/c1_verifier.py",
    "line": null,
    "description": "build_opa_payload() queries every rule-input table using the finding's own evidence_ids; for ANNEX11-S4-TRC-001 (rule 5) this fetches test_cases by the requirement id instead of the linked test_case_id, so the traceability finding never corroborates against OPA (scores INSUFFICIENT_EVIDENCE, not MEDIUM). Discovered in 03-04, out of its file-boundary scope to fix; likely also affects ANNEX11-S10-CHG-001 (rule 10, same multi-input-key shape).",
    "status": "open",
    "reason": "",
    "recorded_at": "2026-08-21T10:29:53.485Z",
    "resolved_at": null
  }
]
````
