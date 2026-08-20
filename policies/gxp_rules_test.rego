package sentinel.gxp_test

import data.sentinel.gxp

# Pinned reference clock for every date-dependent fixture in this suite.
# All date fixtures below are computed as an offset from this constant
# (via NS_PER_DAY), never from time.now_ns() directly, so the suite's
# pass/fail meaning does not drift as real wall-clock time passes.
# Mocked into every date-dependent test via `with time.now_ns as PINNED_NOW_NS`.
PINNED_NOW_NS := 1755648000000000000

NS_PER_DAY := 86400000000000

days_before(n) := PINNED_NOW_NS - (n * NS_PER_DAY)

days_after(n) := PINNED_NOW_NS + (n * NS_PER_DAY)

# --- Rule 1: ANNEX11-S4-DOC-001 (O&M document must be APPROVED) ---

test_rule1_draft_om_document_violates if {
    input_doc := {"documents": [{
        "id": "DOC-2026-OM-99", "system_id": "GXP-MFG-DEMO-01",
        "doc_type": "O&M", "status": "DRAFT",
    }]}
    violations := gxp.violation with input as input_doc
    count(violations) == 1
    some v in violations
    v.rule_id == "ANNEX11-S4-DOC-001"
    v.record_id == "DOC-2026-OM-99"
}

test_rule1_approved_om_document_does_not_violate if {
    input_doc := {"documents": [{
        "id": "DOC-2026-OM-99", "system_id": "GXP-MFG-DEMO-01",
        "doc_type": "O&M", "status": "APPROVED",
    }]}
    count(gxp.violation) == 0 with input as input_doc
}

test_rule1_non_om_doc_type_does_not_violate if {
    input_doc := {"documents": [{
        "id": "DOC-2026-SOP-01", "system_id": "GXP-MFG-DEMO-01",
        "doc_type": "SOP", "status": "DRAFT",
    }]}
    count(gxp.violation) == 0 with input as input_doc
}

test_rule1_empty_documents_array_does_not_violate_or_error if {
    count(gxp.violation) == 0 with input as {"documents": []}
}

# --- Rule 2: ANNEX11-S12-ACC-001 (access review overdue > 30 days) ---

test_rule2_pending_review_98_days_overdue_violates if {
    inp := {"access_reviews": [{
        "id": "AR-2026-05", "system_id": "GXP-MFG-DEMO-01",
        "status": "PENDING", "scheduled_date_ns": days_before(98),
    }]}
    violations := gxp.violation with input as inp with time.now_ns as PINNED_NOW_NS
    count(violations) == 1
    some v in violations
    v.rule_id == "ANNEX11-S12-ACC-001"
    v.record_id == "AR-2026-05"
}

test_rule2_pending_review_10_days_overdue_does_not_violate if {
    inp := {"access_reviews": [{
        "id": "AR-2026-05", "system_id": "GXP-MFG-DEMO-01",
        "status": "PENDING", "scheduled_date_ns": days_before(10),
    }]}
    count(gxp.violation) == 0 with input as inp with time.now_ns as PINNED_NOW_NS
}

test_rule2_complete_review_98_days_overdue_does_not_violate if {
    inp := {"access_reviews": [{
        "id": "AR-2026-05", "system_id": "GXP-MFG-DEMO-01",
        "status": "COMPLETE", "scheduled_date_ns": days_before(98),
    }]}
    count(gxp.violation) == 0 with input as inp with time.now_ns as PINNED_NOW_NS
}

# --- Rule 3: ICH-Q9-RSK-001 (risk review exceeds 12-month cycle) ---

test_rule3_risk_reviewed_730_days_ago_violates if {
    inp := {"risks": [{
        "id": "RSK-2024-11", "system_id": "GXP-MFG-DEMO-01",
        "last_review_date_ns": days_before(730),
    }]}
    violations := gxp.violation with input as inp with time.now_ns as PINNED_NOW_NS
    count(violations) == 1
    some v in violations
    v.rule_id == "ICH-Q9-RSK-001"
    v.record_id == "RSK-2024-11"
}

test_rule3_risk_reviewed_100_days_ago_does_not_violate if {
    inp := {"risks": [{
        "id": "RSK-2024-11", "system_id": "GXP-MFG-DEMO-01",
        "last_review_date_ns": days_before(100),
    }]}
    count(gxp.violation) == 0 with input as inp with time.now_ns as PINNED_NOW_NS
}

