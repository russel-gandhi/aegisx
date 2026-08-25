# Deferred Items — Phase 05 Safety & Remediation

Items discovered during execution that are out of the current plan's declared
scope (`<files>`) and were therefore logged, not fixed, per the executor's
scope-boundary rule.

## Logged during 05-05

**13 pre-existing backend test failures, unrelated to plan 05-05's scope**
(`backend/app/ws/copilot.py`, `backend/app/routes/actions.py`,
`backend/tests/test_ws_broadcast.py`). Confirmed present on the pre-05-05
baseline (immediately after fast-forwarding this worktree to `main` at
`5cbff8c`, before any 05-05 edit) and unchanged after all three of 05-05's
tasks — same 13 failing, same 294 passing both times:

- `tests/test_c1_verifier.py::test_negative_positive_control_truthful_claim_against_real_row_scores_medium`
- `tests/test_c1_verifier.py::test_integration_run_c1_mixed_list_returns_three_distinct_graded_entries`
- `tests/test_c1_verifier.py::test_integration_ten_rules_verify_finding_grades_and_at_least_eight_corroborate`
- `tests/test_c1_verifier.py::test_integration_rule_5_payload_test_cases_object_shape_and_corroborates`
- `tests/test_hero_loop.py::test_hero_fully_mocked_run_at_least_one_finding_verified_medium_or_better`
- `tests/test_hero_loop.py::test_hero_keyless_run_falls_back_to_full_agent_set_and_deterministic_fallback`
- `tests/test_hero_tracer.py::test_success_path_real_finding_verified_medium_confidence`
- `tests/test_hero_tracer.py::test_degraded_path_no_provider_key_same_finding_and_score`
- `tests/test_opa_client.py::test_live_single_document_positive_case_returns_annex11_s4_doc_001`
- `tests/test_opa_client.py::test_live_whole_bundle_all_10_seeded_gaps_produce_exactly_10_violations`
- `tests/test_opa_client.py::test_every_returned_violation_validates_as_opa_violation_model`
- `tests/test_opa_client.py::test_payload_containing_datetime_value_does_not_raise_typeerror`
- `tests/test_routes_findings.py::test_integration_periodic_evaluation_card_grades_medium_with_real_evidence`

Root cause (spot-checked one, not all): `evaluate_opa_policy()` against the
live OPA sidecar at `127.0.0.1:8181` returns zero violations for a payload
the seeded Rego bundle should flag (`test_live_single_document_positive_case_returns_annex11_s4_doc_001`
asserts `len(violations) == 1`, gets `0`). This points at the OPA
policy bundle/container drifting from what these tests expect (stale
bundle load, or a bundle-reload gap after a container restart), not at
application code this plan touches. `test_c1_verifier.py`/`test_hero_loop.py`/
`test_hero_tracer.py`/`test_routes_findings.py` failures are downstream of
the same OPA-corroboration path.

**Action:** none taken (out of scope for 05-05, no plan file in
`backend/app/opa_client.py`, `backend/app/agents/c1_verifier.py`,
`infra/opa/*` was touched). Flagged here for a future OPA/Rego-owning
plan (or `/gsd-secure-phase 05`) to investigate the bundle/container state.
