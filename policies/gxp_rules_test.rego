package sentinel.gxp_test

import data.sentinel.gxp

# Pinned reference clock for every date-dependent fixture in this suite.
# All date fixtures below are computed as an offset from this constant
# (via NS_PER_DAY), never from time.now_ns() directly, so the suite's
# pass/fail meaning does not drift as real wall-clock time passes.
# Mocked into every date-dependent test via `with time.now_ns as PINNED_NOW_NS`.
PINNED_NOW_NS := 1755648000000000000

NS_PER_DAY := 86400000000000

HOUR_NS := 3600000000000

days_before(n) := PINNED_NOW_NS - (n * NS_PER_DAY)

days_after(n) := PINNED_NOW_NS + (n * NS_PER_DAY)

# A fraction of a day past exactly `n` days overdue — the boundary-plus-
# epsilon fixture that would be missed by day-granularity offsets alone.
days_before_plus_hour(n) := PINNED_NOW_NS - (n * NS_PER_DAY) - HOUR_NS

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

# ============================================================
# Task 3 — Critical-review edge-case tier (BRANCHING.md §4/§6)
# ============================================================

# --- Threshold boundaries ---
# For each of the four rules with a non-zero day threshold (30, 365, 7,
# 365): exactly-at-threshold must NOT fire; a fraction of a day past it
# MUST fire. This is where an off-by-one in days_elapsed's division
# would show up and nowhere else.

test_rule2_exactly_30_days_overdue_does_not_violate if {
    inp := {"access_reviews": [{
        "id": "AR-2026-05", "system_id": "GXP-MFG-DEMO-01",
        "status": "PENDING", "scheduled_date_ns": days_before(30),
    }]}
    count(gxp.violation) == 0 with input as inp with time.now_ns as PINNED_NOW_NS
}

test_rule2_fraction_past_30_days_overdue_violates if {
    inp := {"access_reviews": [{
        "id": "AR-2026-05", "system_id": "GXP-MFG-DEMO-01",
        "status": "PENDING", "scheduled_date_ns": days_before_plus_hour(30),
    }]}
    violations := gxp.violation with input as inp with time.now_ns as PINNED_NOW_NS
    count(violations) == 1
    some v in violations
    v.rule_id == "ANNEX11-S12-ACC-001"
}

test_rule3_exactly_365_days_since_review_does_not_violate if {
    inp := {"risks": [{
        "id": "RSK-2024-11", "system_id": "GXP-MFG-DEMO-01",
        "last_review_date_ns": days_before(365),
    }]}
    count(gxp.violation) == 0 with input as inp with time.now_ns as PINNED_NOW_NS
}

test_rule3_fraction_past_365_days_since_review_violates if {
    inp := {"risks": [{
        "id": "RSK-2024-11", "system_id": "GXP-MFG-DEMO-01",
        "last_review_date_ns": days_before_plus_hour(365),
    }]}
    violations := gxp.violation with input as inp with time.now_ns as PINNED_NOW_NS
    count(violations) == 1
    some v in violations
    v.rule_id == "ICH-Q9-RSK-001"
}

test_rule4_exactly_7_days_open_no_rca_does_not_violate if {
    inp := {"incidents": [{
        "id": "INC-849201", "system_id": "GXP-MFG-DEMO-01",
        "severity": "P1", "status": "OPEN", "rca_started": false,
        "opened_date_ns": days_before(7),
    }]}
    count(gxp.violation) == 0 with input as inp with time.now_ns as PINNED_NOW_NS
}

test_rule4_fraction_past_7_days_open_no_rca_violates if {
    inp := {"incidents": [{
        "id": "INC-849201", "system_id": "GXP-MFG-DEMO-01",
        "severity": "P1", "status": "OPEN", "rca_started": false,
        "opened_date_ns": days_before_plus_hour(7),
    }]}
    violations := gxp.violation with input as inp with time.now_ns as PINNED_NOW_NS
    count(violations) == 1
    some v in violations
    v.rule_id == "ANNEX11-S13-INC-001"
}

test_rule8_exactly_365_days_stale_does_not_violate if {
    inp := {"gxp_systems": [{
        "id": "GXP-MFG-DEMO-01", "last_backup_test_ns": days_before(365),
    }]}
    count(gxp.violation) == 0 with input as inp with time.now_ns as PINNED_NOW_NS
}