# --- Rule 4: ANNEX11-S13-INC-001 (P1 incident > 7 days, no RCA) ---

test_rule4_p1_open_no_rca_47_days_violates if {
    inp := {"incidents": [{
        "id": "INC-849201", "system_id": "GXP-MFG-DEMO-01",
        "severity": "P1", "status": "OPEN", "rca_started": false,
        "opened_date_ns": days_before(47),
    }]}
    violations := gxp.violation with input as inp with time.now_ns as PINNED_NOW_NS
    count(violations) == 1
    some v in violations
    v.rule_id == "ANNEX11-S13-INC-001"
    v.record_id == "INC-849201"
}

test_rule4_p1_open_rca_started_47_days_does_not_violate if {
    inp := {"incidents": [{
        "id": "INC-849201", "system_id": "GXP-MFG-DEMO-01",
        "severity": "P1", "status": "OPEN", "rca_started": true,
        "opened_date_ns": days_before(47),
    }]}
    count(gxp.violation) == 0 with input as inp with time.now_ns as PINNED_NOW_NS
}

test_rule4_p2_open_no_rca_47_days_does_not_violate if {
    inp := {"incidents": [{
        "id": "INC-849201", "system_id": "GXP-MFG-DEMO-01",
        "severity": "P2", "status": "OPEN", "rca_started": false,
        "opened_date_ns": days_before(47),
    }]}
    count(gxp.violation) == 0 with input as inp with time.now_ns as PINNED_NOW_NS
}

test_rule4_p1_closed_no_rca_47_days_does_not_violate if {
    inp := {"incidents": [{
        "id": "INC-849201", "system_id": "GXP-MFG-DEMO-01",
        "severity": "P1", "status": "CLOSED", "rca_started": false,
        "opened_date_ns": days_before(47),
    }]}
    count(gxp.violation) == 0 with input as inp with time.now_ns as PINNED_NOW_NS
}

# --- Rule 5: ANNEX11-S4-TRC-001 (requirement lacks executed test evidence) ---

test_rule5_requirement_with_draft_test_case_violates if {
    inp := {
        "requirements": [{"id": "URS-042", "system_id": "GXP-MFG-DEMO-01", "test_case_id": "TC-2026-042"}],
        "test_cases": {"TC-2026-042": {"status": "DRAFT"}},
    }
    violations := gxp.violation with input as inp
    count(violations) == 1
    some v in violations
    v.rule_id == "ANNEX11-S4-TRC-001"
    v.record_id == "URS-042"
}

test_rule5_requirement_with_executed_test_case_does_not_violate if {
    inp := {
        "requirements": [{"id": "URS-042", "system_id": "GXP-MFG-DEMO-01", "test_case_id": "TC-2026-042"}],
        "test_cases": {"TC-2026-042": {"status": "EXECUTED"}},
    }
    count(gxp.violation) == 0 with input as inp
}

# --- Rule 6: ANNEX11-S3-SUP-001 (supplier reassessment overdue) ---

test_rule6_supplier_reassessment_due_before_now_violates if {
    inp := {"suppliers": [{
        "id": "SUP-2026-01", "system_id": "GXP-MFG-DEMO-01",
        "reassessment_due_date_ns": days_before(180),
    }]}
    violations := gxp.violation with input as inp with time.now_ns as PINNED_NOW_NS
    count(violations) == 1
    some v in violations
    v.rule_id == "ANNEX11-S3-SUP-001"
    v.record_id == "SUP-2026-01"
}

test_rule6_supplier_reassessment_due_after_now_does_not_violate if {
    inp := {"suppliers": [{
        "id": "SUP-2026-01", "system_id": "GXP-MFG-DEMO-01",
        "reassessment_due_date_ns": days_after(30),
    }]}
    count(gxp.violation) == 0 with input as inp with time.now_ns as PINNED_NOW_NS
}

# --- Rule 7: ANNEX11-S11-PE-001 (periodic evaluation overdue) ---

test_rule7_periodic_evaluation_due_before_now_violates if {
    inp := {"periodic_evaluations": [{
        "id": "PE-2024-01", "system_id": "GXP-MFG-DEMO-01",
        "due_date_ns": days_before(600),
    }]}
    violations := gxp.violation with input as inp with time.now_ns as PINNED_NOW_NS
    count(violations) == 1
    some v in violations
    v.rule_id == "ANNEX11-S11-PE-001"
    v.record_id == "PE-2024-01"
}

