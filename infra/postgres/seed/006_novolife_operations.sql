-- infra/postgres/seed/006_novolife_operations.sql
--
-- Quick task 260908-qtm, part 3 of 4. Additive demo data for
-- GXP-MES-NOVOLIFE-01; see 004_novolife_system.sql's header for why these
-- files exist and the provenance discipline they follow. Applied after 004
-- and 005 by infra/apply-seed.sh's sorted filename order.
--
-- This file seeds the operational/maintained-state layer: 26 `risks`, 15
-- `incidents`, one `change` with 12 `change_actions`, one `supplier` with
-- its `supplier_assessment`, one `access_review` with 30 `access_records`,
-- one `periodic_evaluation`, and 28 `change_affects` junction rows.
--
-- INSERT order inside this file is foreign-key-safe: `suppliers` before
-- `supplier_assessments` (which references it), `changes` before
-- `change_actions` and before `change_affects` (both reference it).
--
-- Every column supplied is declared by infra/postgres/initdb/001_schema.sql,
-- except `change_affects`, whose three columns come from the additive
-- migration infra/postgres/initdb/002_change_affects.sql. No column outside
-- those two files is referenced (CLAUDE.md Rule 7).
--
-- Every INSERT ends with a conflict-safe upsert-noop guard. The
-- `change_affects` inserts use `ON CONFLICT (change_id, entity_type,
-- entity_id) DO NOTHING` against that table's composite primary key, the
-- same pattern 003_change_affects_fixture.sql already established.
--
-- Routed to SENT-7-05 for AegisX-AI-Project-Bible-v6.md reconciliation.

