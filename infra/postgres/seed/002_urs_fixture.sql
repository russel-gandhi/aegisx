-- infra/postgres/seed/002_urs_fixture.sql
--
-- Phase 3, plan 03-04 (ORC-03, D-05). This is **additive Phase-3 test
-- fixture data**, not AegisX-AI-Project-Bible-v6.md Section 5 seed data —
-- unlike 001_seed.sql, no literal here is transcribed from the Bible.
--
-- Why it exists: `backend/app/agents/a2_compliance.py`'s
-- `verify_urs_approved` check has no APPROVED URS document row to run its
-- positive path against — Section 5 seeds only one `documents` row
-- (`DOC-2026-OM-99`, doc_type O&M, status DRAFT) for GXP-MFG-DEMO-01. This
-- file resolves 03-RESEARCH.md Open Question 1 / 03-CONTEXT.md's
-- "Resolved: RESEARCH.md Open Questions" decision by inserting one real
-- APPROVED URS document, so `verify_urs_approved`'s passing path is
-- exercised against a genuine Postgres row rather than assumed by
-- inspection (D-05).
--
-- No gap is added and none is removed: Rego rule 1
-- (`ANNEX11-S4-DOC-001`, policies/gxp_rules.rego) is scoped to
-- `doc_type == "O&M"` only, so this URS row never matches its `if` body
-- and fires no violation. The ten gaps 001_seed.sql injects, and their
-- violation count, are unchanged by this file.
--
-- Follows 001_seed.sql's own idempotency style exactly: the INSERT ends
-- with a conflict-safe upsert-noop guard on the `id` primary key, so
-- re-running this file is always safe and adds nothing on a second
-- application.
--
-- Every column supplied here is one of the nine columns
-- infra/postgres/initdb/001_schema.sql's `documents` table declares
-- (id, system_id, doc_type, title, version, author, created_date,
-- effective_date, status) — no column outside that DDL is referenced
-- (CLAUDE.md Rule 7, schema closed for this phase).
--
-- Routed to SENT-7-05 for AegisX-AI-Project-Bible-v6.md reconciliation,
-- same as every other deviation/addition recorded this phase.

INSERT INTO documents (id, system_id, doc_type, title, version, author, created_date, effective_date, status)
VALUES ('DOC-2026-URS-01', 'GXP-MFG-DEMO-01', 'URS', 'NovaSynth User Requirements Specification', 'v1.0', 'Sarah Jensen', '2026-07-01 09:00:00', '2026-07-15 00:00:00', 'APPROVED')
ON CONFLICT (id) DO NOTHING;