test_rule7_periodic_evaluation_due_after_now_does_not_violate if {
    inp := {"periodic_evaluations": [{
        "id": "PE-2024-01", "system_id": "GXP-MFG-DEMO-01",
        "due_date_ns": days_after(30),
    }]}
    count(gxp.violation) == 0 with input as inp with time.now_ns as PINNED_NOW_NS
}

# --- Rule 8: ANNEX11-S16-BCK-001 (backup restore test stale > 365 days) ---
# Fixture input carries no `system_id` key anywhere — proving the rule
# works against the real gxp_systems column set (id is the only PK).

test_rule8_system_backup_test_400_days_stale_violates if {
    inp := {"gxp_systems": [{
        "id": "GXP-MFG-DEMO-01", "last_backup_test_ns": days_before(400),
    }]}
    violations := gxp.violation with input as inp with time.now_ns as PINNED_NOW_NS
    count(violations) == 1
    some v in violations
    v.rule_id == "ANNEX11-S16-BCK-001"
    v.record_id == "GXP-MFG-DEMO-01"
    v.system_id == "GXP-MFG-DEMO-01"
}

test_rule8_system_backup_test_100_days_stale_does_not_violate if {
    inp := {"gxp_systems": [{
        "id": "GXP-MFG-DEMO-01", "last_backup_test_ns": days_before(100),
    }]}
    count(gxp.violation) == 0 with input as inp with time.now_ns as PINNED_NOW_NS
}

# --- Rule 9: ANNEX11-S12-ACC-002 (orphaned privileged account, CRITICAL) ---

test_rule9_privileged_departed_account_violates if {
    inp := {"access_records": [{
        "id": "ACC-2026-99", "system_id": "GXP-MFG-DEMO-01",
        "is_privileged": true, "user_status": "DEPARTED",
    }]}
    violations := gxp.violation with input as inp
    count(violations) == 1
    some v in violations
    v.rule_id == "ANNEX11-S12-ACC-002"
    v.record_id == "ACC-2026-99"
    v.severity == "CRITICAL"
}

test_rule9_privileged_active_account_does_not_violate if {
    inp := {"access_records": [{
        "id": "ACC-2026-99", "system_id": "GXP-MFG-DEMO-01",
        "is_privileged": true, "user_status": "ACTIVE",
    }]}
    count(gxp.violation) == 0 with input as inp
}

test_rule9_nonprivileged_departed_account_does_not_violate if {
    inp := {"access_records": [{
        "id": "ACC-2026-99", "system_id": "GXP-MFG-DEMO-01",
        "is_privileged": false, "user_status": "DEPARTED",
    }]}
    count(gxp.violation) == 0 with input as inp
}

# --- Rule 10: ANNEX11-S10-CHG-001 (change closed with open action) ---

test_rule10_closed_change_with_open_action_violates if {
    inp := {
        "changes": [{"id": "CR-2026-089", "system_id": "GXP-MFG-DEMO-01", "status": "CLOSED"}],
        "change_actions": [{"id": "CA-2026-089-1", "change_id": "CR-2026-089", "status": "OPEN"}],
    }
    violations := gxp.violation with input as inp
    count(violations) == 1
    some v in violations
    v.rule_id == "ANNEX11-S10-CHG-001"
    v.record_id == "CR-2026-089"
}

test_rule10_closed_change_with_closed_action_does_not_violate if {
    inp := {
        "changes": [{"id": "CR-2026-089", "system_id": "GXP-MFG-DEMO-01", "status": "CLOSED"}],
        "change_actions": [{"id": "CA-2026-089-1", "change_id": "CR-2026-089", "status": "CLOSED"}],
    }
    count(gxp.violation) == 0 with input as inp
}

test_rule10_open_change_with_open_action_does_not_violate if {
    inp := {
        "changes": [{"id": "CR-2026-089", "system_id": "GXP-MFG-DEMO-01", "status": "OPEN"}],
        "change_actions": [{"id": "CA-2026-089-1", "change_id": "CR-2026-089", "status": "OPEN"}],
    }
    count(gxp.violation) == 0 with input as inp
}