-- ---------------------------------------------------------------------------
-- risks -- the 26-entry shared risk register
-- ---------------------------------------------------------------------------
--
-- RSK-MES-001 through -026 from NL-MES-ITRA-001's register
-- (NL-MES-TRM-001's gate check: "Exactly 26 risk IDs | Pass | RSK-MES-001
-- through -026; all Open").
--
-- `risk_summary` is the register's own "Domain -- Scenario title" pair.
-- `severity` is the register's "Working gross" column mapped to the
-- schema's vocabulary (Working High -> HIGH, Working Medium -> MEDIUM);
-- RSK-MES-026's "Working High if applicable" is seeded HIGH with its
-- applicability caveat kept in the summary text, because the register also
-- records its status as "Open / applicability Verify".
-- `probability` is the per-risk "Likelihood:" value from that risk's own
-- working gross assessment paragraph (Possible / Unlikely). `owner` is the
-- risk's own "Control owner." line.
--
-- `last_review_date_ns` = 2026-08-10T00:00:00Z for all 26, from
-- NL-MES-ITRA-001's single "Assessment date | 10 Aug 2026" -- the register
-- has been assessed once and never re-reviewed. Rego rule 3
-- (ICH-Q9-RSK-001) fires past 365 days, so this correctly produces no
-- review-staleness violation: what is open on these risks is treatment and
-- residual acceptance ("Residual risk: Not rated - controls not yet
-- implemented or verified"), not the review itself. Seeding a stale date to
-- manufacture a violation would misreport the package.

INSERT INTO risks (id, system_id, risk_summary, severity, probability, last_review_date_ns, owner)
VALUES ('RSK-MES-001', 'GXP-MES-NOVOLIFE-01',
    'Manufacturing / product: Unapproved order, recipe, or execution state (working gross Working High; status Open per NL-MES-ITRA-001)',
    'HIGH', 'POSSIBLE', 1786320000000000000, 'Fictional Business Process Owner')
ON CONFLICT (id) DO NOTHING;
INSERT INTO risks (id, system_id, risk_summary, severity, probability, last_review_date_ns, owner)
VALUES ('RSK-MES-002', 'GXP-MES-NOVOLIFE-01',
    'Manufacturing / data: Incorrect or incomplete execution data and calculations (working gross Working High; status Open per NL-MES-ITRA-001)',
    'HIGH', 'POSSIBLE', 1786320000000000000, 'Fictional MES Functional SME')
ON CONFLICT (id) DO NOTHING;
INSERT INTO risks (id, system_id, risk_summary, severity, probability, last_review_date_ns, owner)
VALUES ('RSK-MES-003', 'GXP-MES-NOVOLIFE-01',
    'Manufacturing / quality: Incomplete batch completion, exception disposition, or review (working gross Working High; status Open per NL-MES-ITRA-001)',
    'HIGH', 'POSSIBLE', 1786320000000000000, 'Fictional Quality Assurance')
ON CONFLICT (id) DO NOTHING;
INSERT INTO risks (id, system_id, risk_summary, severity, probability, last_review_date_ns, owner)
VALUES ('RSK-MES-004', 'GXP-MES-NOVOLIFE-01',
    'Records / retention: Loss, unreadability, or incomplete copy of regulated records (working gross Working High; status Open per NL-MES-ITRA-001)',
    'HIGH', 'POSSIBLE', 1786320000000000000, 'Fictional Data Owner')
ON CONFLICT (id) DO NOTHING;
INSERT INTO risks (id, system_id, risk_summary, severity, probability, last_review_date_ns, owner)
VALUES ('RSK-MES-005', 'GXP-MES-NOVOLIFE-01',
    'Security / access: Unauthorised or excessive access (working gross Working High; status Open per NL-MES-ITRA-001)',
    'HIGH', 'POSSIBLE', 1786320000000000000, 'Fictional IT Solution Owner')
ON CONFLICT (id) DO NOTHING;
INSERT INTO risks (id, system_id, risk_summary, severity, probability, last_review_date_ns, owner)
VALUES ('RSK-MES-006', 'GXP-MES-NOVOLIFE-01',
    'Security / identity: Credential, session, or service-account compromise (working gross Working High; status Open per NL-MES-ITRA-001)',
    'HIGH', 'POSSIBLE', 1786320000000000000, 'Fictional Data Integrity / Security SME')
ON CONFLICT (id) DO NOTHING;
INSERT INTO risks (id, system_id, risk_summary, severity, probability, last_review_date_ns, owner)
VALUES ('RSK-MES-007', 'GXP-MES-NOVOLIFE-01',
    'GxP evidence / signature: Invalid or non-attributable electronic signature (working gross Working High; status Open per NL-MES-ITRA-001)',
    'HIGH', 'POSSIBLE', 1786320000000000000, 'Fictional Business Process Owner')
ON CONFLICT (id) DO NOTHING;
INSERT INTO risks (id, system_id, risk_summary, severity, probability, last_review_date_ns, owner)
VALUES ('RSK-MES-008', 'GXP-MES-NOVOLIFE-01',
    'GxP evidence / audit trail: Incomplete, alterable, or ineffective audit trail (working gross Working High; status Open per NL-MES-ITRA-001)',
    'HIGH', 'POSSIBLE', 1786320000000000000, 'Fictional Data Integrity / Security SME')
ON CONFLICT (id) DO NOTHING;
INSERT INTO risks (id, system_id, risk_summary, severity, probability, last_review_date_ns, owner)
VALUES ('RSK-MES-009', 'GXP-MES-NOVOLIFE-01',
    'Data integrity / time: Inconsistent time and chronology (working gross Working Medium; status Open per NL-MES-ITRA-001)',
    'MEDIUM', 'UNLIKELY', 1786320000000000000, 'Fictional Technical / Integration Lead')
ON CONFLICT (id) DO NOTHING;
INSERT INTO risks (id, system_id, risk_summary, severity, probability, last_review_date_ns, owner)
VALUES ('RSK-MES-010', 'GXP-MES-NOVOLIFE-01',
    'Data integrity: Uncontrolled correction, deletion, or record lifecycle (working gross Working High; status Open per NL-MES-ITRA-001)',
    'HIGH', 'POSSIBLE', 1786320000000000000, 'Fictional Data Owner')
ON CONFLICT (id) DO NOTHING;
INSERT INTO risks (id, system_id, risk_summary, severity, probability, last_review_date_ns, owner)
VALUES ('RSK-MES-011', 'GXP-MES-NOVOLIFE-01',
    'Integration / ERP: ERP order/master-data or confirmation interface failure (working gross Working High; status Open per NL-MES-ITRA-001)',
    'HIGH', 'POSSIBLE', 1786320000000000000, 'Fictional Technical / Integration Lead')
ON CONFLICT (id) DO NOTHING;
INSERT INTO risks (id, system_id, risk_summary, severity, probability, last_review_date_ns, owner)
VALUES ('RSK-MES-012', 'GXP-MES-NOVOLIFE-01',
    'Integration / LIMS: LIMS sample, result, or disposition interface failure (working gross Working High; status Open per NL-MES-ITRA-001)',
    'HIGH', 'POSSIBLE', 1786320000000000000, 'Fictional Technical / Integration Lead')
ON CONFLICT (id) DO NOTHING;
INSERT INTO risks (id, system_id, risk_summary, severity, probability, last_review_date_ns, owner)
VALUES ('RSK-MES-013', 'GXP-MES-NOVOLIFE-01',
    'Integration / automation: Automation command, state, or measurement mismatch (working gross Working High; status Open per NL-MES-ITRA-001)',
    'HIGH', 'POSSIBLE', 1786320000000000000, 'Fictional Technical / Integration Lead')
ON CONFLICT (id) DO NOTHING;
INSERT INTO risks (id, system_id, risk_summary, severity, probability, last_review_date_ns, owner)
VALUES ('RSK-MES-014', 'GXP-MES-NOVOLIFE-01',
    'Integration / reporting: Historian/reporting publication is incomplete or misleading (working gross Working High; status Open per NL-MES-ITRA-001)',
    'HIGH', 'POSSIBLE', 1786320000000000000, 'Fictional Data Owner')
ON CONFLICT (id) DO NOTHING;
INSERT INTO risks (id, system_id, risk_summary, severity, probability, last_review_date_ns, owner)
VALUES ('RSK-MES-015', 'GXP-MES-NOVOLIFE-01',
    'Integration / common control: Cross-interface integrity, monitoring, or reconciliation failure (working gross Working High; status Open per NL-MES-ITRA-001)',
    'HIGH', 'POSSIBLE', 1786320000000000000, 'Fictional Technical / Integration Lead')
ON CONFLICT (id) DO NOTHING;
INSERT INTO risks (id, system_id, risk_summary, severity, probability, last_review_date_ns, owner)
VALUES ('RSK-MES-016', 'GXP-MES-NOVOLIFE-01',
    'Continuity / availability: Application or infrastructure unavailability and capacity exhaustion (working gross Working High; status Open per NL-MES-ITRA-001)',
    'HIGH', 'POSSIBLE', 1786320000000000000, 'Fictional IT Solution Owner')
ON CONFLICT (id) DO NOTHING;
INSERT INTO risks (id, system_id, risk_summary, severity, probability, last_review_date_ns, owner)
VALUES ('RSK-MES-017', 'GXP-MES-NOVOLIFE-01',
    'Continuity / backup: Backup is incomplete, corrupt, unavailable, or outside need (working gross Working High; status Open per NL-MES-ITRA-001)',
    'HIGH', 'POSSIBLE', 1786320000000000000, 'Fictional Technical / Integration Lead')
ON CONFLICT (id) DO NOTHING;
INSERT INTO risks (id, system_id, risk_summary, severity, probability, last_review_date_ns, owner)
VALUES ('RSK-MES-018', 'GXP-MES-NOVOLIFE-01',
    'Continuity / recovery: Recovery fails objectives or creates inconsistent state (working gross Working High; status Open per NL-MES-ITRA-001)',
    'HIGH', 'POSSIBLE', 1786320000000000000, 'Fictional IT Solution Owner')
ON CONFLICT (id) DO NOTHING;
INSERT INTO risks (id, system_id, risk_summary, severity, probability, last_review_date_ns, owner)
VALUES ('RSK-MES-019', 'GXP-MES-NOVOLIFE-01',
    'Security / technology: Cyber vulnerability, malware, or insecure component (working gross Working High; status Open per NL-MES-ITRA-001)',
    'HIGH', 'POSSIBLE', 1786320000000000000, 'Fictional Data Integrity / Security SME')
ON CONFLICT (id) DO NOTHING;
INSERT INTO risks (id, system_id, risk_summary, severity, probability, last_review_date_ns, owner)
VALUES ('RSK-MES-020', 'GXP-MES-NOVOLIFE-01',
    'Supplier / service: Supplier or shared-service controls are unclear or ineffective (working gross Working High; status Open per NL-MES-ITRA-001)',
    'HIGH', 'POSSIBLE', 1786320000000000000, 'Fictional IT Solution Owner')
ON CONFLICT (id) DO NOTHING;
INSERT INTO risks (id, system_id, risk_summary, severity, probability, last_review_date_ns, owner)
VALUES ('RSK-MES-021', 'GXP-MES-NOVOLIFE-01',
    'Lifecycle / change: Uncontrolled change, configuration, or promotion (working gross Working High; status Open per NL-MES-ITRA-001)',
    'HIGH', 'POSSIBLE', 1786320000000000000, 'Fictional IT Solution Owner')
ON CONFLICT (id) DO NOTHING;
INSERT INTO risks (id, system_id, risk_summary, severity, probability, last_review_date_ns, owner)
VALUES ('RSK-MES-022', 'GXP-MES-NOVOLIFE-01',
    'Lifecycle / incident: Incident or problem handling fails to protect GxP state (working gross Working High; status Open per NL-MES-ITRA-001)',
    'HIGH', 'POSSIBLE', 1786320000000000000, 'Fictional IT Solution Owner')
ON CONFLICT (id) DO NOTHING;
INSERT INTO risks (id, system_id, risk_summary, severity, probability, last_review_date_ns, owner)
VALUES ('RSK-MES-023', 'GXP-MES-NOVOLIFE-01',
    'Reporting / evidence: Controlled report or extract is misinterpreted or altered (working gross Working Medium; status Open per NL-MES-ITRA-001)',
    'MEDIUM', 'UNLIKELY', 1786320000000000000, 'Fictional Business Process Owner')
ON CONFLICT (id) DO NOTHING;
INSERT INTO risks (id, system_id, risk_summary, severity, probability, last_review_date_ns, owner)
VALUES ('RSK-MES-024', 'GXP-MES-NOVOLIFE-01',
    'Lifecycle / maintained state: Maintained-state controls, review, or training become ineffective (working gross Working Medium; status Open per NL-MES-ITRA-001)',
    'MEDIUM', 'UNLIKELY', 1786320000000000000, 'Fictional IT Solution Owner')
ON CONFLICT (id) DO NOTHING;
INSERT INTO risks (id, system_id, risk_summary, severity, probability, last_review_date_ns, owner)
VALUES ('RSK-MES-025', 'GXP-MES-NOVOLIFE-01',
    'Privacy / personal data: Personal data processing is excessive or insufficiently protected (working gross Working Medium; status Open per NL-MES-ITRA-001)',
    'MEDIUM', 'POSSIBLE', 1786320000000000000, 'Fictional Business Activity Owner')
ON CONFLICT (id) DO NOTHING;
INSERT INTO risks (id, system_id, risk_summary, severity, probability, last_review_date_ns, owner)
VALUES ('RSK-MES-026', 'GXP-MES-NOVOLIFE-01',
    'Data integrity / migration: Initial load or migration loses content and meaning (working gross Working High if applicable; status Open per NL-MES-ITRA-001)',
    'HIGH', 'POSSIBLE', 1786320000000000000, 'Fictional Data Owner')
ON CONFLICT (id) DO NOTHING;

-- ---------------------------------------------------------------------------
-- incidents -- one service incident plus the 14 IQ exception records
-- ---------------------------------------------------------------------------
--
-- The 6 DUMMY-DEV-MES-00# validation deviations (NL-MES-DEVL-001) and 8
-- DUMMY-DEF-MES-00# defects (NL-MES-DEFL-001) have no dedicated table in
-- infra/postgres/initdb/001_schema.sql, so they are mapped onto `incidents`
-- rather than given one -- adding a table is schema scope this task does
-- not have (CLAUDE.md Rule 7), and dropping them would lose the entire IQ
-- exception lifecycle. `severity` therefore carries each record's own
-- Major/Minor grading rather than the P1..P4 vocabulary
-- 001_seed.sql's INC-849201 uses; the two vocabularies coexist in the
-- column because the two source documents genuinely grade on different
-- scales. `title` names the exception class explicitly so a reader of the
-- row is never misled into thinking a validation deviation was a service
-- outage.
--
-- `rca_started` is TRUE for all 14: NL-MES-DEVL-001 carries a
-- "Investigation, validity, solution and closure" section per deviation and
-- NL-MES-DEFL-001 records "Investigation: Final Approved (simulated)" per
-- defect. `status` is CLOSED for all 14 -- both logs reconcile to
-- "Open / cancelled / superseded | 0 / 0 / 0".
--
-- `patient_safety_relevant` is FALSE throughout. These are installation
-- qualification findings in an isolated non-production enclave; the package
-- states repeatedly that "No products, materials, batches, dossier content,
-- authority documentation or actual production exist."
--
-- `opened_date_ns` is each record's own "Observed:" (deviations) or
-- "Detected on" (defects) date.
--
-- Rego rule 4 (ANNEX11-S13-INC-001) needs severity 'P1' AND status 'OPEN';
-- nothing here matches, which is correct -- every one of these was closed
-- with approved evidence.

-- NL-MES-INC-001's single service incident. "Priority | Medium (P3) -
-- simulated"; "Incident status | Closed"; "Detection timestamp | 12 Aug
-- 2026 09:00 fictional package time". `rca_started` TRUE per DEC-INC-008
-- ("cause/correction verified") even though DEC-INC-008 also records that
-- no separate DUMMY-PRB problem record was required for a P3.
INSERT INTO incidents (id, system_id, title, description, severity, status, opened_date_ns, rca_started, patient_safety_relevant)
VALUES ('DUMMY-INC-MES-001', 'GXP-MES-NOVOLIFE-01',
    'ERP-reconciliation support view is stale while authoritative inbound processing remains healthy',
    'A synthetic projection worker stopped, so the ERP-reconciliation support view stopped refreshing. Inbound receipt, validation, idempotency and the authoritative transaction ledger were unaffected; support used the approved authoritative-ledger view as workaround and the approved runbook restart rebuilt the derived view.',
    'P3', 'CLOSED', 1786525200000000000, TRUE, FALSE)
ON CONFLICT (id) DO NOTHING;
INSERT INTO incidents (id, system_id, title, description, severity, status, opened_date_ns, rca_started, patient_safety_relevant)
VALUES ('DUMMY-DEF-MES-001', 'GXP-MES-NOVOLIFE-01',
    'IQ defect: Prohibited platform service remained active',
    'Graded Major. Origin: DUMMY-TC-MES-IQ-005 Step 4 DUMMY-RUN-MES-IQ-005. Corrected, retested and closed with approved evidence during the 03-10 Aug 2026 simulated IQ execution window.',
    'MAJOR', 'CLOSED', 1785715200000000000, TRUE, FALSE)
ON CONFLICT (id) DO NOTHING;
INSERT INTO incidents (id, system_id, title, description, severity, status, opened_date_ns, rca_started, patient_safety_relevant)
VALUES ('DUMMY-DEF-MES-002', 'GXP-MES-NOVOLIFE-01',
    'IQ defect: Database role contained excessive administrative grant',
    'Graded Major. Origin: DUMMY-TC-MES-IQ-006 Step 4 DUMMY-RUN-MES-IQ-006. Corrected, retested and closed with approved evidence during the 03-10 Aug 2026 simulated IQ execution window.',
    'MAJOR', 'CLOSED', 1785715200000000000, TRUE, FALSE)
ON CONFLICT (id) DO NOTHING;
INSERT INTO incidents (id, system_id, title, description, severity, status, opened_date_ns, rca_started, patient_safety_relevant)
VALUES ('DUMMY-DEF-MES-003', 'GXP-MES-NOVOLIFE-01',
    'IQ defect: Certificate renewal alert selector omitted one item',
    'Graded Minor (Non-Obvious). Origin: DUMMY-TC-MES-IQ-010 Step 6 DUMMY-RUN-MES-IQ-010. Corrected, retested and closed with approved evidence during the 03-10 Aug 2026 simulated IQ execution window.',
    'MINOR', 'CLOSED', 1785801600000000000, TRUE, FALSE)
ON CONFLICT (id) DO NOTHING;
INSERT INTO incidents (id, system_id, title, description, severity, status, opened_date_ns, rca_started, patient_safety_relevant)
VALUES ('DUMMY-DEF-MES-004', 'GXP-MES-NOVOLIFE-01',
    'IQ defect: Service identity permitted interactive sign-in',
    'Graded Major. Origin: DUMMY-TC-MES-IQ-011 Step 3 DUMMY-RUN-MES-IQ-011. Corrected, retested and closed with approved evidence during the 03-10 Aug 2026 simulated IQ execution window.',
    'MAJOR', 'CLOSED', 1785801600000000000, TRUE, FALSE)
ON CONFLICT (id) DO NOTHING;
INSERT INTO incidents (id, system_id, title, description, severity, status, opened_date_ns, rca_started, patient_safety_relevant)
VALUES ('DUMMY-DEF-MES-005', 'GXP-MES-NOVOLIFE-01',
    'IQ defect: Time-source failure alert did not reach support queue',
    'Graded Major. Origin: DUMMY-TC-MES-IQ-013 Step 5 DUMMY-RUN-MES-IQ-013. Corrected, retested and closed with approved evidence during the 03-10 Aug 2026 simulated IQ execution window.',
    'MAJOR', 'CLOSED', 1785888000000000000, TRUE, FALSE)
ON CONFLICT (id) DO NOTHING;
INSERT INTO incidents (id, system_id, title, description, severity, status, opened_date_ns, rca_started, patient_safety_relevant)
VALUES ('DUMMY-DEF-MES-006', 'GXP-MES-NOVOLIFE-01',
    'IQ defect: ERP quarantine alert lacked escalation owner',
    'Graded Minor (Non-Obvious). Origin: DUMMY-TC-MES-IQ-016 Step 6 DUMMY-RUN-MES-IQ-016. Corrected, retested and closed with approved evidence during the 03-10 Aug 2026 simulated IQ execution window.',
    'MINOR', 'CLOSED', 1785888000000000000, TRUE, FALSE)
ON CONFLICT (id) DO NOTHING;
INSERT INTO incidents (id, system_id, title, description, severity, status, opened_date_ns, rca_started, patient_safety_relevant)
VALUES ('DUMMY-DEF-MES-007', 'GXP-MES-NOVOLIFE-01',
    'IQ defect: Protected log retention shorter than approved baseline',
    'Graded Major. Origin: DUMMY-TC-MES-IQ-020 Step 3 DUMMY-RUN-MES-IQ-020. Corrected, retested and closed with approved evidence during the 03-10 Aug 2026 simulated IQ execution window.',
    'MAJOR', 'CLOSED', 1785974400000000000, TRUE, FALSE)
ON CONFLICT (id) DO NOTHING;
INSERT INTO incidents (id, system_id, title, description, severity, status, opened_date_ns, rca_started, patient_safety_relevant)
VALUES ('DUMMY-DEF-MES-008', 'GXP-MES-NOVOLIFE-01',
    'IQ defect: Unapproved listening port present in hardened baseline',
    'Graded Major. Origin: DUMMY-TC-MES-IQ-027 Step 4 DUMMY-RUN-MES-IQ-027. Corrected, retested and closed with approved evidence during the 03-10 Aug 2026 simulated IQ execution window.',
    'MAJOR', 'CLOSED', 1785974400000000000, TRUE, FALSE)
ON CONFLICT (id) DO NOTHING;
INSERT INTO incidents (id, system_id, title, description, severity, status, opened_date_ns, rca_started, patient_safety_relevant)
VALUES ('DUMMY-DEV-MES-001', 'GXP-MES-NOVOLIFE-01',
    'IQ validation deviation: Independent media checksum did not match the approved manifest',
    'Graded Major. Origin: DUMMY-TC-MES-IQ-002 Step 3 DUMMY-RUN-MES-IQ-002-DEV. Corrected, retested and closed with approved evidence during the 03-10 Aug 2026 simulated IQ execution window.',
    'MAJOR', 'CLOSED', 1785715200000000000, TRUE, FALSE)
ON CONFLICT (id) DO NOTHING;
INSERT INTO incidents (id, system_id, title, description, severity, status, opened_date_ns, rca_started, patient_safety_relevant)
VALUES ('DUMMY-DEV-MES-002', 'GXP-MES-NOVOLIFE-01',
    'IQ validation deviation: Restore target was not fully isolated from shared non-production network',
    'Graded Major. Origin: DUMMY-TC-MES-IQ-022 Step 4 DUMMY-RUN-MES-IQ-022-DEV. Corrected, retested and closed with approved evidence during the 03-10 Aug 2026 simulated IQ execution window.',
    'MAJOR', 'CLOSED', 1785715200000000000, TRUE, FALSE)
ON CONFLICT (id) DO NOTHING;
INSERT INTO incidents (id, system_id, title, description, severity, status, opened_date_ns, rca_started, patient_safety_relevant)
VALUES ('DUMMY-DEV-MES-003', 'GXP-MES-NOVOLIFE-01',
    'IQ validation deviation: Support-document review metadata was not synchronized',
    'Graded Minor (Non-Obvious). Origin: DUMMY-TC-MES-IQ-028 Step 3 DUMMY-RUN-MES-IQ-028-DEV. Corrected, retested and closed with approved evidence during the 03-10 Aug 2026 simulated IQ execution window.',
    'MINOR', 'CLOSED', 1785801600000000000, TRUE, FALSE)
ON CONFLICT (id) DO NOTHING;
INSERT INTO incidents (id, system_id, title, description, severity, status, opened_date_ns, rca_started, patient_safety_relevant)
VALUES ('DUMMY-DEV-MES-004', 'GXP-MES-NOVOLIFE-01',
    'IQ validation deviation: Cleanup rule omitted one temporary evidence-staging file',
    'Graded Minor (Non-Obvious). Origin: DUMMY-TC-MES-IQ-029 Step 6 DUMMY-RUN-MES-IQ-029-DEV. Corrected, retested and closed with approved evidence during the 03-10 Aug 2026 simulated IQ execution window.',
    'MINOR', 'CLOSED', 1785801600000000000, TRUE, FALSE)
ON CONFLICT (id) DO NOTHING;
INSERT INTO incidents (id, system_id, title, description, severity, status, opened_date_ns, rca_started, patient_safety_relevant)
VALUES ('DUMMY-DEV-MES-005', 'GXP-MES-NOVOLIFE-01',
    'IQ validation deviation: DUMMY printer output lacked the required training banner',
    'Graded Minor (Obvious). Origin: DUMMY-TC-MES-IQ-025 Step 6 DUMMY-RUN-MES-IQ-025-DEV. Corrected, retested and closed with approved evidence during the 03-10 Aug 2026 simulated IQ execution window.',
    'MINOR', 'CLOSED', 1785888000000000000, TRUE, FALSE)
ON CONFLICT (id) DO NOTHING;
INSERT INTO incidents (id, system_id, title, description, severity, status, opened_date_ns, rca_started, patient_safety_relevant)
VALUES ('DUMMY-DEV-MES-006', 'GXP-MES-NOVOLIFE-01',
    'IQ validation deviation: Candidate baseline export was indexed in the wrong controlled subfolder',
    'Graded Minor (Obvious). Origin: DUMMY-TC-MES-IQ-030 Step 6 DUMMY-RUN-MES-IQ-030-DEV. Corrected, retested and closed with approved evidence during the 03-10 Aug 2026 simulated IQ execution window.',
    'MINOR', 'CLOSED', 1785888000000000000, TRUE, FALSE)
ON CONFLICT (id) DO NOTHING;

-- ---------------------------------------------------------------------------
-- access_reviews / access_records -- NL-MES-AMRR-001
-- ---------------------------------------------------------------------------
--
-- `review_type` is a 50-character column and the report's own review-type
-- sentence does not fit: "DUMMY annual production plus risk-based quarterly
-- privileged/broad/local/platform/database/service and annual
-- non-production review". The token below names the same cadence pair the
-- report's own frequency table sets out ("All production access | At least
-- annually"; "Privileged, broad, local/default, platform/database, and
-- machine/service access | Quarterly").
--
-- `status` is 'COMPLETE', not 'PENDING': the report states "Review
-- conclusion | Report complete; access control Not in control - six
-- synthetic rejected assignments and remediation Open" and "Counts | 30
-- expected; 30 retrieved; 30 reviewed". The review happened. What is open
-- is the remediation of its six Reject decisions, which lives in the
-- `access_records` rows below, not in the review's own status. Rego rule 2
-- (ANNEX11-S12-ACC-001) keys off status 'PENDING' plus an overdue schedule,
-- so it correctly stays silent -- reporting an overdue review here would be
-- a false finding on top of a real one.

INSERT INTO access_reviews (id, system_id, review_type, scheduled_date_ns, status, reviewer, accounts_in_scope)
VALUES ('DUMMY-AMRR-MES-001', 'GXP-MES-NOVOLIFE-01', 'ANNUAL_PLUS_QUARTERLY_PRIVILEGED', 1786492800000000000, 'COMPLETE', 'Fictional IT Solution Manager', 30)
ON CONFLICT (id) DO NOTHING;

-- The 30 reviewed assignments, verbatim from the report's population table
-- (24 Retain, 6 Reject).
--
-- `is_privileged` is TRUE only where the report's own "Account type" column
-- reads "Privileged human" (5 rows). Machine/service, orphan/local and
-- default/local accounts are separately typed there and are NOT marked
-- privileged here, even though the report's frequency table puts them on
-- the same quarterly cadence -- the schema column names privilege, and
-- widening it to "higher-risk account" would be an interpretation the
-- source does not make.
--
-- `user_status` carries each row's own "Current state" value. Note what
-- this does NOT produce: Rego rule 9 (ANNEX11-S12-ACC-002) fires on
-- is_privileged AND user_status = 'DEPARTED', and nobody in this population
-- is recorded as departed. The closest rows are ACC-AMR-016
-- (privileged, "Authorization withdrawn") and ACC-AMR-007 (not privileged,
-- "Role ended"). Mapping either onto 'DEPARTED' to make the rule fire would
-- be fabricating a finding, so neither is mapped.

INSERT INTO access_records (id, system_id, user_id, is_privileged, user_status)
VALUES ('ACC-AMR-001', 'GXP-MES-NOVOLIFE-01', 'DUMMY-USER-001', FALSE, 'APPROVED_CURRENT')
ON CONFLICT (id) DO NOTHING;
INSERT INTO access_records (id, system_id, user_id, is_privileged, user_status)
VALUES ('ACC-AMR-002', 'GXP-MES-NOVOLIFE-01', 'DUMMY-USER-002', FALSE, 'APPROVED_CURRENT')
ON CONFLICT (id) DO NOTHING;
INSERT INTO access_records (id, system_id, user_id, is_privileged, user_status)
VALUES ('ACC-AMR-003', 'GXP-MES-NOVOLIFE-01', 'DUMMY-USER-003', FALSE, 'APPROVED_CURRENT')
ON CONFLICT (id) DO NOTHING;
INSERT INTO access_records (id, system_id, user_id, is_privileged, user_status)
VALUES ('ACC-AMR-004', 'GXP-MES-NOVOLIFE-01', 'DUMMY-USER-004', FALSE, 'APPROVED_CURRENT')
ON CONFLICT (id) DO NOTHING;
INSERT INTO access_records (id, system_id, user_id, is_privileged, user_status)
VALUES ('ACC-AMR-005', 'GXP-MES-NOVOLIFE-01', 'DUMMY-USER-005', FALSE, 'APPROVED_CURRENT')
ON CONFLICT (id) DO NOTHING;
INSERT INTO access_records (id, system_id, user_id, is_privileged, user_status)
VALUES ('ACC-AMR-006', 'GXP-MES-NOVOLIFE-01', 'DUMMY-USER-006', FALSE, 'APPROVED_CURRENT')
ON CONFLICT (id) DO NOTHING;
INSERT INTO access_records (id, system_id, user_id, is_privileged, user_status)
VALUES ('ACC-AMR-007', 'GXP-MES-NOVOLIFE-01', 'DUMMY-USER-007', FALSE, 'ROLE_ENDED')
ON CONFLICT (id) DO NOTHING;
INSERT INTO access_records (id, system_id, user_id, is_privileged, user_status)
VALUES ('ACC-AMR-008', 'GXP-MES-NOVOLIFE-01', 'DUMMY-USER-008', FALSE, 'APPROVED_CURRENT')
ON CONFLICT (id) DO NOTHING;
INSERT INTO access_records (id, system_id, user_id, is_privileged, user_status)
VALUES ('ACC-AMR-009', 'GXP-MES-NOVOLIFE-01', 'DUMMY-USER-009', FALSE, 'COMBINATION_PROHIBITED')
ON CONFLICT (id) DO NOTHING;
INSERT INTO access_records (id, system_id, user_id, is_privileged, user_status)
VALUES ('ACC-AMR-010', 'GXP-MES-NOVOLIFE-01', 'DUMMY-LOCAL-001', FALSE, 'NO_OWNER_APPROVAL')
ON CONFLICT (id) DO NOTHING;
INSERT INTO access_records (id, system_id, user_id, is_privileged, user_status)
VALUES ('ACC-AMR-011', 'GXP-MES-NOVOLIFE-01', 'DUMMY-DEFAULT-001', FALSE, 'UNNECESSARY_DEFAULT')
ON CONFLICT (id) DO NOTHING;
INSERT INTO access_records (id, system_id, user_id, is_privileged, user_status)
VALUES ('ACC-AMR-012', 'GXP-MES-NOVOLIFE-01', 'DUMMY-CW-001', FALSE, 'TIME_BOUND_CURRENT')
ON CONFLICT (id) DO NOTHING;
INSERT INTO access_records (id, system_id, user_id, is_privileged, user_status)
VALUES ('ACC-AMR-013', 'GXP-MES-NOVOLIFE-01', 'DUMMY-CW-002', FALSE, 'TIME_BOUND_EXPIRED')
ON CONFLICT (id) DO NOTHING;
INSERT INTO access_records (id, system_id, user_id, is_privileged, user_status)
VALUES ('ACC-AMR-014', 'GXP-MES-NOVOLIFE-01', 'DUMMY-ADMIN-001', TRUE, 'APPROVED_TIME_BOUND')
ON CONFLICT (id) DO NOTHING;
INSERT INTO access_records (id, system_id, user_id, is_privileged, user_status)
VALUES ('ACC-AMR-015', 'GXP-MES-NOVOLIFE-01', 'DUMMY-DBA-001', TRUE, 'APPROVED_TIME_BOUND')
ON CONFLICT (id) DO NOTHING;
INSERT INTO access_records (id, system_id, user_id, is_privileged, user_status)
VALUES ('ACC-AMR-016', 'GXP-MES-NOVOLIFE-01', 'DUMMY-DBA-002', TRUE, 'AUTHORIZATION_WITHDRAWN')
ON CONFLICT (id) DO NOTHING;
INSERT INTO access_records (id, system_id, user_id, is_privileged, user_status)
VALUES ('ACC-AMR-017', 'GXP-MES-NOVOLIFE-01', 'DUMMY-ADMIN-002', TRUE, 'APPROVED_TIME_BOUND')
ON CONFLICT (id) DO NOTHING;
INSERT INTO access_records (id, system_id, user_id, is_privileged, user_status)
VALUES ('ACC-AMR-018', 'GXP-MES-NOVOLIFE-01', 'DUMMY-SVC-ERP-001', FALSE, 'OWNER_CURRENT')
ON CONFLICT (id) DO NOTHING;
INSERT INTO access_records (id, system_id, user_id, is_privileged, user_status)
VALUES ('ACC-AMR-019', 'GXP-MES-NOVOLIFE-01', 'DUMMY-SVC-LIMS-001', FALSE, 'OWNER_CURRENT')
ON CONFLICT (id) DO NOTHING;
INSERT INTO access_records (id, system_id, user_id, is_privileged, user_status)
VALUES ('ACC-AMR-020', 'GXP-MES-NOVOLIFE-01', 'DUMMY-SVC-REPORT-001', FALSE, 'OWNER_CURRENT')
ON CONFLICT (id) DO NOTHING;
INSERT INTO access_records (id, system_id, user_id, is_privileged, user_status)
VALUES ('ACC-AMR-021', 'GXP-MES-NOVOLIFE-01', 'DUMMY-SVC-DB-001', FALSE, 'OWNER_CURRENT')
ON CONFLICT (id) DO NOTHING;
INSERT INTO access_records (id, system_id, user_id, is_privileged, user_status)
VALUES ('ACC-AMR-022', 'GXP-MES-NOVOLIFE-01', 'DUMMY-TESTER-001', FALSE, 'APPROVED_CURRENT')
ON CONFLICT (id) DO NOTHING;
INSERT INTO access_records (id, system_id, user_id, is_privileged, user_status)
VALUES ('ACC-AMR-023', 'GXP-MES-NOVOLIFE-01', 'DUMMY-TESTER-002', FALSE, 'APPROVED_CURRENT')
ON CONFLICT (id) DO NOTHING;
INSERT INTO access_records (id, system_id, user_id, is_privileged, user_status)
VALUES ('ACC-AMR-024', 'GXP-MES-NOVOLIFE-01', 'DUMMY-SVC-VAL-001', FALSE, 'OWNER_CURRENT')
ON CONFLICT (id) DO NOTHING;
INSERT INTO access_records (id, system_id, user_id, is_privileged, user_status)
VALUES ('ACC-AMR-025', 'GXP-MES-NOVOLIFE-01', 'DUMMY-DEV-001', FALSE, 'APPROVED_CURRENT')
ON CONFLICT (id) DO NOTHING;
INSERT INTO access_records (id, system_id, user_id, is_privileged, user_status)
VALUES ('ACC-AMR-026', 'GXP-MES-NOVOLIFE-01', 'DUMMY-DEVADMIN-001', TRUE, 'APPROVED_TIME_BOUND')
ON CONFLICT (id) DO NOTHING;
INSERT INTO access_records (id, system_id, user_id, is_privileged, user_status)
VALUES ('ACC-AMR-027', 'GXP-MES-NOVOLIFE-01', 'DUMMY-TRAINER-001', FALSE, 'APPROVED_CURRENT')
ON CONFLICT (id) DO NOTHING;
INSERT INTO access_records (id, system_id, user_id, is_privileged, user_status)
VALUES ('ACC-AMR-028', 'GXP-MES-NOVOLIFE-01', 'DUMMY-LEARNER-001', FALSE, 'APPROVED_CURRENT')
ON CONFLICT (id) DO NOTHING;
INSERT INTO access_records (id, system_id, user_id, is_privileged, user_status)
VALUES ('ACC-AMR-029', 'GXP-MES-NOVOLIFE-01', 'DUMMY-USER-010', FALSE, 'APPROVED_CURRENT')
ON CONFLICT (id) DO NOTHING;
INSERT INTO access_records (id, system_id, user_id, is_privileged, user_status)
VALUES ('ACC-AMR-030', 'GXP-MES-NOVOLIFE-01', 'DUMMY-USER-011', FALSE, 'APPROVED_CURRENT')
ON CONFLICT (id) DO NOTHING;

-- ---------------------------------------------------------------------------
-- suppliers / supplier_assessments -- NL-MES-SUPA-001
-- ---------------------------------------------------------------------------
--
-- NL-MES-SUPA-001 names its subject only as "Supplier Alpha - fictional
-- PAS-X product and support provider" and assigns it no controlled supplier
-- identifier anywhere in the package, so the primary key below is a
-- constructed one following the package's own DUMMY-<TYPE>-MES-### id
-- shape. That is the one identifier in these four files not lifted from a
-- source document; it is called out here rather than left to be discovered.
--
-- `status` = 'CONDITIONAL' is the report's own overall conclusion:
-- "Supplier Alpha is deemed conditionally fit for selection and controlled
-- implementation planning ... Supplier Alpha is not deemed ready to deliver
-- or operate a GxP service until the qualification assessment is complete."
--
-- `reassessment_due_date_ns` = 2027-08-10T00:00:00Z: one year from the
-- report's "Assessment date | 10 Aug 2026", per its own reassessment plan
-- ("Perform annual re-attestation of the supplier assessment"). Rego rule 6
-- (ANNEX11-S3-SUP-001) therefore correctly reports nothing -- the
-- assessment is current; it is conditional, which is a different fact and
-- one this schema has no column for.

INSERT INTO suppliers (id, system_id, name, reassessment_due_date_ns, status)
VALUES ('DUMMY-SUP-MES-001', 'GXP-MES-NOVOLIFE-01', 'Supplier Alpha - fictional PAS-X product and support provider', 1817856000000000000, 'CONDITIONAL')
ON CONFLICT (id) DO NOTHING;

INSERT INTO supplier_assessments (id, supplier_id, assessment_date_ns, result)
VALUES ('DUMMY-SUPA-MES-001', 'DUMMY-SUP-MES-001', 1786320000000000000, 'CONDITIONALLY_FIT')
ON CONFLICT (id) DO NOTHING;

-- ---------------------------------------------------------------------------
-- periodic_evaluations -- NL-MES-ITPSE-001
-- ---------------------------------------------------------------------------
--
-- `due_date_ns` is the one nanosecond value in these four files that needed
-- a judgement call, so the reasoning is written out rather than implied.
--
-- NL-MES-ITPSE-001 states no calendar next-due date. Its frequency decision
-- is conditional on a state that does not exist -- "Eight High and four
-- Medium criteria support an annual maximum ITPSE interval ONCE AN
-- OPERATING ACCOUNTING PERIOD EXISTS" -- and its only unconditional
-- obligation is a trigger, not a date: "Reassess before any hypothetical
-- activation", reinforced by FREQ-PSE-012 "annual; pre-activation
-- reassessment mandatory".
--
-- Seeding "report date + 1 year" would assert that this evaluation
-- discharged the obligation and bought twelve months. It did not. Its own
-- overall conclusion is "Evaluation complete; solution not in control, not
-- validated, not fit for operational use, and not released", all 18 of its
-- actions (PSE-ACT-001..018) are Open or Planned with none "represented as
-- implemented, tested, accepted, or closed", and 12 of those 18 are due
-- "Before hypothetical activation" or "Before release reconsideration".
--
-- So the reassessment obligation crystallised on the report's own date and
-- nothing has discharged it since. due_date_ns = 2026-08-12T00:00:00Z makes
-- a2_compliance.verify_periodic_eval_current fail (it compares against
-- time.time_ns()), which is exactly what the report itself concludes, and
-- Rego rule 7 (ANNEX11-S11-PE-001) corroborates it against the same row so
-- C1 can score the finding rather than returning INSUFFICIENT_EVIDENCE.
--
-- `status` = 'OPEN' for the same reason: 18 open actions, adverse
-- conclusion.

INSERT INTO periodic_evaluations (id, system_id, due_date_ns, status)
VALUES ('DUMMY-ITPSE-MES-001', 'GXP-MES-NOVOLIFE-01', 1786492800000000000, 'OPEN')
ON CONFLICT (id) DO NOTHING;

-- ---------------------------------------------------------------------------
-- changes / change_actions -- NL-MES-CHG-001
-- ---------------------------------------------------------------------------
--
-- The change id is DUMMY-CHG-MES-001, the pack's own "Change ID" control
-- field. This quick task's PLAN.md referred to it as `CHG-MES-001`; that
-- string appears nowhere in the source package, and the plan's own
-- constraint is that ids come from the docs, so the document's id wins.
--
-- `description` is the pack's own "Change title". `status` is 'CLOSED' per
-- "Change-record status | Closed - simulated future-state training branch
-- only".
--
-- `qa_approval_date` is NULL. The pack records the authorisation as a fact
-- -- "Quality decision | Approval for execution in isolated branch |
-- Fictional Quality role approval | Authorised - branch only" -- but
-- attaches no date to it, and its document date is the date of the pack,
-- not of the approval. Per this task's constraint, an unstated value stays
-- NULL rather than borrowing a plausible one.

INSERT INTO changes (id, system_id, description, status, qa_approval_date)
VALUES ('DUMMY-CHG-MES-001', 'GXP-MES-NOVOLIFE-01',
    'Add duplicate inbound ERP production-order quarantine alert and operator-visible reconciliation status',
    'CLOSED', NULL)
ON CONFLICT (id) DO NOTHING;

-- The twelve controlled activities from the pack's execution plan, every
-- one recorded "Complete - simulated". Rego rule 10
-- (ANNEX11-S10-CHG-001) fires on a CLOSED change with an OPEN linked
-- action; none is open here, so it correctly stays silent -- the pack's
-- evaluation is "All eight criteria are Met within the isolated fictional
-- branch". (001_seed.sql's CR-2026-089 is the seeded example that DOES
-- trip that rule; duplicating the pattern here would mean inventing an
-- unresolved action this change record does not have.)

INSERT INTO change_actions (id, change_id, description, status)
VALUES ('TASK-CHG-001', 'DUMMY-CHG-MES-001',
    'Freeze and reconcile pre-change branch baseline',
    'COMPLETE')
ON CONFLICT (id) DO NOTHING;
INSERT INTO change_actions (id, change_id, description, status)
VALUES ('TASK-CHG-002', 'DUMMY-CHG-MES-001',
    'Approve impact/risk assessment and execution scope',
    'COMPLETE')
ON CONFLICT (id) DO NOTHING;
INSERT INTO change_actions (id, change_id, description, status)
VALUES ('TASK-CHG-003', 'DUMMY-CHG-MES-001',
    'Update future-state IS/FS/DS control descriptions',
    'COMPLETE')
ON CONFLICT (id) DO NOTHING;
INSERT INTO change_actions (id, change_id, description, status)
VALUES ('TASK-CHG-004', 'DUMMY-CHG-MES-001',
    'Create versioned configuration delta and backout values',
    'COMPLETE')
ON CONFLICT (id) DO NOTHING;
INSERT INTO change_actions (id, change_id, description, status)
VALUES ('TASK-CHG-005', 'DUMMY-CHG-MES-001',
    'Configure duplicate key, quarantine state and alert event in isolated DUMMY environment',
    'COMPLETE')
ON CONFLICT (id) DO NOTHING;
INSERT INTO change_actions (id, change_id, description, status)
VALUES ('TASK-CHG-006', 'DUMMY-CHG-MES-001',
    'Peer-review configuration and least-privilege allocation',
    'COMPLETE')
ON CONFLICT (id) DO NOTHING;
INSERT INTO change_actions (id, change_id, description, status)
VALUES ('TASK-CHG-007', 'DUMMY-CHG-MES-001',
    'Execute positive, duplicate, reorder, retry/replay and concurrency verification',
    'COMPLETE')
ON CONFLICT (id) DO NOTHING;
INSERT INTO change_actions (id, change_id, description, status)
VALUES ('TASK-CHG-008', 'DUMMY-CHG-MES-001',
    'Verify alert, queue, audit record, retention and retrieval',
    'COMPLETE')
ON CONFLICT (id) DO NOTHING;
INSERT INTO change_actions (id, change_id, description, status)
VALUES ('TASK-CHG-009', 'DUMMY-CHG-MES-001',
    'Exercise backout and reconcile transaction population',
    'COMPLETE')
ON CONFLICT (id) DO NOTHING;
INSERT INTO change_actions (id, change_id, description, status)
VALUES ('TASK-CHG-010', 'DUMMY-CHG-MES-001',
    'Update simulated TRM, operations, guide, SLA and training links',
    'COMPLETE')
ON CONFLICT (id) DO NOTHING;
INSERT INTO change_actions (id, change_id, description, status)
VALUES ('TASK-CHG-011', 'DUMMY-CHG-MES-001',
    'Perform independent configuration audit against target baseline',
    'COMPLETE')
ON CONFLICT (id) DO NOTHING;
INSERT INTO change_actions (id, change_id, description, status)
VALUES ('TASK-CHG-012', 'DUMMY-CHG-MES-001',
    'Evaluate criteria, approve simulated closure and retain package HOLD',
    'COMPLETE')
ON CONFLICT (id) DO NOTHING;

-- ---------------------------------------------------------------------------
-- change_affects -- what DUMMY-CHG-MES-001 touches
-- ---------------------------------------------------------------------------
--
-- This is the table that makes Blast Radius traverse past one hop, and
-- every row below is read off NL-MES-CHG-001 section 12's own traceability
-- delta (TRACE-CHG-001..009) or impact IMP-CHG-008's named document set --
-- not inferred from a shared system_id, which D-03 explicitly rejects as an
-- edge source.
--
-- `entity_id` carries no database foreign key (002_change_affects.sql
-- explains why: Postgres cannot express one key targeting several tables by
-- a sibling column's value), and `evidence_graph._add_change_affects_edges`
-- validates `entity_type` against the frozen CHANGE_AFFECTS_ENTITY_TYPES
-- allowlist and silently skips a row whose `entity_id` does not resolve.
-- Every id below resolves: the requirements and design elements come from
-- 005_novolife_traceability.sql, the risks from this file above, and the
-- documents from 004_novolife_system.sql.
--
-- Four of the five legal entity types are used. TEST_CASE is deliberately
-- absent: the change pack's traceability delta lists URS/FS/DS/CI/INT
-- references and names no test case, and the affected requirements already
-- reach their OV test cases through the real, declared
-- REQUIREMENT --VERIFIED_BY--> TEST_CASE edge
-- (`requirements.test_case_id`). 003_change_affects_fixture.sql set that
-- precedent for CA-2026-089-1: do not hand-seed a junction row for a target
-- an existing declared relationship already reaches.


-- TRACE-CHG-001..006: the five directly affected requirements
-- (URS-MES-028/036/043/045/047) plus TRACE-CHG-006's secondary
-- audit-evidence impact (URS-MES-020/021/022). IMP-CHG-005 records
-- "No requirement change" -- these are impact links, which is exactly
-- what AFFECTS means, not rewrites.
INSERT INTO change_affects (change_id, entity_type, entity_id)
VALUES ('DUMMY-CHG-MES-001', 'REQUIREMENT', 'URS-MES-020')
ON CONFLICT (change_id, entity_type, entity_id) DO NOTHING;
INSERT INTO change_affects (change_id, entity_type, entity_id)
VALUES ('DUMMY-CHG-MES-001', 'REQUIREMENT', 'URS-MES-021')
ON CONFLICT (change_id, entity_type, entity_id) DO NOTHING;
INSERT INTO change_affects (change_id, entity_type, entity_id)
VALUES ('DUMMY-CHG-MES-001', 'REQUIREMENT', 'URS-MES-022')
ON CONFLICT (change_id, entity_type, entity_id) DO NOTHING;
INSERT INTO change_affects (change_id, entity_type, entity_id)
VALUES ('DUMMY-CHG-MES-001', 'REQUIREMENT', 'URS-MES-028')
ON CONFLICT (change_id, entity_type, entity_id) DO NOTHING;
INSERT INTO change_affects (change_id, entity_type, entity_id)
VALUES ('DUMMY-CHG-MES-001', 'REQUIREMENT', 'URS-MES-036')
ON CONFLICT (change_id, entity_type, entity_id) DO NOTHING;
INSERT INTO change_affects (change_id, entity_type, entity_id)
VALUES ('DUMMY-CHG-MES-001', 'REQUIREMENT', 'URS-MES-043')
ON CONFLICT (change_id, entity_type, entity_id) DO NOTHING;
INSERT INTO change_affects (change_id, entity_type, entity_id)
VALUES ('DUMMY-CHG-MES-001', 'REQUIREMENT', 'URS-MES-045')
ON CONFLICT (change_id, entity_type, entity_id) DO NOTHING;
INSERT INTO change_affects (change_id, entity_type, entity_id)
VALUES ('DUMMY-CHG-MES-001', 'REQUIREMENT', 'URS-MES-047')
ON CONFLICT (change_id, entity_type, entity_id) DO NOTHING;

-- The DS-MES references those same nine trace rows name alongside each
-- requirement ("FS-MES-028; DS-MES-028; CI-MES-028", etc.).
INSERT INTO change_affects (change_id, entity_type, entity_id)
VALUES ('DUMMY-CHG-MES-001', 'DESIGN_ELEMENT', 'DS-MES-020')
ON CONFLICT (change_id, entity_type, entity_id) DO NOTHING;
INSERT INTO change_affects (change_id, entity_type, entity_id)
VALUES ('DUMMY-CHG-MES-001', 'DESIGN_ELEMENT', 'DS-MES-021')
ON CONFLICT (change_id, entity_type, entity_id) DO NOTHING;
INSERT INTO change_affects (change_id, entity_type, entity_id)
VALUES ('DUMMY-CHG-MES-001', 'DESIGN_ELEMENT', 'DS-MES-022')
ON CONFLICT (change_id, entity_type, entity_id) DO NOTHING;
INSERT INTO change_affects (change_id, entity_type, entity_id)
VALUES ('DUMMY-CHG-MES-001', 'DESIGN_ELEMENT', 'DS-MES-028')
ON CONFLICT (change_id, entity_type, entity_id) DO NOTHING;
INSERT INTO change_affects (change_id, entity_type, entity_id)
VALUES ('DUMMY-CHG-MES-001', 'DESIGN_ELEMENT', 'DS-MES-036')
ON CONFLICT (change_id, entity_type, entity_id) DO NOTHING;
INSERT INTO change_affects (change_id, entity_type, entity_id)
VALUES ('DUMMY-CHG-MES-001', 'DESIGN_ELEMENT', 'DS-MES-043')
ON CONFLICT (change_id, entity_type, entity_id) DO NOTHING;
INSERT INTO change_affects (change_id, entity_type, entity_id)
VALUES ('DUMMY-CHG-MES-001', 'DESIGN_ELEMENT', 'DS-MES-045')
ON CONFLICT (change_id, entity_type, entity_id) DO NOTHING;
INSERT INTO change_affects (change_id, entity_type, entity_id)
VALUES ('DUMMY-CHG-MES-001', 'DESIGN_ELEMENT', 'DS-MES-047')
ON CONFLICT (change_id, entity_type, entity_id) DO NOTHING;

-- TRACE-CHG-007/008/009. All three remain Open in the shared register --
-- the pack is explicit that its eight local "Low" post-control labels
-- "are not shared residual-risk ratings and create no operational
-- acceptance" -- so the risks are linked, not downgraded.
INSERT INTO change_affects (change_id, entity_type, entity_id)
VALUES ('DUMMY-CHG-MES-001', 'RISK', 'RSK-MES-011')
ON CONFLICT (change_id, entity_type, entity_id) DO NOTHING;
INSERT INTO change_affects (change_id, entity_type, entity_id)
VALUES ('DUMMY-CHG-MES-001', 'RISK', 'RSK-MES-015')
ON CONFLICT (change_id, entity_type, entity_id) DO NOTHING;
INSERT INTO change_affects (change_id, entity_type, entity_id)
VALUES ('DUMMY-CHG-MES-001', 'RISK', 'RSK-MES-021')
ON CONFLICT (change_id, entity_type, entity_id) DO NOTHING;

-- IMP-CHG-008: "Documents and records | IS/DS/CS/TRM/OMSOP/UG/AG/SLA/TRN
-- would require controlled revision | Affected".
INSERT INTO change_affects (change_id, entity_type, entity_id)
VALUES ('DUMMY-CHG-MES-001', 'DOCUMENT', 'NL-MES-AG-001')
ON CONFLICT (change_id, entity_type, entity_id) DO NOTHING;
INSERT INTO change_affects (change_id, entity_type, entity_id)
VALUES ('DUMMY-CHG-MES-001', 'DOCUMENT', 'NL-MES-CS-001')
ON CONFLICT (change_id, entity_type, entity_id) DO NOTHING;
INSERT INTO change_affects (change_id, entity_type, entity_id)
VALUES ('DUMMY-CHG-MES-001', 'DOCUMENT', 'NL-MES-DS-001')
ON CONFLICT (change_id, entity_type, entity_id) DO NOTHING;
INSERT INTO change_affects (change_id, entity_type, entity_id)
VALUES ('DUMMY-CHG-MES-001', 'DOCUMENT', 'NL-MES-IS-001')
ON CONFLICT (change_id, entity_type, entity_id) DO NOTHING;
INSERT INTO change_affects (change_id, entity_type, entity_id)
VALUES ('DUMMY-CHG-MES-001', 'DOCUMENT', 'NL-MES-OMSOP-001')
ON CONFLICT (change_id, entity_type, entity_id) DO NOTHING;
INSERT INTO change_affects (change_id, entity_type, entity_id)
VALUES ('DUMMY-CHG-MES-001', 'DOCUMENT', 'NL-MES-SLA-001')
ON CONFLICT (change_id, entity_type, entity_id) DO NOTHING;
INSERT INTO change_affects (change_id, entity_type, entity_id)
VALUES ('DUMMY-CHG-MES-001', 'DOCUMENT', 'NL-MES-TRM-001')
ON CONFLICT (change_id, entity_type, entity_id) DO NOTHING;
INSERT INTO change_affects (change_id, entity_type, entity_id)
VALUES ('DUMMY-CHG-MES-001', 'DOCUMENT', 'NL-MES-TRN-001')
ON CONFLICT (change_id, entity_type, entity_id) DO NOTHING;
INSERT INTO change_affects (change_id, entity_type, entity_id)
VALUES ('DUMMY-CHG-MES-001', 'DOCUMENT', 'NL-MES-UG-001')
ON CONFLICT (change_id, entity_type, entity_id) DO NOTHING;