test_rule8_fraction_past_365_days_stale_violates if {
    inp := {"gxp_systems": [{
        "id": "GXP-MFG-DEMO-01", "last_backup_test_ns": days_before_plus_hour(365),
    }]}
    violations := gxp.violation with input as inp with time.now_ns as PINNED_NOW_NS
    count(violations) == 1
    some v in violations
    v.rule_id == "ANNEX11-S16-BCK-001"
}

# --- Future-dated records (regression guard for Finding B) ---
# Rules 6 and 7 use a `> 0` threshold. Under the Bible's original
# `time.diff(...)` form, `time.diff` reports a non-negative magnitude
# regardless of direction, so a record due in the FUTURE would still
# have satisfied `[2] > 0` on many days and incorrectly fired. days_elapsed
# is signed, so a future-dated record yields a negative value and must
# never fire. These are the regression fixtures for Finding B.

test_rule6_future_due_date_does_not_violate_finding_b_regression if {
    inp := {"suppliers": [{
        "id": "SUP-2026-01", "system_id": "GXP-MFG-DEMO-01",
        "reassessment_due_date_ns": days_after(45),
    }]}
    count(gxp.violation) == 0 with input as inp with time.now_ns as PINNED_NOW_NS
}

test_rule7_future_due_date_does_not_violate_finding_b_regression if {
    inp := {"periodic_evaluations": [{
        "id": "PE-2024-01", "system_id": "GXP-MFG-DEMO-01",
        "due_date_ns": days_after(45),
    }]}
    count(gxp.violation) == 0 with input as inp with time.now_ns as PINNED_NOW_NS
}

# --- Absent input keys ---
# A rule that errors on a missing top-level key would take down an
# entire evaluate_opa_policy() call in Phase 3 whenever an agent sends a
# partial payload.

test_empty_input_object_returns_empty_set_no_error if {
    count(gxp.violation) == 0 with input as {}
}

# --- Absent fields within a record ---
# Rule 4: an incident with no `rca_started` key at all. Rego's
# `not inc.rca_started` succeeds for both "false" and "absent" — this
# fixture pins that intended behaviour rather than leaving it accidental.

test_rule4_absent_rca_started_key_still_violates if {
    inp := {"incidents": [{
        "id": "INC-849201", "system_id": "GXP-MFG-DEMO-01",
        "severity": "P1", "status": "OPEN",
        "opened_date_ns": days_before(47),
    }]}
    violations := gxp.violation with input as inp with time.now_ns as PINNED_NOW_NS
    count(violations) == 1
    some v in violations
    v.rule_id == "ANNEX11-S13-INC-001"
}

# --- Rule 5's map shape: dangling test_case_id reference ---
# A requirement whose test_case_id has no matching key in
# input.test_cases must not be reported as a traceability failure with a
# wrong/undefined record ID — it must simply produce no violation.

test_rule5_dangling_test_case_reference_does_not_violate if {
    inp := {
        "requirements": [{"id": "URS-042", "system_id": "GXP-MFG-DEMO-01", "test_case_id": "TC-MISSING"}],
        "test_cases": {},
    }
    count(gxp.violation) == 0 with input as inp
}

# --- Whole-bundle integration ---
# All 10 seeded gap records (Bible Section 5 shapes) supplied together,
# exactly as a caller assembling live Postgres rows would build the
# payload. Proves the 10 rules compose without interfering — the
# integration leg of the Critical-review bar that per-rule fixtures
# cannot show.

