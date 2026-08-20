-- infra/postgres/seed/001_seed.sql
--
-- SENT-1-02 / ENV-03: synthetic seed data for GxP Sentinel's two demo
-- systems. Source of truth: GxP-Sentinel-Project-Bible-v6.md Section 5
-- (lines 939-997). Every literal value below is byte-identical to the
-- Bible — string IDs, person names, nanosecond integers, and the NULL for
-- documents.effective_date are all load-bearing (Rego rules and the demo
-- script key off them exactly).
--
-- One mechanical deviation from the Bible's literal text, and only one:
-- every INSERT ends with a conflict-safe upsert-noop guard on the `id`
-- primary key. This changes no value and adds no row; it exists purely to
-- make this script safely re-runnable, because the seed is applied by an
-- explicitly-invoked script (infra/apply-seed.sh) rather than by
-- container init, and will be run repeatedly during development.
--
-- Deliberately NOT bind-mounted into the postgres container (unlike
-- infra/postgres/initdb/) — applying seed data is a deliberate operator
-- action, not part of environment bring-up, so a cold start yields a
-- clean, correctly-shaped, empty database. Apply via
-- `bash infra/apply-seed.sh`, which streams this file over stdin.
--
-- This is the entire seed script. Section 5 seeds only GXP-MFG-DEMO-01's
-- 10 gaps plus one healthy BUS-IT-DEMO-02 row. Every other table
-- (document_chunks, design_elements, test_results, supplier_assessments,
-- findings, evidence_refs, graph_nodes/graph_edges,
-- candidate_memory/trusted_memory, users, sessions, agent_messages,
-- action_proposals, audit_events) is intentionally left empty — no
-- additional rows are invented for them (CLAUDE.md Rule 7).

-- GXP-MFG-DEMO-01 (Unhealthy)
INSERT INTO gxp_systems (id, name, system_owner, lifecycle_state, gxp_impact, readiness_score, last_backup_test_ns)
VALUES ('GXP-MFG-DEMO-01', 'NovaSynth Manufacturing Execution Support System', 'Jens Larsen', 'OPERATIONAL', TRUE, 61, 1709251200000000000)
ON CONFLICT (id) DO NOTHING;

-- Gap 1: O&M Document DRAFT
INSERT INTO documents (id, system_id, doc_type, title, version, author, created_date, effective_date, status)
VALUES ('DOC-2026-OM-99', 'GXP-MFG-DEMO-01', 'O&M', 'NovaSynth Operations Manual', 'v1.0', 'Sarah Jensen', '2026-08-01 10:00:00', NULL, 'DRAFT')
ON CONFLICT (id) DO NOTHING;

-- Gap 2: Access Review 98 Days Overdue (Epoch ns for May 11, 2026)
INSERT INTO access_reviews (id, system_id, review_type, scheduled_date_ns, status, reviewer, accounts_in_scope)
VALUES ('AR-2026-05', 'GXP-MFG-DEMO-01', 'QUARTERLY_PRIVILEGED', 1715424000000000000, 'PENDING', 'Marcus Aurelius', 14)
ON CONFLICT (id) DO NOTHING;

-- Gap 3: Risk Assessment Expired (Last reviewed Aug 15, 2024)
INSERT INTO risks (id, system_id, risk_summary, severity, probability, last_review_date_ns, owner)
VALUES ('RSK-2024-11', 'GXP-MFG-DEMO-01', 'Data corruption during LIMS interface sync', 'HIGH', 'OCCASIONAL', 1723718400000000000, 'Data Integrity Office')
ON CONFLICT (id) DO NOTHING;

-- Gap 4: P1 Incident Open 47 Days, No RCA (Opened July 1, 2026)
INSERT INTO incidents (id, system_id, title, description, severity, status, opened_date_ns, rca_started, patient_safety_relevant)
VALUES ('INC-849201', 'GXP-MFG-DEMO-01', 'Batch release module timeout', 'Operators unable to sign electronic batch record', 'P1', 'OPEN', 1719830400000000000, FALSE, TRUE)
ON CONFLICT (id) DO NOTHING;

-- Gap 5: URS-042 No Test Evidence
INSERT INTO requirements (id, system_id, req_text, test_case_id)
VALUES ('URS-042', 'GXP-MFG-DEMO-01', 'System shall enforce complex passwords', 'TC-2026-042')
ON CONFLICT (id) DO NOTHING;

INSERT INTO test_cases (id, system_id, status)
VALUES ('TC-2026-042', 'GXP-MFG-DEMO-01', 'DRAFT')
ON CONFLICT (id) DO NOTHING;

-- Gap 6: Supplier reassessment 6 months overdue
INSERT INTO suppliers (id, system_id, name, reassessment_due_date_ns, status)
VALUES ('SUP-2026-01', 'GXP-MFG-DEMO-01', 'DataSync Solutions', 1708214400000000000, 'APPROVED')
ON CONFLICT (id) DO NOTHING;

-- Gap 7: Periodic evaluation overdue 24 months
INSERT INTO periodic_evaluations (id, system_id, due_date_ns, status)
VALUES ('PE-2024-01', 'GXP-MFG-DEMO-01', 1704067200000000000, 'PENDING')
ON CONFLICT (id) DO NOTHING;

-- Gap 8: Backup restore test stale (triggered by gxp_systems.last_backup_test_ns
-- above — no separate INSERT)

-- Gap 9: Orphaned privileged account (Employee departed 90 days ago)
INSERT INTO access_records (id, system_id, user_id, is_privileged, user_status)
VALUES ('ACC-2026-99', 'GXP-MFG-DEMO-01', 'U-9942', TRUE, 'DEPARTED')
ON CONFLICT (id) DO NOTHING;

-- Gap 10: Change record closed with unresolved actions
INSERT INTO changes (id, system_id, description, status, qa_approval_date)
VALUES ('CR-2026-089', 'GXP-MFG-DEMO-01', 'Database migration', 'CLOSED', '2026-08-01 12:00:00')
ON CONFLICT (id) DO NOTHING;

INSERT INTO change_actions (id, change_id, description, status)
VALUES ('CA-2026-089-1', 'CR-2026-089', 'Update SOPs post-migration', 'OPEN')
ON CONFLICT (id) DO NOTHING;

-- BUS-IT-DEMO-02 (Healthy)
INSERT INTO gxp_systems (id, name, system_owner, lifecycle_state, gxp_impact, readiness_score, last_backup_test_ns)
VALUES ('BUS-IT-DEMO-02', 'Argonaut Business Analytics Platform', 'Elena Rostova', 'OPERATIONAL', FALSE, 94, 1722470400000000000)
ON CONFLICT (id) DO NOTHING;
