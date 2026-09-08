-- infra/postgres/seed/004_novolife_system.sql
--
-- Quick task 260908-qtm, part 1 of 4 (004 system+documents, 005
-- traceability, 006 operations, 007 pre-seeded CAPA). This is **additive
-- demo data for a third GxP system**, not AegisX-AI-Project-Bible-v6.md
-- Section 5 seed data -- like 002_urs_fixture.sql and
-- 003_change_affects_fixture.sql, no literal here is transcribed from the
-- Bible.
--
-- Why it exists: Evidence Investigation, CAPA and Blast Radius were being
-- demonstrated against GXP-MFG-DEMO-01, whose entire evidence corpus is
-- two `documents` rows, one `requirements` row and one `test_cases` row
-- (001_seed.sql + 002_urs_fixture.sql). The cards render, but they cite a
-- corpus too thin to look like a real regulated system. This file and its
-- three siblings seed GXP-MES-NOVOLIFE-01 from the 35 controlled DUMMY
-- documents in Dummy_data/ -- the Novo Life MES PAS-X audit-simulation
-- package -- so the same code paths cite a realistically dense corpus.
--
-- Seed data, not response stubs, and that distinction is the whole point.
-- Faking assurance-card text, CAPA narratives or graph edges in the route
-- or UI layer would mean hand-typing C1 confidence grades, OPA rule ids and
-- graph relationships that nothing actually computed -- exactly the failure
-- this product exists to prevent (CLAUDE.md, "Core Value"). Rows keep
-- A2 -> C1 -> OPA and the NetworkX traversal fully real; this file adds
-- *data* only.
--
-- Provenance discipline. Every id, name, title, date, status and free-text
-- value below is lifted from a named .docx's own controlled fields. Where a
-- document states no value, the column is NULL and a comment says so --
-- nothing is invented to fill a gap (the source package's own "Verify:"
-- register exists for exactly that reason). Where a value required a
-- judgement call (the two non-APPROVED document statuses), the reasoning
-- and the citation are written out inline rather than left implicit.
--
-- No regulatory citation is asserted anywhere in these four files. Rule ids
-- and Annex 11 / 21 CFR 11 / ICH Q9 clause mappings come from the Bible's
-- Section 14 citation map via policies/gxp_rules.rego and
-- backend/app/agents/, never from seed data (CLAUDE.md Rule 13).
--
-- Every column supplied here is one of the eight (gxp_systems) or nine
-- (documents) columns infra/postgres/initdb/001_schema.sql declares. The
-- later additive migration 005_documents_content_hash.sql's
-- `content_sha256` is deliberately not written: it is nullable, its unique
-- index is partial (`WHERE content_sha256 IS NOT NULL`), and these rows
-- describe documents that were never uploaded through
-- `POST /api/documents`, so they have no ingested content to hash.
--
-- Follows 001_seed.sql's idempotency style exactly: every INSERT ends with
-- a conflict-safe upsert-noop guard on the `id` primary key, so re-running
-- infra/apply-seed.sh is always a no-op on a second application.
--
-- Routed to SENT-7-05 for AegisX-AI-Project-Bible-v6.md reconciliation,
-- same as every other deviation/addition recorded since Phase 3.

