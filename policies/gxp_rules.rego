package sentinel.gxp

# days_elapsed(ts) returns the signed count of days from `ts` to the
# reference clock (time.now_ns(); mockable in tests via
# `with time.now_ns as <ns>`, confirmed supported on OPA 1.19.1),
# computed as the nanosecond difference divided by 86400000000000 (ns
# per day).
#
# This replaces the Bible's literal `time.diff(time.now_ns(), ts)[2]`
# expression used in rules 2, 3, 4, 6, 7, and 8. `time.diff` returns
# `[years, months, days, hours, minutes, seconds]` — index `[2]` is the
# *calendar day-of-month remainder* between the two timestamps, not an
# elapsed-day total, so `[2] > 365` can never be true and `[2] > 30` is
# true on at most a single boundary day. `time.diff` also normalises to
# a non-negative magnitude regardless of which timestamp is earlier, so
# the Bible's `> 0` form (rules 6 and 7) would additionally fire on
# records that are not yet due.
#
# days_elapsed is deliberately signed: a future-dated `ts` yields a
# negative value and therefore fails every `> N` threshold below, which
# is what makes the "not yet due" negative fixtures behave correctly.
# Every threshold constant (30, 365, 7, 0, 365) is carried over from the
# Bible unchanged — only the elapsed-time computation is corrected.
# Recorded as a deviation in policies/BIBLE-DEVIATIONS.md.
days_elapsed(ts) := (time.now_ns() - ts) / 86400000000000

# 1. ANNEX11-S4-DOC-001: O&M Manual must be approved
# Source: EU GMP Annex 11, Section 4 (Documentation)
# Input shape: {"documents": [{"id": "...", "system_id": "...", "doc_type": "O&M", "status": "DRAFT"}]}
# Expected Output: violation array containing record_id of DRAFT O&M document.
violation contains {
    "rule_id": "ANNEX11-S4-DOC-001", "severity": "HIGH",
    "system_id": doc.system_id, "record_id": doc.id,
    "description": "O&M Document is not in APPROVED state"
} if {
    doc := input.documents[_]
    doc.doc_type == "O&M"
    doc.status != "APPROVED"
}

# 2. ANNEX11-S12-ACC-001: Access reviews must not be overdue by > 30 days
# Source: EU GMP Annex 11, Section 12 (Security) & 21 CFR 11.10(d)
# Input shape: {"access_reviews": [{"id": "...", "system_id": "...", "status": "PENDING", "scheduled_date_ns": 1715424000000000000}]}
violation contains {
    "rule_id": "ANNEX11-S12-ACC-001", "severity": "HIGH",
    "system_id": rev.system_id, "record_id": rev.id,
    "description": "Access review overdue beyond 30-day grace period"
} if {
    rev := input.access_reviews[_]
    rev.status == "PENDING"
    days_elapsed(rev.scheduled_date_ns) > 30
}

# 3. ICH-Q9-RSK-001: Risk assessments must be reviewed annually
# Source: ICH Q9(R1) Quality Risk Management
# Input shape: {"risks": [{"id": "...", "system_id": "...", "last_review_date_ns": 1723718400000000000}]}
violation contains {
    "rule_id": "ICH-Q9-RSK-001", "severity": "MEDIUM",
    "system_id": rsk.system_id, "record_id": rsk.id,
    "description": "Risk assessment exceeds 12-month review cycle"
} if {
    rsk := input.risks[_]
    days_elapsed(rsk.last_review_date_ns) > 365
}

# 4. ANNEX11-S13-INC-001: P1 Incidents > 7 days require RCA
# Source: EU GMP Annex 11, Section 13 (Incident Management)
# Input shape: {"incidents": [{"id": "...", "system_id": "...", "severity": "P1", "status": "OPEN", "rca_started": false, "opened_date_ns": ...}]}
violation contains {
    "rule_id": "ANNEX11-S13-INC-001", "severity": "HIGH",
    "system_id": inc.system_id, "record_id": inc.id,
    "description": "P1 Incident open > 7 days without documented Root Cause Analysis"
} if {
    inc := input.incidents[_]
    inc.severity == "P1"
    inc.status == "OPEN"
    not inc.rca_started
    days_elapsed(inc.opened_date_ns) > 7
}