test_whole_bundle_all_10_seeded_gaps_produce_exactly_10_violations if {
    inp := {
        "documents": [{
            "id": "DOC-2026-OM-99", "system_id": "GXP-MFG-DEMO-01",
            "doc_type": "O&M", "status": "DRAFT",
        }],
        "access_reviews": [{
            "id": "AR-2026-05", "system_id": "GXP-MFG-DEMO-01",
            "status": "PENDING", "scheduled_date_ns": days_before(98),
        }],
        "risks": [{
            "id": "RSK-2024-11", "system_id": "GXP-MFG-DEMO-01",
            "last_review_date_ns": days_before(730),
        }],
        "incidents": [{
            "id": "INC-849201", "system_id": "GXP-MFG-DEMO-01",
            "severity": "P1", "status": "OPEN", "rca_started": false,
            "opened_date_ns": days_before(47),
        }],
        "requirements": [{
            "id": "URS-042", "system_id": "GXP-MFG-DEMO-01", "test_case_id": "TC-2026-042",
        }],
        "test_cases": {"TC-2026-042": {"status": "DRAFT"}},
        "suppliers": [{
            "id": "SUP-2026-01", "system_id": "GXP-MFG-DEMO-01",
            "reassessment_due_date_ns": days_before(180),
        }],
        "periodic_evaluations": [{
            "id": "PE-2024-01", "system_id": "GXP-MFG-DEMO-01",
            "due_date_ns": days_before(600),
        }],
        "gxp_systems": [{
            "id": "GXP-MFG-DEMO-01", "last_backup_test_ns": days_before(400),
        }],
        "access_records": [{
            "id": "ACC-2026-99", "system_id": "GXP-MFG-DEMO-01",
            "is_privileged": true, "user_status": "DEPARTED",
        }],
        "changes": [{"id": "CR-2026-089", "system_id": "GXP-MFG-DEMO-01", "status": "CLOSED"}],
        "change_actions": [{"id": "CA-2026-089-1", "change_id": "CR-2026-089", "status": "OPEN"}],
    }
    violations := gxp.violation with input as inp with time.now_ns as PINNED_NOW_NS
    count(violations) == 10
    got_ids := {v.rule_id | some v in violations}
    want_ids := {
        "ANNEX11-S4-DOC-001", "ANNEX11-S12-ACC-001", "ICH-Q9-RSK-001",
        "ANNEX11-S13-INC-001", "ANNEX11-S4-TRC-001", "ANNEX11-S3-SUP-001",
        "ANNEX11-S11-PE-001", "ANNEX11-S16-BCK-001", "ANNEX11-S12-ACC-002",
        "ANNEX11-S10-CHG-001",
    }
    got_ids == want_ids
}

# --- Healthy-system negative ---
# BUS-IT-DEMO-02-shaped clean records across every table. A bundle that
# fires on everything is as useless as one that fires on nothing.

test_healthy_system_produces_zero_violations if {
    inp := {
        "documents": [{
            "id": "DOC-2026-SOP-01", "system_id": "BUS-IT-DEMO-02",
            "doc_type": "O&M", "status": "APPROVED",
        }],
        "access_reviews": [{
            "id": "AR-2026-06", "system_id": "BUS-IT-DEMO-02",
            "status": "COMPLETE", "scheduled_date_ns": days_before(10),
        }],
        "risks": [{
            "id": "RSK-2026-01", "system_id": "BUS-IT-DEMO-02",
            "last_review_date_ns": days_before(30),
        }],
        "incidents": [{
            "id": "INC-2026-01", "system_id": "BUS-IT-DEMO-02",
            "severity": "P2", "status": "OPEN", "rca_started": false,
            "opened_date_ns": days_before(2),
        }],
        "requirements": [{
            "id": "URS-100", "system_id": "BUS-IT-DEMO-02", "test_case_id": "TC-2026-100",
        }],
        "test_cases": {"TC-2026-100": {"status": "EXECUTED"}},
        "suppliers": [{
            "id": "SUP-2026-02", "system_id": "BUS-IT-DEMO-02",
            "reassessment_due_date_ns": days_after(90),
        }],
        "periodic_evaluations": [{
            "id": "PE-2026-01", "system_id": "BUS-IT-DEMO-02",
            "due_date_ns": days_after(90),
        }],
        "gxp_systems": [{
            "id": "BUS-IT-DEMO-02", "last_backup_test_ns": days_before(10),
        }],
        "access_records": [{
            "id": "ACC-2026-01", "system_id": "BUS-IT-DEMO-02",
            "is_privileged": true, "user_status": "ACTIVE",
        }],
        "changes": [{"id": "CR-2026-001", "system_id": "BUS-IT-DEMO-02", "status": "CLOSED"}],
        "change_actions": [{"id": "CA-2026-001-1", "change_id": "CR-2026-001", "status": "CLOSED"}],
    }
    count(gxp.violation) == 0 with input as inp with time.now_ns as PINNED_NOW_NS
}