-- ---------------------------------------------------------------------------
-- GXP-MES-NOVOLIFE-01 -- the system row
-- ---------------------------------------------------------------------------
--
-- `description` is NL-MES-SYS-001 section 1.2 "Intended use", first
-- sentence, verbatim.
--
-- `system_owner`: NL-MES-SYS-001 section 12 assigns the maintained system
-- description, operational management and audit readiness to the "IT System
-- Manager" role, and the package writes fictional roles as "Fictional
-- <role>" -- "Fictional IT System Manager" appears literally in the source
-- set. No individual is named anywhere in the package by design.
--
-- `lifecycle_state` is 'PRE_OPERATIONAL', which is a deliberate deviation
-- from this quick task's PLAN.md Task 1 (it said 'OPERATIONAL'). The plan's
-- own overriding constraint is that values come from the docs, and the docs
-- are unambiguous and repeat it in five separate control blocks: "Current
-- package operating state | PRE-OPERATIONAL / NOT ACTIVATED" and "Current
-- package release recommendation | HOLD / DEFER - DO NOT RELEASE"
-- (NL-MES-CHG-001, NL-MES-INC-001, and echoed by NL-MES-VSR-001,
-- NL-MES-ITPSE-001 and NL-MES-URR-001). Seeding 'OPERATIONAL' would assert
-- a release the package explicitly withholds. The column is a free-text
-- display value -- `routes/systems.py` selects it and `evidence_graph.py`
-- copies it into SYSTEM node properties; nothing branches on it -- so the
-- honest value costs nothing.
--
-- `readiness_score` is 0 per PLAN.md: the app computes posture from live
-- findings (`GET /api/systems/{id}/readiness` returns this stored score
-- alongside a live `open_findings` count), and guessing a number here would
-- be inventing the one figure this product is supposed to derive.
--
-- `last_backup_test_ns` = 2026-08-11T00:00:00Z, the date of NL-MES-BRVR-001
-- ("Version / date | 0.1 / 11 Aug 2026"), whose result is "Successful
-- (simulated); 12/12 activities Passed; 0 open execution exceptions". Rego
-- rule 8 (ANNEX11-S16-BCK-001) fires only past 365 days, so this correctly
-- produces no backup-staleness violation -- the BRVR really did pass.

INSERT INTO gxp_systems (id, name, description, system_owner, lifecycle_state, gxp_impact, readiness_score, last_backup_test_ns)
VALUES (
    'GXP-MES-NOVOLIFE-01',
    'Novo Life MES PAS-X Manufacturing Execution System',
    'MES PAS-X is intended to support controlled electronic execution and documentation of pharmaceutical manufacturing at Novo Life. The planned solution receives production orders and relevant master data, presents approved manufacturing instructions, guides authorised users through configured workflows, captures execution data and approvals contemporaneously, manages exceptions and electronic records, and exchanges manufacturing status and results with connected systems.',
    'Fictional IT System Manager',
    'PRE_OPERATIONAL', TRUE, 0, 1786406400000000000
)
ON CONFLICT (id) DO NOTHING;