# 5. ANNEX11-S4-TRC-001: URS requires linked executed test evidence
# Source: EU GMP Annex 11, Section 4 (Documentation/Traceability)
# Input shape: {"requirements": [...], "test_cases": {"TC-ID": {"status": "DRAFT"}}}
# NOTE: input.test_cases is an OBJECT keyed by test-case ID, not an array
# — the only input key in this bundle with that shape. Callers building
# this payload from Postgres rows must key it by id, not list the rows.
violation contains {
    "rule_id": "ANNEX11-S4-TRC-001", "severity": "HIGH",
    "system_id": req.system_id, "record_id": req.id,
    "description": "Requirement lacks executed test case evidence"
} if {
    req := input.requirements[_]
    test := input.test_cases[req.test_case_id]
    test.status == "DRAFT"
}

# 6. ANNEX11-S3-SUP-001: Supplier reassessment overdue
# Source: EU GMP Annex 11, Section 3 (Suppliers and Service Providers)
# Input shape: {"suppliers": [{"id": "...", "system_id": "...", "reassessment_due_date_ns": 1712000000000000000}]}
violation contains {
    "rule_id": "ANNEX11-S3-SUP-001", "severity": "MEDIUM",
    "system_id": sup.system_id, "record_id": sup.id,
    "description": "Supplier reassessment overdue"
} if {
    sup := input.suppliers[_]
    days_elapsed(sup.reassessment_due_date_ns) > 0
}

# 7. ANNEX11-S11-PE-001: Periodic evaluation overdue
# Source: EU GMP Annex 11, Section 11 (Periodic Evaluation)
# Input shape: {"periodic_evaluations": [{"id": "...", "system_id": "...", "due_date_ns": ...}]}
violation contains {
    "rule_id": "ANNEX11-S11-PE-001", "severity": "HIGH",
    "system_id": pe.system_id, "record_id": pe.id,
    "description": "Periodic evaluation overdue > 12 months"
} if {
    pe := input.periodic_evaluations[_]
    days_elapsed(pe.due_date_ns) > 0
}

# 8. ANNEX11-S16-BCK-001: Backup restore test stale
# Source: EU GMP Annex 11, Section 16 (Business Continuity)
# Input shape: {"gxp_systems": [{"id": "...", "last_backup_test_ns": ...}]}
# NOTE: the Bible emits "system_id": sys.system_id, but the gxp_systems
# table has no system_id column (its primary key is `id`) — under the
# Bible's own stated input shape that key is undefined, which makes the
# whole rule undefined and silently suppresses every violation. For a
# system-level finding the system itself is the record, so both keys
# resolve to sys.id. Recorded as a deviation in
# policies/BIBLE-DEVIATIONS.md.
violation contains {
    "rule_id": "ANNEX11-S16-BCK-001", "severity": "HIGH",
    "system_id": sys.id, "record_id": sys.id,
    "description": "Backup restore test older than 12 months"
} if {
    sys := input.gxp_systems[_]
    days_elapsed(sys.last_backup_test_ns) > 365
}

# 9. ANNEX11-S12-ACC-002: Orphaned privileged account
# Source: EU GMP Annex 11, Section 12 (Security)
# Input shape: {"access_records": [{"id": "...", "system_id": "...", "is_privileged": true, "user_status": "DEPARTED"}]}
violation contains {
    "rule_id": "ANNEX11-S12-ACC-002", "severity": "CRITICAL",
    "system_id": acc.system_id, "record_id": acc.id,
    "description": "Privileged account active but user marked departed"
} if {
    acc := input.access_records[_]
    acc.is_privileged == true
    acc.user_status == "DEPARTED"
}

# 10. ANNEX11-S10-CHG-001: Change record closed with unresolved actions
# Source: EU GMP Annex 11, Section 10 (Change and Configuration Management)
# Input shape: {"changes": [...], "change_actions": [{"change_id": "...", "status": "OPEN"}]}
violation contains {
    "rule_id": "ANNEX11-S10-CHG-001", "severity": "HIGH",
    "system_id": chg.system_id, "record_id": chg.id,
    "description": "Change closed but linked actions remain open"
} if {
    chg := input.changes[_]
    chg.status == "CLOSED"
    action := input.change_actions[_]
    action.change_id == chg.id
    action.status == "OPEN"
}