-- ---------------------------------------------------------------------------
-- The 35 controlled documents
-- ---------------------------------------------------------------------------
--
-- One row per .docx in Dummy_data/. `id` is each document's own
-- "Document ID" control field (NL-MES-<CODE>-001); `doc_type` is that same
-- code, which is also the type token in the filename; `title` is the
-- document's own title line. `version` is 'v0.1' for all 35 -- every
-- document's control block reads "Version | 0.1" and every version history
-- has exactly one row.
--
-- `created_date` is each document's own stated date ("Document date",
-- "Prepared date", "Report date" or "Version / date"), at 00:00:00 because
-- no document states a time of day.
--
-- `effective_date` is NULL for all 35, matching 001_seed.sql's own NULL for
-- DOC-2026-OM-99 and matching the package's repeated statement that nothing
-- here is effective: "Simulated Reviewed and Approved for Demo/Training Use
-- Only. This wording confirms only a simulated review state and is not a
-- real approval, validation conclusion, system release, or quality-system
-- decision." An effective date would assert the release the package
-- withholds.
--
-- `status` is 'APPROVED' for 33 of 35 -- mapping each document's own
-- "Simulated Reviewed and Approved for Demo/Training Use Only" controlled
-- status. Two rows are deliberately not APPROVED so that
-- verify_urs_approved and verify_no_stale_documents each have a real row to
-- cite rather than degrading to a NO-RECORD finding; both are justified
-- from the package's own review findings immediately above their INSERT.
--
-- Known consequence, recorded so it is not mistaken for a bug: these rows
-- have no `document_chunks`, because they were seeded rather than uploaded
-- through `POST /api/documents`. `GET /api/documents` derives
-- `ingestion_status` from `COUNT(chunk_id)`, so the Knowledge page renders
-- all 35 as FAILED. That is the same pre-existing behaviour GXP-MFG-DEMO-01's
-- two seeded documents already have; ingesting the .docx files through the
-- Knowledge upload flow is the intended path to READY and is out of scope
-- for a seed file.
INSERT INTO documents (id, system_id, doc_type, title, version, author, created_date, effective_date, status)
VALUES ('NL-MES-AG-001', 'GXP-MES-NOVOLIFE-01', 'AG', 'Administrator Guide', 'v0.1', 'Fictional lifecycle documentation role', '2026-08-12 00:00:00', NULL, 'APPROVED')
ON CONFLICT (id) DO NOTHING;
INSERT INTO documents (id, system_id, doc_type, title, version, author, created_date, effective_date, status)
VALUES ('NL-MES-AMRR-001', 'GXP-MES-NOVOLIFE-01', 'AMRR', 'Access Management Review Report', 'v0.1', 'Fictional Access Review Documentation Author', '2026-08-12 00:00:00', NULL, 'APPROVED')
ON CONFLICT (id) DO NOTHING;
INSERT INTO documents (id, system_id, doc_type, title, version, author, created_date, effective_date, status)
VALUES ('NL-MES-ATR-001', 'GXP-MES-NOVOLIFE-01', 'ATR', 'Audit Trail Review SOP and Baseline Review Report', 'v0.1', 'Fictional ATR Documentation Author', '2026-08-12 00:00:00', NULL, 'APPROVED')
ON CONFLICT (id) DO NOTHING;
INSERT INTO documents (id, system_id, doc_type, title, version, author, created_date, effective_date, status)
VALUES ('NL-MES-BRVR-001', 'GXP-MES-NOVOLIFE-01', 'BRVR', 'Backup and Restore Verification Report', 'v0.1', 'Fictional lifecycle documentation role', '2026-08-11 00:00:00', NULL, 'APPROVED')
ON CONFLICT (id) DO NOTHING;
INSERT INTO documents (id, system_id, doc_type, title, version, author, created_date, effective_date, status)
VALUES ('NL-MES-CHG-001', 'GXP-MES-NOVOLIFE-01', 'CHG', 'Change Record Pack', 'v0.1', 'Fictional Change Documentation Author', '2026-08-12 00:00:00', NULL, 'APPROVED')
ON CONFLICT (id) DO NOTHING;
INSERT INTO documents (id, system_id, doc_type, title, version, author, created_date, effective_date, status)
VALUES ('NL-MES-CS-001', 'GXP-MES-NOVOLIFE-01', 'CS', 'Configuration Specification', 'v0.1', 'Fictional MES Configuration Lead', '2026-08-11 00:00:00', NULL, 'APPROVED')
ON CONFLICT (id) DO NOTHING;
INSERT INTO documents (id, system_id, doc_type, title, version, author, created_date, effective_date, status)
VALUES ('NL-MES-DEFL-001', 'GXP-MES-NOVOLIFE-01', 'DEFL', 'Defect Log', 'v0.1', 'Fictional lifecycle documentation role', '2026-08-11 00:00:00', NULL, 'APPROVED')
ON CONFLICT (id) DO NOTHING;
INSERT INTO documents (id, system_id, doc_type, title, version, author, created_date, effective_date, status)
VALUES ('NL-MES-DEVL-001', 'GXP-MES-NOVOLIFE-01', 'DEVL', 'Deviation Log', 'v0.1', 'Fictional lifecycle documentation role', '2026-08-11 00:00:00', NULL, 'APPROVED')
ON CONFLICT (id) DO NOTHING;
INSERT INTO documents (id, system_id, doc_type, title, version, author, created_date, effective_date, status)
VALUES ('NL-MES-DIA-001', 'GXP-MES-NOVOLIFE-01', 'DIA', 'Data Integrity Assessment', 'v0.1', 'Fictional Data Integrity Steward', '2026-08-11 00:00:00', NULL, 'APPROVED')
ON CONFLICT (id) DO NOTHING;

-- verify_no_stale_documents' citation. NOT an invented state: the DRR's
-- own section 5.2 closure rule says "If a finding changes intended use,
-- requirement wording, risk, component allocation, data flow, software
-- category or verification scope, this DRR must be re-opened or
-- superseded before downstream reliance." DUMMY-DRF-MES-009 is exactly
-- such a finding ("Issue the dedicated 16-field traceability matrix and
-- assign controlled test-case IDs before protocol approval/execution",
-- gate PV-G5) and it is recorded Open -- "Not closed in this report" --
-- while the evidence it demanded, NL-MES-TRM-001, was issued the day
-- after the DRR. The DRR was never re-opened, so by its own rule it is
-- no longer the current basis for downstream reliance. That is
-- source-currency staleness, which is precisely what
-- a2_compliance.verify_no_stale_documents detects (and it is a distinct
-- question from approval-state: the DRR's formal disposition really is
-- "Approved with Conditions").
INSERT INTO documents (id, system_id, doc_type, title, version, author, created_date, effective_date, status)
VALUES ('NL-MES-DRR-001', 'GXP-MES-NOVOLIFE-01', 'DRR', 'Design Review Report', 'v0.1', 'Fictional Design Review Lead / Validation Lead', '2026-08-11 00:00:00', NULL, 'SUPERSEDED')
ON CONFLICT (id) DO NOTHING;
INSERT INTO documents (id, system_id, doc_type, title, version, author, created_date, effective_date, status)
VALUES ('NL-MES-DS-001', 'GXP-MES-NOVOLIFE-01', 'DS', 'Design Specification', 'v0.1', 'Fictional Solution Architect / Validation Lead', '2026-08-10 00:00:00', NULL, 'APPROVED')
ON CONFLICT (id) DO NOTHING;
INSERT INTO documents (id, system_id, doc_type, title, version, author, created_date, effective_date, status)
VALUES ('NL-MES-FS-001', 'GXP-MES-NOVOLIFE-01', 'FS', 'Functional Specification', 'v0.1', 'Fictional Validation Lead', '2026-08-10 00:00:00', NULL, 'APPROVED')
ON CONFLICT (id) DO NOTHING;
INSERT INTO documents (id, system_id, doc_type, title, version, author, created_date, effective_date, status)
VALUES ('NL-MES-INC-001', 'GXP-MES-NOVOLIFE-01', 'INC', 'Incident Sample Pack', 'v0.1', 'Fictional Incident Documentation Author', '2026-08-12 00:00:00', NULL, 'APPROVED')
ON CONFLICT (id) DO NOTHING;
INSERT INTO documents (id, system_id, doc_type, title, version, author, created_date, effective_date, status)
VALUES ('NL-MES-IPLAN-001', 'GXP-MES-NOVOLIFE-01', 'IPLAN', 'IT Implementation Plan', 'v0.1', 'Fictional IT Solution / Project Manager', '2026-08-10 00:00:00', NULL, 'APPROVED')
ON CONFLICT (id) DO NOTHING;
INSERT INTO documents (id, system_id, doc_type, title, version, author, created_date, effective_date, status)
VALUES ('NL-MES-IQP-001', 'GXP-MES-NOVOLIFE-01', 'IQP', 'Installation Qualification Protocol', 'v0.1', 'Fictional Engineering Responsible / Verification Lead', '2026-08-11 00:00:00', NULL, 'APPROVED')
ON CONFLICT (id) DO NOTHING;
INSERT INTO documents (id, system_id, doc_type, title, version, author, created_date, effective_date, status)
VALUES ('NL-MES-IQR-001', 'GXP-MES-NOVOLIFE-01', 'IQR', 'Installation Qualification Report', 'v0.1', 'Fictional lifecycle documentation role', '2026-08-11 00:00:00', NULL, 'APPROVED')
ON CONFLICT (id) DO NOTHING;
INSERT INTO documents (id, system_id, doc_type, title, version, author, created_date, effective_date, status)
VALUES ('NL-MES-IQTC-001', 'GXP-MES-NOVOLIFE-01', 'IQTC', 'IQ Test Cases', 'v0.1', 'Fictional lifecycle documentation role', '2026-08-11 00:00:00', NULL, 'APPROVED')
ON CONFLICT (id) DO NOTHING;
INSERT INTO documents (id, system_id, doc_type, title, version, author, created_date, effective_date, status)
VALUES ('NL-MES-IREP-001', 'GXP-MES-NOVOLIFE-01', 'IREP', 'IT Implementation Report', 'v0.1', 'Fictional Implementation Report Author', '2026-08-11 00:00:00', NULL, 'APPROVED')
ON CONFLICT (id) DO NOTHING;
INSERT INTO documents (id, system_id, doc_type, title, version, author, created_date, effective_date, status)
VALUES ('NL-MES-IRP-001', 'GXP-MES-NOVOLIFE-01', 'IRP', 'IT Recovery Plan', 'v0.1', 'Fictional IT Solution Manager', '2026-08-11 00:00:00', NULL, 'APPROVED')
ON CONFLICT (id) DO NOTHING;
INSERT INTO documents (id, system_id, doc_type, title, version, author, created_date, effective_date, status)
VALUES ('NL-MES-IRTR-001', 'GXP-MES-NOVOLIFE-01', 'IRTR', 'IT Recovery Test Protocol and Report', 'v0.1', 'Fictional Recovery Test Manager', '2026-08-11 00:00:00', NULL, 'APPROVED')
ON CONFLICT (id) DO NOTHING;
INSERT INTO documents (id, system_id, doc_type, title, version, author, created_date, effective_date, status)
VALUES ('NL-MES-IS-001', 'GXP-MES-NOVOLIFE-01', 'IS', 'Integration Specification', 'v0.1', 'Fictional Integration Architect', '2026-08-10 00:00:00', NULL, 'APPROVED')
ON CONFLICT (id) DO NOTHING;
INSERT INTO documents (id, system_id, doc_type, title, version, author, created_date, effective_date, status)
VALUES ('NL-MES-ITPSE-001', 'GXP-MES-NOVOLIFE-01', 'ITPSE', 'IT Periodic System Evaluation Report', 'v0.1', 'Fictional ITPSE Documentation Author', '2026-08-12 00:00:00', NULL, 'APPROVED')
ON CONFLICT (id) DO NOTHING;
INSERT INTO documents (id, system_id, doc_type, title, version, author, created_date, effective_date, status)
VALUES ('NL-MES-ITRA-001', 'GXP-MES-NOVOLIFE-01', 'ITRA', 'IT Risk Assessment', 'v0.1', 'Fictional IT Risk Responsible / Validation Lead', '2026-08-10 00:00:00', NULL, 'APPROVED')
ON CONFLICT (id) DO NOTHING;
INSERT INTO documents (id, system_id, doc_type, title, version, author, created_date, effective_date, status)
VALUES ('NL-MES-ITRRA-001', 'GXP-MES-NOVOLIFE-01', 'ITRRA', 'IT Requirement Risk Assessment', 'v0.1', 'Fictional Validation Lead / IT Risk Responsible', '2026-08-10 00:00:00', NULL, 'APPROVED')
ON CONFLICT (id) DO NOTHING;
INSERT INTO documents (id, system_id, doc_type, title, version, author, created_date, effective_date, status)
VALUES ('NL-MES-MLGP-001', 'GXP-MES-NOVOLIFE-01', 'MLGP', 'Master Lifecycle Generation Plan', 'v0.1', 'Fictional Validation Lead', '2026-08-10 00:00:00', NULL, 'APPROVED')
ON CONFLICT (id) DO NOTHING;
INSERT INTO documents (id, system_id, doc_type, title, version, author, created_date, effective_date, status)
VALUES ('NL-MES-OMSOP-001', 'GXP-MES-NOVOLIFE-01', 'OMSOP', 'Operation and Maintenance SOP', 'v0.1', 'Fictional O&M Author', '2026-08-11 00:00:00', NULL, 'APPROVED')
ON CONFLICT (id) DO NOTHING;
INSERT INTO documents (id, system_id, doc_type, title, version, author, created_date, effective_date, status)
VALUES ('NL-MES-SLA-001', 'GXP-MES-NOVOLIFE-01', 'SLA', 'Service Level Agreement', 'v0.1', 'Fictional lifecycle documentation role', '2026-08-12 00:00:00', NULL, 'APPROVED')
ON CONFLICT (id) DO NOTHING;
INSERT INTO documents (id, system_id, doc_type, title, version, author, created_date, effective_date, status)
VALUES ('NL-MES-SUPA-001', 'GXP-MES-NOVOLIFE-01', 'SUPA', 'Supplier Assessment Report', 'v0.1', 'Fictional Supplier Assessment Lead', '2026-08-10 00:00:00', NULL, 'APPROVED')
ON CONFLICT (id) DO NOTHING;
INSERT INTO documents (id, system_id, doc_type, title, version, author, created_date, effective_date, status)
VALUES ('NL-MES-SYS-001', 'GXP-MES-NOVOLIFE-01', 'SYS', 'System Overview and Description', 'v0.1', 'Fictional Validation Lead', '2026-08-10 00:00:00', NULL, 'APPROVED')
ON CONFLICT (id) DO NOTHING;
INSERT INTO documents (id, system_id, doc_type, title, version, author, created_date, effective_date, status)
VALUES ('NL-MES-TRM-001', 'GXP-MES-NOVOLIFE-01', 'TRM', 'Traceability Matrix', 'v0.1', NULL, '2026-08-11 00:00:00', NULL, 'APPROVED')
ON CONFLICT (id) DO NOTHING;
INSERT INTO documents (id, system_id, doc_type, title, version, author, created_date, effective_date, status)
VALUES ('NL-MES-TRN-001', 'GXP-MES-NOVOLIFE-01', 'TRN', 'Training Matrix / Training Evidence Index', 'v0.1', 'Fictional Training Documentation Author', '2026-08-12 00:00:00', NULL, 'APPROVED')
ON CONFLICT (id) DO NOTHING;
INSERT INTO documents (id, system_id, doc_type, title, version, author, created_date, effective_date, status)
VALUES ('NL-MES-UG-001', 'GXP-MES-NOVOLIFE-01', 'UG', 'User Guide', 'v0.1', 'Fictional lifecycle documentation role', '2026-08-11 00:00:00', NULL, 'APPROVED')
ON CONFLICT (id) DO NOTHING;
INSERT INTO documents (id, system_id, doc_type, title, version, author, created_date, effective_date, status)
VALUES ('NL-MES-URR-001', 'GXP-MES-NOVOLIFE-01', 'URR', 'User Requirement Review Report', 'v0.1', 'Fictional Requirement Review Author', '2026-08-12 00:00:00', NULL, 'APPROVED')
ON CONFLICT (id) DO NOTHING;

-- verify_urs_approved's citation, and the only doc_type = 'URS' row for
-- this system. NOT APPROVED, and no approval is invented: NL-MES-URR-001
-- (the controlled review of this exact document, 12 Aug 2026) records
-- "Current release recommendation | HOLD / DEFER - DO NOT RELEASE",
-- URR-FND-001 Major "Historical URS trace/status fields are stale" Open,
-- URR-FND-010 Major "Source-document status updates are not transacted"
-- Open, and URR-ACT-001 "Open change to harmonise 50 URS risk/trace/status
-- fields ... Before any release reconsideration | Open". A document with
-- an open, unclosed controlled revision against it is IN_REVIEW, not
-- APPROVED.
--
-- IN_REVIEW is deliberately outside verify_no_stale_documents'
-- ('SUPERSEDED','WITHDRAWN','OBSOLETE') set, so the URS-approval card and
-- the stale-document card cite two different records instead of both
-- landing on this one row (both queries are ORDER BY id LIMIT 1).
INSERT INTO documents (id, system_id, doc_type, title, version, author, created_date, effective_date, status)
VALUES ('NL-MES-URS-001', 'GXP-MES-NOVOLIFE-01', 'URS', 'User Requirement Specification', 'v0.1', 'Fictional Requirement Author / Validation Lead', '2026-08-10 00:00:00', NULL, 'IN_REVIEW')
ON CONFLICT (id) DO NOTHING;
INSERT INTO documents (id, system_id, doc_type, title, version, author, created_date, effective_date, status)
VALUES ('NL-MES-VSR-001', 'GXP-MES-NOVOLIFE-01', 'VSR', 'Final Validation Summary Report / Release Recommendation', 'v0.1', 'Fictional Validation Documentation Author', '2026-08-12 00:00:00', NULL, 'APPROVED')
ON CONFLICT (id) DO NOTHING;
