-- infra/postgres/seed/005_novolife_traceability.sql
--
-- Quick task 260908-qtm, part 2 of 4. Additive demo data for
-- GXP-MES-NOVOLIFE-01; see 004_novolife_system.sql's header for why these
-- files exist, the provenance discipline they follow, and the "seed rows,
-- never response stubs" rationale. Applied after 004 by
-- infra/apply-seed.sh's sorted filename order, which is also the
-- foreign-key-safe order (gxp_systems and documents already exist).
--
-- This file seeds the requirement -> test -> design chain: 50
-- `requirements`, 82 `test_cases`, 46 `test_results` and 50
-- `design_elements`. The last three tables had ZERO rows in the entire
-- seed set before this file (001_seed.sql seeds one `test_cases` row and
-- no `test_results` or `design_elements` at all; 003_change_affects_fixture
-- .sql adds a single `design_elements` row), so this is where the evidence
-- graph gains most of its density -- `evidence_graph.py`'s TEST_RESULT and
-- DESIGN_ELEMENT node types and its REQUIREMENT --VERIFIED_BY--> TEST_CASE
-- and TEST_CASE --HAS_RESULT--> TEST_RESULT edges finally have real rows to
-- draw from.
--
-- Every column supplied here is declared by
-- infra/postgres/initdb/001_schema.sql: requirements(id, system_id,
-- req_text, test_case_id), test_cases(id, system_id, status),
-- test_results(id, test_case_id, execution_date_ns, pass_fail, tester),
-- design_elements(id, system_id, description). No column outside that DDL
-- is referenced (CLAUDE.md Rule 7).
--
-- Every INSERT ends with a conflict-safe upsert-noop guard on the `id`
-- primary key, matching 001_seed.sql's re-runnability convention.
--
-- Routed to SENT-7-05 for AegisX-AI-Project-Bible-v6.md reconciliation.

-- ---------------------------------------------------------------------------
-- test_cases, part 1 of 2: the 50 provisional operational-verification cases
-- ---------------------------------------------------------------------------
--
-- These are inserted BEFORE `requirements` purely for readability -- the
-- `requirements.test_case_id` column carries no database foreign key (see
-- the requirements block below), so no ordering is enforced here. The graph
-- builder is what actually resolves the link.
--
-- DUMMY-TC-MES-OV-001 through -050 are NL-MES-TRM-001's own planned test
-- IDs, one per requirement, and its gate check records them as "Exactly 50
-- unique planned test IDs | Pass | DUMMY-TC-MES-OV-001 through -050".
--
-- status = 'DRAFT', and that is the single most load-bearing value in this
-- file, so here is the full basis. NL-MES-TRM-001 states, in its own words:
--
--   * field rule 10: "Test case ID | This TRM | Provisional
--     DUMMY-TC-MES-OV-001 to -050"
--   * field rule 11: "Test result | Future execution/report | Not Run for
--     all 50"
--   * gate check: "No executed results claimed | Pass | 50 of 50 results
--     are Not Run"
--   * gate check: "Actual results | 0 | 0 | No execution evidence claimed"
--   * glossary: "Provisional test ID | Reserved fictional planning
--     identifier subject to approved plan/protocol control"
--
-- A reserved planning identifier with no approved protocol behind it and no
-- execution is a DRAFT test case. That is not a convenience: it is the one
-- status the app's vocabulary has for "designed but not executed", and it
-- is what makes the traceability finding TRUE rather than merely present.
--
-- It also determines how far C1 can trust the resulting finding.
-- a2_compliance.verify_test_traceability fails on either a DRAFT linked
-- test case or an unresolvable `test_case_id`, but only the DRAFT branch is
-- corroborated by the live policy bundle -- Rego rule 5
-- (ANNEX11-S4-TRC-001, policies/gxp_rules.rego) reads
-- `input.test_cases[req.test_case_id]` and is undefined, emitting no
-- violation at all, when the key is missing. Seeding these as real DRAFT
-- rows therefore yields a finding C1 can score MEDIUM against real OPA
-- corroboration; leaving the 50 links dangling would yield the same finding
-- with INSUFFICIENT_EVIDENCE and would also delete all 50
-- REQUIREMENT --VERIFIED_BY--> TEST_CASE edges from Blast Radius
-- (`evidence_graph._add_edge` drops an edge whose endpoint is absent).
-- Both the truthful reading and the useful one point the same way.

INSERT INTO test_cases (id, system_id, status)
VALUES ('DUMMY-TC-MES-OV-001', 'GXP-MES-NOVOLIFE-01', 'DRAFT')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_cases (id, system_id, status)
VALUES ('DUMMY-TC-MES-OV-002', 'GXP-MES-NOVOLIFE-01', 'DRAFT')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_cases (id, system_id, status)
VALUES ('DUMMY-TC-MES-OV-003', 'GXP-MES-NOVOLIFE-01', 'DRAFT')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_cases (id, system_id, status)
VALUES ('DUMMY-TC-MES-OV-004', 'GXP-MES-NOVOLIFE-01', 'DRAFT')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_cases (id, system_id, status)
VALUES ('DUMMY-TC-MES-OV-005', 'GXP-MES-NOVOLIFE-01', 'DRAFT')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_cases (id, system_id, status)
VALUES ('DUMMY-TC-MES-OV-006', 'GXP-MES-NOVOLIFE-01', 'DRAFT')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_cases (id, system_id, status)
VALUES ('DUMMY-TC-MES-OV-007', 'GXP-MES-NOVOLIFE-01', 'DRAFT')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_cases (id, system_id, status)
VALUES ('DUMMY-TC-MES-OV-008', 'GXP-MES-NOVOLIFE-01', 'DRAFT')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_cases (id, system_id, status)
VALUES ('DUMMY-TC-MES-OV-009', 'GXP-MES-NOVOLIFE-01', 'DRAFT')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_cases (id, system_id, status)
VALUES ('DUMMY-TC-MES-OV-010', 'GXP-MES-NOVOLIFE-01', 'DRAFT')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_cases (id, system_id, status)
VALUES ('DUMMY-TC-MES-OV-011', 'GXP-MES-NOVOLIFE-01', 'DRAFT')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_cases (id, system_id, status)
VALUES ('DUMMY-TC-MES-OV-012', 'GXP-MES-NOVOLIFE-01', 'DRAFT')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_cases (id, system_id, status)
VALUES ('DUMMY-TC-MES-OV-013', 'GXP-MES-NOVOLIFE-01', 'DRAFT')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_cases (id, system_id, status)
VALUES ('DUMMY-TC-MES-OV-014', 'GXP-MES-NOVOLIFE-01', 'DRAFT')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_cases (id, system_id, status)
VALUES ('DUMMY-TC-MES-OV-015', 'GXP-MES-NOVOLIFE-01', 'DRAFT')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_cases (id, system_id, status)
VALUES ('DUMMY-TC-MES-OV-016', 'GXP-MES-NOVOLIFE-01', 'DRAFT')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_cases (id, system_id, status)
VALUES ('DUMMY-TC-MES-OV-017', 'GXP-MES-NOVOLIFE-01', 'DRAFT')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_cases (id, system_id, status)
VALUES ('DUMMY-TC-MES-OV-018', 'GXP-MES-NOVOLIFE-01', 'DRAFT')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_cases (id, system_id, status)
VALUES ('DUMMY-TC-MES-OV-019', 'GXP-MES-NOVOLIFE-01', 'DRAFT')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_cases (id, system_id, status)
VALUES ('DUMMY-TC-MES-OV-020', 'GXP-MES-NOVOLIFE-01', 'DRAFT')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_cases (id, system_id, status)
VALUES ('DUMMY-TC-MES-OV-021', 'GXP-MES-NOVOLIFE-01', 'DRAFT')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_cases (id, system_id, status)
VALUES ('DUMMY-TC-MES-OV-022', 'GXP-MES-NOVOLIFE-01', 'DRAFT')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_cases (id, system_id, status)
VALUES ('DUMMY-TC-MES-OV-023', 'GXP-MES-NOVOLIFE-01', 'DRAFT')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_cases (id, system_id, status)
VALUES ('DUMMY-TC-MES-OV-024', 'GXP-MES-NOVOLIFE-01', 'DRAFT')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_cases (id, system_id, status)
VALUES ('DUMMY-TC-MES-OV-025', 'GXP-MES-NOVOLIFE-01', 'DRAFT')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_cases (id, system_id, status)
VALUES ('DUMMY-TC-MES-OV-026', 'GXP-MES-NOVOLIFE-01', 'DRAFT')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_cases (id, system_id, status)
VALUES ('DUMMY-TC-MES-OV-027', 'GXP-MES-NOVOLIFE-01', 'DRAFT')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_cases (id, system_id, status)
VALUES ('DUMMY-TC-MES-OV-028', 'GXP-MES-NOVOLIFE-01', 'DRAFT')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_cases (id, system_id, status)
VALUES ('DUMMY-TC-MES-OV-029', 'GXP-MES-NOVOLIFE-01', 'DRAFT')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_cases (id, system_id, status)
VALUES ('DUMMY-TC-MES-OV-030', 'GXP-MES-NOVOLIFE-01', 'DRAFT')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_cases (id, system_id, status)
VALUES ('DUMMY-TC-MES-OV-031', 'GXP-MES-NOVOLIFE-01', 'DRAFT')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_cases (id, system_id, status)
VALUES ('DUMMY-TC-MES-OV-032', 'GXP-MES-NOVOLIFE-01', 'DRAFT')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_cases (id, system_id, status)
VALUES ('DUMMY-TC-MES-OV-033', 'GXP-MES-NOVOLIFE-01', 'DRAFT')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_cases (id, system_id, status)
VALUES ('DUMMY-TC-MES-OV-034', 'GXP-MES-NOVOLIFE-01', 'DRAFT')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_cases (id, system_id, status)
VALUES ('DUMMY-TC-MES-OV-035', 'GXP-MES-NOVOLIFE-01', 'DRAFT')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_cases (id, system_id, status)
VALUES ('DUMMY-TC-MES-OV-036', 'GXP-MES-NOVOLIFE-01', 'DRAFT')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_cases (id, system_id, status)
VALUES ('DUMMY-TC-MES-OV-037', 'GXP-MES-NOVOLIFE-01', 'DRAFT')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_cases (id, system_id, status)
VALUES ('DUMMY-TC-MES-OV-038', 'GXP-MES-NOVOLIFE-01', 'DRAFT')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_cases (id, system_id, status)
VALUES ('DUMMY-TC-MES-OV-039', 'GXP-MES-NOVOLIFE-01', 'DRAFT')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_cases (id, system_id, status)
VALUES ('DUMMY-TC-MES-OV-040', 'GXP-MES-NOVOLIFE-01', 'DRAFT')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_cases (id, system_id, status)
VALUES ('DUMMY-TC-MES-OV-041', 'GXP-MES-NOVOLIFE-01', 'DRAFT')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_cases (id, system_id, status)
VALUES ('DUMMY-TC-MES-OV-042', 'GXP-MES-NOVOLIFE-01', 'DRAFT')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_cases (id, system_id, status)
VALUES ('DUMMY-TC-MES-OV-043', 'GXP-MES-NOVOLIFE-01', 'DRAFT')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_cases (id, system_id, status)
VALUES ('DUMMY-TC-MES-OV-044', 'GXP-MES-NOVOLIFE-01', 'DRAFT')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_cases (id, system_id, status)
VALUES ('DUMMY-TC-MES-OV-045', 'GXP-MES-NOVOLIFE-01', 'DRAFT')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_cases (id, system_id, status)
VALUES ('DUMMY-TC-MES-OV-046', 'GXP-MES-NOVOLIFE-01', 'DRAFT')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_cases (id, system_id, status)
VALUES ('DUMMY-TC-MES-OV-047', 'GXP-MES-NOVOLIFE-01', 'DRAFT')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_cases (id, system_id, status)
VALUES ('DUMMY-TC-MES-OV-048', 'GXP-MES-NOVOLIFE-01', 'DRAFT')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_cases (id, system_id, status)
VALUES ('DUMMY-TC-MES-OV-049', 'GXP-MES-NOVOLIFE-01', 'DRAFT')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_cases (id, system_id, status)
VALUES ('DUMMY-TC-MES-OV-050', 'GXP-MES-NOVOLIFE-01', 'DRAFT')
ON CONFLICT (id) DO NOTHING;

-- ---------------------------------------------------------------------------
-- test_cases, part 2 of 2: the 32 installation-qualification cases
-- ---------------------------------------------------------------------------
--
-- DUMMY-TC-MES-IQ-001 through -032 are NL-MES-IQTC-001's designed case set
-- ("Case population | 32 detailed cases: DUMMY-TC-MES-IQ-001 through
-- DUMMY-TC-MES-IQ-032").
--
-- status = 'PASSED' comes from NL-MES-IQR-001, not from NL-MES-IQTC-001.
-- That distinction is deliberate and the IQ Report itself insists on it:
-- "NL-MES-IQTC-001 remains unchanged: its 224 execution fields still say No
-- Run. This report uses separate simulated run objects solely to
-- demonstrate the approved reporting model. The distinction is intentional
-- and audit-visible." The protocol document is the design; the report
-- carries the execution facts. PLAN.md Task 2 says "status per the IQ
-- Report", and the IQ Report's conclusion is "all 32 cases have final
-- Passed dispositions and no open exception blocks acceptance" --
-- "IQ cases | 32 | 18 Passed / 14 Failed | 32 Passed / 0 Failed".
--
-- These 32 rows are NOT linked from any `requirements.test_case_id`, and
-- that is also from the source. NL-MES-IQTC-001 does allocate requirements
-- to cases ("Requirement allocation | URS-MES-037, URS-MES-038, ..."), but
-- IQ is the Installation Verification layer; NL-MES-TRM-001 -- the
-- controlled linkage index, and the document that owns the requirement ->
-- test relationship -- traces every one of the 50 requirements to an OV
-- case instead, and separately records "Actual results | 0". Re-pointing
-- the 50 requirements at these PASSED IQ cases would manufacture
-- requirement-verification evidence the package explicitly says does not
-- exist, and would silently turn the traceability card green. They are
-- seeded because they are real evidence of a real activity, and they carry
-- their own real results below.

INSERT INTO test_cases (id, system_id, status)
VALUES ('DUMMY-TC-MES-IQ-001', 'GXP-MES-NOVOLIFE-01', 'PASSED')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_cases (id, system_id, status)
VALUES ('DUMMY-TC-MES-IQ-002', 'GXP-MES-NOVOLIFE-01', 'PASSED')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_cases (id, system_id, status)
VALUES ('DUMMY-TC-MES-IQ-003', 'GXP-MES-NOVOLIFE-01', 'PASSED')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_cases (id, system_id, status)
VALUES ('DUMMY-TC-MES-IQ-004', 'GXP-MES-NOVOLIFE-01', 'PASSED')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_cases (id, system_id, status)
VALUES ('DUMMY-TC-MES-IQ-005', 'GXP-MES-NOVOLIFE-01', 'PASSED')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_cases (id, system_id, status)
VALUES ('DUMMY-TC-MES-IQ-006', 'GXP-MES-NOVOLIFE-01', 'PASSED')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_cases (id, system_id, status)
VALUES ('DUMMY-TC-MES-IQ-007', 'GXP-MES-NOVOLIFE-01', 'PASSED')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_cases (id, system_id, status)
VALUES ('DUMMY-TC-MES-IQ-008', 'GXP-MES-NOVOLIFE-01', 'PASSED')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_cases (id, system_id, status)
VALUES ('DUMMY-TC-MES-IQ-009', 'GXP-MES-NOVOLIFE-01', 'PASSED')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_cases (id, system_id, status)
VALUES ('DUMMY-TC-MES-IQ-010', 'GXP-MES-NOVOLIFE-01', 'PASSED')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_cases (id, system_id, status)
VALUES ('DUMMY-TC-MES-IQ-011', 'GXP-MES-NOVOLIFE-01', 'PASSED')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_cases (id, system_id, status)
VALUES ('DUMMY-TC-MES-IQ-012', 'GXP-MES-NOVOLIFE-01', 'PASSED')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_cases (id, system_id, status)
VALUES ('DUMMY-TC-MES-IQ-013', 'GXP-MES-NOVOLIFE-01', 'PASSED')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_cases (id, system_id, status)
VALUES ('DUMMY-TC-MES-IQ-014', 'GXP-MES-NOVOLIFE-01', 'PASSED')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_cases (id, system_id, status)
VALUES ('DUMMY-TC-MES-IQ-015', 'GXP-MES-NOVOLIFE-01', 'PASSED')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_cases (id, system_id, status)
VALUES ('DUMMY-TC-MES-IQ-016', 'GXP-MES-NOVOLIFE-01', 'PASSED')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_cases (id, system_id, status)
VALUES ('DUMMY-TC-MES-IQ-017', 'GXP-MES-NOVOLIFE-01', 'PASSED')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_cases (id, system_id, status)
VALUES ('DUMMY-TC-MES-IQ-018', 'GXP-MES-NOVOLIFE-01', 'PASSED')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_cases (id, system_id, status)
VALUES ('DUMMY-TC-MES-IQ-019', 'GXP-MES-NOVOLIFE-01', 'PASSED')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_cases (id, system_id, status)
VALUES ('DUMMY-TC-MES-IQ-020', 'GXP-MES-NOVOLIFE-01', 'PASSED')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_cases (id, system_id, status)
VALUES ('DUMMY-TC-MES-IQ-021', 'GXP-MES-NOVOLIFE-01', 'PASSED')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_cases (id, system_id, status)
VALUES ('DUMMY-TC-MES-IQ-022', 'GXP-MES-NOVOLIFE-01', 'PASSED')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_cases (id, system_id, status)
VALUES ('DUMMY-TC-MES-IQ-023', 'GXP-MES-NOVOLIFE-01', 'PASSED')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_cases (id, system_id, status)
VALUES ('DUMMY-TC-MES-IQ-024', 'GXP-MES-NOVOLIFE-01', 'PASSED')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_cases (id, system_id, status)
VALUES ('DUMMY-TC-MES-IQ-025', 'GXP-MES-NOVOLIFE-01', 'PASSED')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_cases (id, system_id, status)
VALUES ('DUMMY-TC-MES-IQ-026', 'GXP-MES-NOVOLIFE-01', 'PASSED')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_cases (id, system_id, status)
VALUES ('DUMMY-TC-MES-IQ-027', 'GXP-MES-NOVOLIFE-01', 'PASSED')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_cases (id, system_id, status)
VALUES ('DUMMY-TC-MES-IQ-028', 'GXP-MES-NOVOLIFE-01', 'PASSED')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_cases (id, system_id, status)
VALUES ('DUMMY-TC-MES-IQ-029', 'GXP-MES-NOVOLIFE-01', 'PASSED')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_cases (id, system_id, status)
VALUES ('DUMMY-TC-MES-IQ-030', 'GXP-MES-NOVOLIFE-01', 'PASSED')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_cases (id, system_id, status)
VALUES ('DUMMY-TC-MES-IQ-031', 'GXP-MES-NOVOLIFE-01', 'PASSED')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_cases (id, system_id, status)
VALUES ('DUMMY-TC-MES-IQ-032', 'GXP-MES-NOVOLIFE-01', 'PASSED')
ON CONFLICT (id) DO NOTHING;

-- ---------------------------------------------------------------------------
-- requirements -- all 50 URS-MES-###
-- ---------------------------------------------------------------------------
--
-- `req_text` is each requirement's own approved statement from
-- NL-MES-URS-001's requirement register, reproduced verbatim -- the TRM's
-- own field rule for this column is "Requirement statement | URS | Approved
-- statement reproduced without reinterpretation", so no summarising is done
-- here either.
--
-- `test_case_id` is NL-MES-TRM-001's own trace for that requirement:
-- URS-MES-### -> DUMMY-TC-MES-OV-###, one to one across all 50 rows. Note
-- that `requirements.test_case_id` carries NO database foreign key
-- (001_schema.sql); `evidence_graph._add_edge` drops the edge at build time
-- if the value does not resolve. Every value written here DOES resolve, to
-- the DRAFT rows inserted above -- there are no deliberately dangling links
-- in this file.
--
-- What this produces downstream, stated plainly so a later reader does not
-- "fix" it: a2_compliance.verify_test_traceability walks these rows
-- ORDER BY id, stops at the first whose linked test case is DRAFT or
-- unresolvable, and therefore cites URS-MES-001 -> DUMMY-TC-MES-OV-001. All
-- 50 are equally in that state; the check reports the first, by design.

INSERT INTO requirements (id, system_id, req_text, test_case_id)
VALUES ('URS-MES-001', 'GXP-MES-NOVOLIFE-01',
    'The MES shall make a production order available for execution only when the order is authorised, required master data are valid, and the currently approved effective master batch record or recipe is associated with the order.',
    'DUMMY-TC-MES-OV-001')
ON CONFLICT (id) DO NOTHING;
INSERT INTO requirements (id, system_id, req_text, test_case_id)
VALUES ('URS-MES-002', 'GXP-MES-NOVOLIFE-01',
    'The MES shall guide authorised users through the approved execution sequence and prevent completion of a mandatory step until its defined prerequisites and required entries are satisfied.',
    'DUMMY-TC-MES-OV-002')
ON CONFLICT (id) DO NOTHING;
INSERT INTO requirements (id, system_id, req_text, test_case_id)
VALUES ('URS-MES-003', 'GXP-MES-NOVOLIFE-01',
    'The MES shall capture required manual and automated execution values with their units, source, business context, date and time, and shall apply only approved calculation and validation rules.',
    'DUMMY-TC-MES-OV-003')
ON CONFLICT (id) DO NOTHING;
INSERT INTO requirements (id, system_id, req_text, test_case_id)
VALUES ('URS-MES-004', 'GXP-MES-NOVOLIFE-01',
    'The MES shall verify and record the identity and applicable released, available, calibration, or readiness status of materials and equipment before their controlled use in a batch step.',
    'DUMMY-TC-MES-OV-004')
ON CONFLICT (id) DO NOTHING;
INSERT INTO requirements (id, system_id, req_text, test_case_id)
VALUES ('URS-MES-005', 'GXP-MES-NOVOLIFE-01',
    'The MES shall control hold, stop, resume, cancel, and abort transitions for active execution and shall preserve the reason, authorised actor, date and time, prior state, and resulting state for each transition.',
    'DUMMY-TC-MES-OV-005')
ON CONFLICT (id) DO NOTHING;
INSERT INTO requirements (id, system_id, req_text, test_case_id)
VALUES ('URS-MES-006', 'GXP-MES-NOVOLIFE-01',
    'The MES shall identify execution exceptions against approved rules, place affected work into the defined controlled state, and present the exception with its batch context, evidence, status, and disposition linkage for authorised review-by-exception.',
    'DUMMY-TC-MES-OV-006')
ON CONFLICT (id) DO NOTHING;
INSERT INTO requirements (id, system_id, req_text, test_case_id)
VALUES ('URS-MES-007', 'GXP-MES-NOVOLIFE-01',
    'The MES shall create a complete and chronological electronic batch record containing required instructions, entries, calculated values, material and equipment use, events, exceptions, reviews, electronic signatures, and associated metadata for the executed batch.',
    'DUMMY-TC-MES-OV-007')
ON CONFLICT (id) DO NOTHING;
INSERT INTO requirements (id, system_id, req_text, test_case_id)
VALUES ('URS-MES-008', 'GXP-MES-NOVOLIFE-01',
    'The MES shall prevent final completion of an electronic batch record until all mandatory entries, steps, reviews, signatures, and blocking exception dispositions required by the approved workflow are complete.',
    'DUMMY-TC-MES-OV-008')
ON CONFLICT (id) DO NOTHING;
INSERT INTO requirements (id, system_id, req_text, test_case_id)
VALUES ('URS-MES-009', 'GXP-MES-NOVOLIFE-01',
    'The MES shall provide authorised reviewers with a controlled review view of the electronic batch record, including required exceptions, changes, signatures, and relevant audit-trail context, and shall record the review outcome and acknowledgement.',
    'DUMMY-TC-MES-OV-009')
ON CONFLICT (id) DO NOTHING;
INSERT INTO requirements (id, system_id, req_text, test_case_id)
VALUES ('URS-MES-010', 'GXP-MES-NOVOLIFE-01',
    'The MES solution shall retain electronic batch records, associated metadata, audit trails, and electronic signatures in a readable and retrievable form for the approved retention period and shall prevent unauthorised deletion or loss of required linkages.',
    'DUMMY-TC-MES-OV-010')
ON CONFLICT (id) DO NOTHING;
INSERT INTO requirements (id, system_id, req_text, test_case_id)
VALUES ('URS-MES-011', 'GXP-MES-NOVOLIFE-01',
    'The MES shall generate complete and accurate human-readable and approved electronic copies of electronic batch records, including relevant metadata, audit trails, and electronic signatures, while preserving content and meaning.',
    'DUMMY-TC-MES-OV-011')
ON CONFLICT (id) DO NOTHING;
INSERT INTO requirements (id, system_id, req_text, test_case_id)
VALUES ('URS-MES-012', 'GXP-MES-NOVOLIFE-01',
    'The MES shall require each interactive user to authenticate with a unique attributable identity through the approved identity service and shall apply approved session, lockout, and re-authentication controls.',
    'DUMMY-TC-MES-OV-012')
ON CONFLICT (id) DO NOTHING;
INSERT INTO requirements (id, system_id, req_text, test_case_id)
VALUES ('URS-MES-013', 'GXP-MES-NOVOLIFE-01',
    'The MES shall restrict functions and data to approved role-based permissions so that users can perform only the activities necessary for their assigned responsibilities.',
    'DUMMY-TC-MES-OV-013')
ON CONFLICT (id) DO NOTHING;
INSERT INTO requirements (id, system_id, req_text, test_case_id)
VALUES ('URS-MES-014', 'GXP-MES-NOVOLIFE-01',
    'The MES access process shall support approved provisioning, modification, suspension, and revocation of user access with traceable requester, approver, executor, effective date, and resulting role assignment.',
    'DUMMY-TC-MES-OV-014')
ON CONFLICT (id) DO NOTHING;
INSERT INTO requirements (id, system_id, req_text, test_case_id)
VALUES ('URS-MES-015', 'GXP-MES-NOVOLIFE-01',
    'The MES solution shall identify, restrict, own, protect, and monitor privileged and service accounts, and shall prevent their use as unowned or shared interactive business-user identities.',
    'DUMMY-TC-MES-OV-015')
ON CONFLICT (id) DO NOTHING;
INSERT INTO requirements (id, system_id, req_text, test_case_id)
VALUES ('URS-MES-016', 'GXP-MES-NOVOLIFE-01',
    'The MES access-control arrangement shall prevent or detect approved segregation-of-duties conflicts and shall enable periodic review and documented disposition of user, role, privileged, and service-account access.',
    'DUMMY-TC-MES-OV-016')
ON CONFLICT (id) DO NOTHING;
INSERT INTO requirements (id, system_id, req_text, test_case_id)
VALUES ('URS-MES-017', 'GXP-MES-NOVOLIFE-01',
    'The MES shall permit an electronic signature only for an authorised unique user acting in an approved signing role and shall require the configured authentication or re-authentication at the point of signing.',
    'DUMMY-TC-MES-OV-017')
ON CONFLICT (id) DO NOTHING;
INSERT INTO requirements (id, system_id, req_text, test_case_id)
VALUES ('URS-MES-018', 'GXP-MES-NOVOLIFE-01',
    'Each MES electronic signature shall record and display the signer''s attributable identity, the approved signature meaning, and the date and time of signing in the context of the signed record.',
    'DUMMY-TC-MES-OV-018')
ON CONFLICT (id) DO NOTHING;
INSERT INTO requirements (id, system_id, req_text, test_case_id)
VALUES ('URS-MES-019', 'GXP-MES-NOVOLIFE-01',
    'The MES shall permanently link each electronic signature to the specific signed record and version so that the signature cannot be excised, copied, transferred, or reused to approve other data without detection.',
    'DUMMY-TC-MES-OV-019')
ON CONFLICT (id) DO NOTHING;
INSERT INTO requirements (id, system_id, req_text, test_case_id)
VALUES ('URS-MES-020', 'GXP-MES-NOVOLIFE-01',
    'The MES shall automatically create secure, time-stamped audit-trail records for risk-relevant creation, modification, deletion, status, signature, access, and configuration events, including who acted, what changed, when, and the required reason or prior/new values.',
    'DUMMY-TC-MES-OV-020')
ON CONFLICT (id) DO NOTHING;
INSERT INTO requirements (id, system_id, req_text, test_case_id)
VALUES ('URS-MES-021', 'GXP-MES-NOVOLIFE-01',
    'The MES solution shall protect audit trails from unauthorised alteration or deletion, including by privileged users, and shall retain them in a readable, retrievable, and time-aligned form for at least the retention period of the associated record.',
    'DUMMY-TC-MES-OV-021')
ON CONFLICT (id) DO NOTHING;
INSERT INTO requirements (id, system_id, req_text, test_case_id)
VALUES ('URS-MES-022', 'GXP-MES-NOVOLIFE-01',
    'The MES shall allow authorised reviewers to retrieve, search, sort, filter, and export relevant audit-trail information together with the record context needed to evaluate changes, omissions, repeated actions, and unusual activity.',
    'DUMMY-TC-MES-OV-022')
ON CONFLICT (id) DO NOTHING;
INSERT INTO requirements (id, system_id, req_text, test_case_id)
VALUES ('URS-MES-023', 'GXP-MES-NOVOLIFE-01',
    'The MES shall support the approved routine, periodic, and investigation-based audit-trail review processes by presenting the defined review population and recording the reviewer, review date, outcome, identified issue, and related disposition reference.',
    'DUMMY-TC-MES-OV-023')
ON CONFLICT (id) DO NOTHING;
INSERT INTO requirements (id, system_id, req_text, test_case_id)
VALUES ('URS-MES-024', 'GXP-MES-NOVOLIFE-01',
    'The MES solution shall maintain GxP data and required metadata so they remain attributable, legible, contemporaneous, original or a verified true copy, accurate, complete, consistent, enduring, and available throughout their approved lifecycle.',
    'DUMMY-TC-MES-OV-024')
ON CONFLICT (id) DO NOTHING;
INSERT INTO requirements (id, system_id, req_text, test_case_id)
VALUES ('URS-MES-025', 'GXP-MES-NOVOLIFE-01',
    'The MES solution shall use the approved authoritative time source across application, database, interface, audit, and signature components and shall apply the defined time-zone and daylight-saving rules consistently.',
    'DUMMY-TC-MES-OV-025')
ON CONFLICT (id) DO NOTHING;
INSERT INTO requirements (id, system_id, req_text, test_case_id)
VALUES ('URS-MES-026', 'GXP-MES-NOVOLIFE-01',
    'The MES shall permit correction of GxP data only by an authorised role through the approved function while preserving the original value, corrected value, reason, actor, date and time, and required review or approval.',
    'DUMMY-TC-MES-OV-026')
ON CONFLICT (id) DO NOTHING;
INSERT INTO requirements (id, system_id, req_text, test_case_id)
VALUES ('URS-MES-027', 'GXP-MES-NOVOLIFE-01',
    'The MES solution shall preserve the content, meaning, metadata, audit trails, electronic signatures, record relationships, and required dynamic characteristics of GxP data through approved transfer, retention, archive, restore, or migration activities.',
    'DUMMY-TC-MES-OV-027')
ON CONFLICT (id) DO NOTHING;
INSERT INTO requirements (id, system_id, req_text, test_case_id)
VALUES ('URS-MES-028', 'GXP-MES-NOVOLIFE-01',
    'The MES shall receive authorised production orders and applicable master data from the designated ERP source with sufficient identifiers, version/status information, and completeness checks to accept, reject, or quarantine each inbound object deterministically.',
    'DUMMY-TC-MES-OV-028')
ON CONFLICT (id) DO NOTHING;
INSERT INTO requirements (id, system_id, req_text, test_case_id)
VALUES ('URS-MES-029', 'GXP-MES-NOVOLIFE-01',
    'The MES shall transmit authorised manufacturing confirmations, consumption, yield, and applicable status data to ERP with defined identifiers and acknowledgements sufficient to detect omission, duplication, rejection, and inconsistent state.',
    'DUMMY-TC-MES-OV-029')
ON CONFLICT (id) DO NOTHING;
INSERT INTO requirements (id, system_id, req_text, test_case_id)
VALUES ('URS-MES-030', 'GXP-MES-NOVOLIFE-01',
    'The MES shall create and transmit an authorised sample request and applicable batch/sample context to LIMS and shall track acknowledgement and sample status using stable cross-system identifiers.',
    'DUMMY-TC-MES-OV-030')
ON CONFLICT (id) DO NOTHING;
INSERT INTO requirements (id, system_id, req_text, test_case_id)
VALUES ('URS-MES-031', 'GXP-MES-NOVOLIFE-01',
    'The MES shall receive authorised LIMS results or disposition/status information, verify the cross-system identity and permitted status transition, and prevent use of late, invalid, superseded, or unmatched information without controlled disposition.',
    'DUMMY-TC-MES-OV-031')
ON CONFLICT (id) DO NOTHING;
INSERT INTO requirements (id, system_id, req_text, test_case_id)
VALUES ('URS-MES-032', 'GXP-MES-NOVOLIFE-01',
    'The MES shall transmit approved commands, setpoints, or recipe context to the automation layer only for the correct active batch and permitted process state and shall require the defined acknowledgement or safe failure response.',
    'DUMMY-TC-MES-OV-032')
ON CONFLICT (id) DO NOTHING;
INSERT INTO requirements (id, system_id, req_text, test_case_id)
VALUES ('URS-MES-033', 'GXP-MES-NOVOLIFE-01',
    'The MES shall receive required automation measurements, statuses, alarms, and events with source identity, unit, date and time, sequence, and batch/step context and shall visibly handle invalid, missing, late, or out-of-range data.',
    'DUMMY-TC-MES-OV-033')
ON CONFLICT (id) DO NOTHING;
INSERT INTO requirements (id, system_id, req_text, test_case_id)
VALUES ('URS-MES-034', 'GXP-MES-NOVOLIFE-01',
    'The MES shall publish only the approved process, event, audit-context, or performance data to the historian/reporting layer with defined source authority, time context, completeness controls, and no unauthorised write-back to the MES record.',
    'DUMMY-TC-MES-OV-034')
ON CONFLICT (id) DO NOTHING;
INSERT INTO requirements (id, system_id, req_text, test_case_id)
VALUES ('URS-MES-035', 'GXP-MES-NOVOLIFE-01',
    'The MES shall consume authentication outcomes and approved identity attributes from the designated enterprise identity service while keeping MES role assignment and regulated authorisation under controlled ownership.',
    'DUMMY-TC-MES-OV-035')
ON CONFLICT (id) DO NOTHING;
INSERT INTO requirements (id, system_id, req_text, test_case_id)
VALUES ('URS-MES-036', 'GXP-MES-NOVOLIFE-01',
    'Every in-scope MES interface shall apply approved authentication, mapping/version control, sequencing, duplicate detection, acknowledgement, timeout, retry or replay, error visibility, monitoring, and reconciliation appropriate to the transferred data and risk.',
    'DUMMY-TC-MES-OV-036')
ON CONFLICT (id) DO NOTHING;
INSERT INTO requirements (id, system_id, req_text, test_case_id)
VALUES ('URS-MES-037', 'GXP-MES-NOVOLIFE-01',
    'The MES solution shall back up all approved software, configuration, GxP data, metadata, audit trails, electronic signatures, and interface state required for recovery at the approved frequency, retention, protection, and Recovery Point Objective.',
    'DUMMY-TC-MES-OV-037')
ON CONFLICT (id) DO NOTHING;
INSERT INTO requirements (id, system_id, req_text, test_case_id)
VALUES ('URS-MES-038', 'GXP-MES-NOVOLIFE-01',
    'The MES solution shall allow authorised restoration of the approved software, configuration, records, metadata, audit trails, signatures, and interface state to a complete, accurate, and internally consistent recovery point.',
    'DUMMY-TC-MES-OV-038')
ON CONFLICT (id) DO NOTHING;
INSERT INTO requirements (id, system_id, req_text, test_case_id)
VALUES ('URS-MES-039', 'GXP-MES-NOVOLIFE-01',
    'The MES solution shall support recovery of its critical components and dependencies within the approved recovery objectives and shall require reconciliation of active batches, interfaces, exceptions, access, and data integrity before regulated execution resumes.',
    'DUMMY-TC-MES-OV-039')
ON CONFLICT (id) DO NOTHING;
INSERT INTO requirements (id, system_id, req_text, test_case_id)
VALUES ('URS-MES-040', 'GXP-MES-NOVOLIFE-01',
    'The MES backup and recovery processes shall be verified during initial implementation and at the approved operational frequency, with monitored execution, documented results, controlled issue handling, and re-verification after significant change.',
    'DUMMY-TC-MES-OV-040')
ON CONFLICT (id) DO NOTHING;
INSERT INTO requirements (id, system_id, req_text, test_case_id)
VALUES ('URS-MES-041', 'GXP-MES-NOVOLIFE-01',
    'The MES shall provide authorised users with current operational views and reports of order, batch, step, hold, exception, and completion status using controlled definitions and traceable source data.',
    'DUMMY-TC-MES-OV-041')
ON CONFLICT (id) DO NOTHING;
INSERT INTO requirements (id, system_id, req_text, test_case_id)
VALUES ('URS-MES-042', 'GXP-MES-NOVOLIFE-01',
    'The MES shall provide authorised quality/reviewer roles with a batch-focused report or view that identifies required exceptions, unresolved items, changes, signatures, review status, and links to the underlying electronic batch record and audit evidence.',
    'DUMMY-TC-MES-OV-042')
ON CONFLICT (id) DO NOTHING;
INSERT INTO requirements (id, system_id, req_text, test_case_id)
VALUES ('URS-MES-043', 'GXP-MES-NOVOLIFE-01',
    'The MES shall provide authorised support and business roles with reports or queues that identify failed, delayed, rejected, duplicated, unreconciled, or manually dispositioned interface transactions and execution exceptions.',
    'DUMMY-TC-MES-OV-043')
ON CONFLICT (id) DO NOTHING;
INSERT INTO requirements (id, system_id, req_text, test_case_id)
VALUES ('URS-MES-044', 'GXP-MES-NOVOLIFE-01',
    'Each GxP-relevant MES report or extract shall identify its source, report definition/version, execution date and time, selection criteria, and executing user, and shall prevent unauthorised alteration of the issued result.',
    'DUMMY-TC-MES-OV-044')
ON CONFLICT (id) DO NOTHING;
INSERT INTO requirements (id, system_id, req_text, test_case_id)
VALUES ('URS-MES-045', 'GXP-MES-NOVOLIFE-01',
    'The MES solution shall monitor availability, capacity, critical jobs, interfaces, storage, backup, security-relevant events, and service health and shall route actionable alerts with context and timestamp to an accountable support role.',
    'DUMMY-TC-MES-OV-045')
ON CONFLICT (id) DO NOTHING;
INSERT INTO requirements (id, system_id, req_text, test_case_id)
VALUES ('URS-MES-046', 'GXP-MES-NOVOLIFE-01',
    'The MES support process shall record, prioritise, investigate, communicate, correct, and close incidents and problems with assessment of GxP/data impact, preserved evidence, controlled workaround, restoration, root cause, and linkage to corrective change where applicable.',
    'DUMMY-TC-MES-OV-046')
ON CONFLICT (id) DO NOTHING;
INSERT INTO requirements (id, system_id, req_text, test_case_id)
VALUES ('URS-MES-047', 'GXP-MES-NOVOLIFE-01',
    'The MES lifecycle shall maintain approved configuration baselines and require documented impact and risk assessment, authorisation, controlled implementation, verification, release, and traceability update for changes affecting intended use, records, controls, interfaces, or operation.',
    'DUMMY-TC-MES-OV-047')
ON CONFLICT (id) DO NOTHING;
INSERT INTO requirements (id, system_id, req_text, test_case_id)
VALUES ('URS-MES-048', 'GXP-MES-NOVOLIFE-01',
    'The MES service arrangement shall define and maintain supplier and shared-service responsibilities, evidence access, support levels, security and quality obligations, and timely notification of relevant releases, changes, incidents, vulnerabilities, and lifecycle or support-status events.',
    'DUMMY-TC-MES-OV-048')
ON CONFLICT (id) DO NOTHING;
INSERT INTO requirements (id, system_id, req_text, test_case_id)
VALUES ('URS-MES-049', 'GXP-MES-NOVOLIFE-01',
    'The MES lifecycle shall support periodic evaluation of continued fitness for intended use, including requirements, risks, changes, incidents, access, audit-trail controls, backup/recovery, supplier performance, security, capacity, obsolescence, training, and open actions.',
    'DUMMY-TC-MES-OV-049')
ON CONFLICT (id) DO NOTHING;
INSERT INTO requirements (id, system_id, req_text, test_case_id)
VALUES ('URS-MES-050', 'GXP-MES-NOVOLIFE-01',
    'The MES operating model shall provide controlled role-based user and administrator guidance and shall permit regulated use only by personnel whose required training or qualification status is complete or managed through an approved exception.',
    'DUMMY-TC-MES-OV-050')
ON CONFLICT (id) DO NOTHING;

-- ---------------------------------------------------------------------------
-- test_results -- 46 simulated IQ run records
-- ---------------------------------------------------------------------------
--
-- One row per run object in NL-MES-IQR-001's case/run table: 32 original
-- runs (18 Passed, 14 Failed) plus the 14 targeted reruns that closed them.
-- That is the report's own arithmetic -- "Original steps | 224 | 210
-- initially Passed; 14 initially Failed; final accepted distribution 224
-- Passed after rerun" and "Defects | 8 ... Validation deviations | 6".
--
-- The 14 initial Failed rows are kept rather than overwritten. The IQ
-- Report is explicit that they are evidence, not embarrassment: "the 14
-- initial Failed values represent properly documented DUMMY
-- exception-bearing runs, not unresolved failures." Seeding only the
-- reruns would erase the exception lifecycle this package exists to
-- demonstrate.
--
-- `tester` is 'Fictional Engineering Responsible' -- NL-MES-IQR-001's own
-- execution role ("Prerequisite activation | ... | Fictional Engineering
-- Responsible"). The package names no individuals anywhere, deliberately.
--
-- `execution_date_ns` is populated only where the source states a date:
-- the 14 initial failures take the "Observed:" / "Detected on" date from
-- NL-MES-DEVL-001 / NL-MES-DEFL-001, and the 14 reruns take the date
-- printed beside them in the IQ Report's rerun column. The 18 clean runs
-- get NULL: the report gives only a "Simulated execution window | 03 Aug
-- 2026 through 10 Aug 2026" and no per-run date, and picking a date inside
-- that window would be inventing a fact (no code reads this column for
-- those rows -- `evidence_graph.py`'s TEST_RESULT property_columns are
-- ("pass_fail", "tester") only).

INSERT INTO test_results (id, test_case_id, execution_date_ns, pass_fail, tester)
VALUES ('DUMMY-RUN-MES-IQ-001-IQR', 'DUMMY-TC-MES-IQ-001', NULL, TRUE, 'Fictional Engineering Responsible')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_results (id, test_case_id, execution_date_ns, pass_fail, tester)
VALUES ('DUMMY-RUN-MES-IQ-002-DEV', 'DUMMY-TC-MES-IQ-002', 1785715200000000000, FALSE, 'Fictional Engineering Responsible')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_results (id, test_case_id, execution_date_ns, pass_fail, tester)
VALUES ('DUMMY-RUN-MES-IQ-002-DEV-R1', 'DUMMY-TC-MES-IQ-002', 1786060800000000000, TRUE, 'Fictional Engineering Responsible')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_results (id, test_case_id, execution_date_ns, pass_fail, tester)
VALUES ('DUMMY-RUN-MES-IQ-003-IQR', 'DUMMY-TC-MES-IQ-003', NULL, TRUE, 'Fictional Engineering Responsible')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_results (id, test_case_id, execution_date_ns, pass_fail, tester)
VALUES ('DUMMY-RUN-MES-IQ-004-IQR', 'DUMMY-TC-MES-IQ-004', NULL, TRUE, 'Fictional Engineering Responsible')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_results (id, test_case_id, execution_date_ns, pass_fail, tester)
VALUES ('DUMMY-RUN-MES-IQ-005', 'DUMMY-TC-MES-IQ-005', 1785715200000000000, FALSE, 'Fictional Engineering Responsible')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_results (id, test_case_id, execution_date_ns, pass_fail, tester)
VALUES ('DUMMY-RUN-MES-IQ-005-R1', 'DUMMY-TC-MES-IQ-005', 1786233600000000000, TRUE, 'Fictional Engineering Responsible')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_results (id, test_case_id, execution_date_ns, pass_fail, tester)
VALUES ('DUMMY-RUN-MES-IQ-006', 'DUMMY-TC-MES-IQ-006', 1785715200000000000, FALSE, 'Fictional Engineering Responsible')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_results (id, test_case_id, execution_date_ns, pass_fail, tester)
VALUES ('DUMMY-RUN-MES-IQ-006-R1', 'DUMMY-TC-MES-IQ-006', 1786233600000000000, TRUE, 'Fictional Engineering Responsible')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_results (id, test_case_id, execution_date_ns, pass_fail, tester)
VALUES ('DUMMY-RUN-MES-IQ-007-IQR', 'DUMMY-TC-MES-IQ-007', NULL, TRUE, 'Fictional Engineering Responsible')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_results (id, test_case_id, execution_date_ns, pass_fail, tester)
VALUES ('DUMMY-RUN-MES-IQ-008-IQR', 'DUMMY-TC-MES-IQ-008', NULL, TRUE, 'Fictional Engineering Responsible')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_results (id, test_case_id, execution_date_ns, pass_fail, tester)
VALUES ('DUMMY-RUN-MES-IQ-009-IQR', 'DUMMY-TC-MES-IQ-009', NULL, TRUE, 'Fictional Engineering Responsible')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_results (id, test_case_id, execution_date_ns, pass_fail, tester)
VALUES ('DUMMY-RUN-MES-IQ-010', 'DUMMY-TC-MES-IQ-010', 1785801600000000000, FALSE, 'Fictional Engineering Responsible')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_results (id, test_case_id, execution_date_ns, pass_fail, tester)
VALUES ('DUMMY-RUN-MES-IQ-010-R1', 'DUMMY-TC-MES-IQ-010', 1786233600000000000, TRUE, 'Fictional Engineering Responsible')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_results (id, test_case_id, execution_date_ns, pass_fail, tester)
VALUES ('DUMMY-RUN-MES-IQ-011', 'DUMMY-TC-MES-IQ-011', 1785801600000000000, FALSE, 'Fictional Engineering Responsible')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_results (id, test_case_id, execution_date_ns, pass_fail, tester)
VALUES ('DUMMY-RUN-MES-IQ-011-R1', 'DUMMY-TC-MES-IQ-011', 1786233600000000000, TRUE, 'Fictional Engineering Responsible')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_results (id, test_case_id, execution_date_ns, pass_fail, tester)
VALUES ('DUMMY-RUN-MES-IQ-012-IQR', 'DUMMY-TC-MES-IQ-012', NULL, TRUE, 'Fictional Engineering Responsible')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_results (id, test_case_id, execution_date_ns, pass_fail, tester)
VALUES ('DUMMY-RUN-MES-IQ-013', 'DUMMY-TC-MES-IQ-013', 1785888000000000000, FALSE, 'Fictional Engineering Responsible')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_results (id, test_case_id, execution_date_ns, pass_fail, tester)
VALUES ('DUMMY-RUN-MES-IQ-013-R1', 'DUMMY-TC-MES-IQ-013', 1786320000000000000, TRUE, 'Fictional Engineering Responsible')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_results (id, test_case_id, execution_date_ns, pass_fail, tester)
VALUES ('DUMMY-RUN-MES-IQ-014-IQR', 'DUMMY-TC-MES-IQ-014', NULL, TRUE, 'Fictional Engineering Responsible')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_results (id, test_case_id, execution_date_ns, pass_fail, tester)
VALUES ('DUMMY-RUN-MES-IQ-015-IQR', 'DUMMY-TC-MES-IQ-015', NULL, TRUE, 'Fictional Engineering Responsible')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_results (id, test_case_id, execution_date_ns, pass_fail, tester)
VALUES ('DUMMY-RUN-MES-IQ-016', 'DUMMY-TC-MES-IQ-016', 1785888000000000000, FALSE, 'Fictional Engineering Responsible')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_results (id, test_case_id, execution_date_ns, pass_fail, tester)
VALUES ('DUMMY-RUN-MES-IQ-016-R1', 'DUMMY-TC-MES-IQ-016', 1786320000000000000, TRUE, 'Fictional Engineering Responsible')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_results (id, test_case_id, execution_date_ns, pass_fail, tester)
VALUES ('DUMMY-RUN-MES-IQ-017-IQR', 'DUMMY-TC-MES-IQ-017', NULL, TRUE, 'Fictional Engineering Responsible')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_results (id, test_case_id, execution_date_ns, pass_fail, tester)
VALUES ('DUMMY-RUN-MES-IQ-018-IQR', 'DUMMY-TC-MES-IQ-018', NULL, TRUE, 'Fictional Engineering Responsible')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_results (id, test_case_id, execution_date_ns, pass_fail, tester)
VALUES ('DUMMY-RUN-MES-IQ-019-IQR', 'DUMMY-TC-MES-IQ-019', NULL, TRUE, 'Fictional Engineering Responsible')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_results (id, test_case_id, execution_date_ns, pass_fail, tester)
VALUES ('DUMMY-RUN-MES-IQ-020', 'DUMMY-TC-MES-IQ-020', 1785974400000000000, FALSE, 'Fictional Engineering Responsible')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_results (id, test_case_id, execution_date_ns, pass_fail, tester)
VALUES ('DUMMY-RUN-MES-IQ-020-R1', 'DUMMY-TC-MES-IQ-020', 1786320000000000000, TRUE, 'Fictional Engineering Responsible')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_results (id, test_case_id, execution_date_ns, pass_fail, tester)
VALUES ('DUMMY-RUN-MES-IQ-021-IQR', 'DUMMY-TC-MES-IQ-021', NULL, TRUE, 'Fictional Engineering Responsible')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_results (id, test_case_id, execution_date_ns, pass_fail, tester)
VALUES ('DUMMY-RUN-MES-IQ-022-DEV', 'DUMMY-TC-MES-IQ-022', 1785715200000000000, FALSE, 'Fictional Engineering Responsible')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_results (id, test_case_id, execution_date_ns, pass_fail, tester)
VALUES ('DUMMY-RUN-MES-IQ-022-DEV-R1', 'DUMMY-TC-MES-IQ-022', 1786147200000000000, TRUE, 'Fictional Engineering Responsible')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_results (id, test_case_id, execution_date_ns, pass_fail, tester)
VALUES ('DUMMY-RUN-MES-IQ-023-IQR', 'DUMMY-TC-MES-IQ-023', NULL, TRUE, 'Fictional Engineering Responsible')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_results (id, test_case_id, execution_date_ns, pass_fail, tester)
VALUES ('DUMMY-RUN-MES-IQ-024-IQR', 'DUMMY-TC-MES-IQ-024', NULL, TRUE, 'Fictional Engineering Responsible')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_results (id, test_case_id, execution_date_ns, pass_fail, tester)
VALUES ('DUMMY-RUN-MES-IQ-025-DEV', 'DUMMY-TC-MES-IQ-025', 1785888000000000000, FALSE, 'Fictional Engineering Responsible')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_results (id, test_case_id, execution_date_ns, pass_fail, tester)
VALUES ('DUMMY-RUN-MES-IQ-025-DEV-R1', 'DUMMY-TC-MES-IQ-025', 1785974400000000000, TRUE, 'Fictional Engineering Responsible')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_results (id, test_case_id, execution_date_ns, pass_fail, tester)
VALUES ('DUMMY-RUN-MES-IQ-026-IQR', 'DUMMY-TC-MES-IQ-026', NULL, TRUE, 'Fictional Engineering Responsible')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_results (id, test_case_id, execution_date_ns, pass_fail, tester)
VALUES ('DUMMY-RUN-MES-IQ-027', 'DUMMY-TC-MES-IQ-027', 1785974400000000000, FALSE, 'Fictional Engineering Responsible')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_results (id, test_case_id, execution_date_ns, pass_fail, tester)
VALUES ('DUMMY-RUN-MES-IQ-027-R1', 'DUMMY-TC-MES-IQ-027', 1786320000000000000, TRUE, 'Fictional Engineering Responsible')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_results (id, test_case_id, execution_date_ns, pass_fail, tester)
VALUES ('DUMMY-RUN-MES-IQ-028-DEV', 'DUMMY-TC-MES-IQ-028', 1785801600000000000, FALSE, 'Fictional Engineering Responsible')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_results (id, test_case_id, execution_date_ns, pass_fail, tester)
VALUES ('DUMMY-RUN-MES-IQ-028-DEV-R1', 'DUMMY-TC-MES-IQ-028', 1786233600000000000, TRUE, 'Fictional Engineering Responsible')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_results (id, test_case_id, execution_date_ns, pass_fail, tester)
VALUES ('DUMMY-RUN-MES-IQ-029-DEV', 'DUMMY-TC-MES-IQ-029', 1785801600000000000, FALSE, 'Fictional Engineering Responsible')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_results (id, test_case_id, execution_date_ns, pass_fail, tester)
VALUES ('DUMMY-RUN-MES-IQ-029-DEV-R1', 'DUMMY-TC-MES-IQ-029', 1786233600000000000, TRUE, 'Fictional Engineering Responsible')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_results (id, test_case_id, execution_date_ns, pass_fail, tester)
VALUES ('DUMMY-RUN-MES-IQ-030-DEV', 'DUMMY-TC-MES-IQ-030', 1785888000000000000, FALSE, 'Fictional Engineering Responsible')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_results (id, test_case_id, execution_date_ns, pass_fail, tester)
VALUES ('DUMMY-RUN-MES-IQ-030-DEV-R1', 'DUMMY-TC-MES-IQ-030', 1785974400000000000, TRUE, 'Fictional Engineering Responsible')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_results (id, test_case_id, execution_date_ns, pass_fail, tester)
VALUES ('DUMMY-RUN-MES-IQ-031-IQR', 'DUMMY-TC-MES-IQ-031', NULL, TRUE, 'Fictional Engineering Responsible')
ON CONFLICT (id) DO NOTHING;
INSERT INTO test_results (id, test_case_id, execution_date_ns, pass_fail, tester)
VALUES ('DUMMY-RUN-MES-IQ-032-IQR', 'DUMMY-TC-MES-IQ-032', NULL, TRUE, 'Fictional Engineering Responsible')
ON CONFLICT (id) DO NOTHING;

-- ---------------------------------------------------------------------------
-- design_elements -- the 50 DS-MES-### technical design entries
-- ---------------------------------------------------------------------------
--
-- NL-MES-DS-001's one-to-one design chain against the 50 requirements
-- (NL-MES-TRM-001 gate check: "Exactly 50 FS, DS and CI IDs | Pass |
-- One-to-one numeric design chain for every requirement"). `description` is
-- each entry's own title plus its "Technical design:" statement, truncated
-- at the entry's "Design-verification focus:" clause -- that clause
-- describes how the element will be tested, not what it is, and belongs to
-- the verification layer this column does not model.
--
-- `design_elements` was, before this file, the emptiest table in the schema
-- (one row, DE-2026-DB-01, added by 003_change_affects_fixture.sql purely so
-- a CHANGE --AFFECTS--> DESIGN_ELEMENT edge had any target at all). These
-- 50 rows are what let 006_novolife_operations.sql's change_affects entries
-- point at real design elements the change record actually names.

INSERT INTO design_elements (id, system_id, description)
VALUES ('DS-MES-001', 'GXP-MES-NOVOLIFE-01',
    'Approved order and instruction selection Technical design: An order-release service shall stage received order data separately from executable state and evaluate source authority, order status, product context and the effective approved instruction version in one controlled release transaction. Only a successful gate creates an executable instance; failure leaves the source object visible but unavailable for execution.')
ON CONFLICT (id) DO NOTHING;
INSERT INTO design_elements (id, system_id, description)
VALUES ('DS-MES-002', 'GXP-MES-NOVOLIFE-01',
    'Controlled execution sequence Technical design: Execution shall use an explicit state machine with configured allowed transitions and guard conditions for prerequisite, role, material, equipment and interface status. Each accepted transition shall commit the new state, actor/source, time and causal event atomically with the batch record.')
ON CONFLICT (id) DO NOTHING;
INSERT INTO design_elements (id, system_id, description)
VALUES ('DS-MES-003', 'GXP-MES-NOVOLIFE-01',
    'Execution data and calculation capture Technical design: A typed data-capture service shall bind entries and calculated values to batch, step, field definition, unit, precision, rule version, actor/source and time. Server-side validation shall enforce mandatory status, ranges and calculation inputs before the value transaction is committed.')
ON CONFLICT (id) DO NOTHING;
INSERT INTO design_elements (id, system_id, description)
VALUES ('DS-MES-004', 'GXP-MES-NOVOLIFE-01',
    'Material and equipment status verification Technical design: Material and equipment checks shall resolve stable identities against designated status sources and persist the evaluated status, source version/time and batch-step context. Expired, unavailable, mismatched or ambiguous items shall fail the prerequisite and create a visible exception without advancing execution.')
ON CONFLICT (id) DO NOTHING;
INSERT INTO design_elements (id, system_id, description)
VALUES ('DS-MES-005', 'GXP-MES-NOVOLIFE-01',
    'Controlled hold, resume, and termination Technical design: Hold, resume and termination shall be separate controlled commands with role, reason, current-state and dependency guards. The design shall checkpoint the execution position and incomplete transactions, prevent work while held, and require configured re-entry evidence before resume.')
ON CONFLICT (id) DO NOTHING;
INSERT INTO design_elements (id, system_id, description)
VALUES ('DS-MES-006', 'GXP-MES-NOVOLIFE-01',
    'Exception and review-by-exception handling Technical design: Exceptions shall be first-class records linked to the originating batch, step, field/event, severity, owner, status and evidence. A configurable disposition workflow shall separate creation, investigation and approval roles and block completion while a required disposition is open.')
ON CONFLICT (id) DO NOTHING;
INSERT INTO design_elements (id, system_id, description)
VALUES ('DS-MES-007', 'GXP-MES-NOVOLIFE-01',
    'Complete electronic batch record Technical design: The electronic batch record shall be assembled by stable batch identity from execution events, values, material/equipment checks, signatures, audit references, exceptions and interface evidence. A completeness manifest shall identify required record classes and their current versions without duplicating or silently omitting evidence.')
ON CONFLICT (id) DO NOTHING;
INSERT INTO design_elements (id, system_id, description)
VALUES ('DS-MES-008', 'GXP-MES-NOVOLIFE-01',
    'Batch-record completion control Technical design: A completion rule engine shall evaluate mandatory step states, data fields, calculations, signatures, exceptions, material/equipment evidence and required interface outcomes against the effective instruction version. Completion shall be a single controlled transition and shall not rely on client-side checks alone.')
ON CONFLICT (id) DO NOTHING;
INSERT INTO design_elements (id, system_id, description)
VALUES ('DS-MES-009', 'GXP-MES-NOVOLIFE-01',
    'Authorised batch-record review Technical design: The review workspace shall present the effective record version, exception population, signatures, audit history and reconciliation indicators from governed sources. Reviewer decisions shall be role-separated, attributable, time-stamped and bound to the reviewed record version; later changes shall invalidate or reopen review as configured.')
ON CONFLICT (id) DO NOTHING;
INSERT INTO design_elements (id, system_id, description)
VALUES ('DS-MES-010', 'GXP-MES-NOVOLIFE-01',
    'Record retention and retrieval Technical design: Record storage and retrieval shall index regulated records by stable business identifiers and lifecycle metadata while applying authorised retention and access rules. Retrieval shall verify package completeness and expose archived/read-only status without modifying the original record.')
ON CONFLICT (id) DO NOTHING;
INSERT INTO design_elements (id, system_id, description)
VALUES ('DS-MES-011', 'GXP-MES-NOVOLIFE-01',
    'Complete and accurate record copies Technical design: A controlled-copy service shall render a defined record package with batch identity, record/version provenance, generated-at context, signature meaning/linkage and applicable audit/exception evidence. Exports shall be marked and protected according to the approved format and access rule.')
ON CONFLICT (id) DO NOTHING;
INSERT INTO design_elements (id, system_id, description)
VALUES ('DS-MES-012', 'GXP-MES-NOVOLIFE-01',
    'Unique identity and authentication Technical design: Interactive authentication shall be mediated by the approved enterprise identity boundary and mapped to one immutable MES subject. Sessions shall be issued only after successful authentication, use configured inactivity/maximum-life controls and fail closed when identity validation is unavailable or ambiguous.')
ON CONFLICT (id) DO NOTHING;
INSERT INTO design_elements (id, system_id, description)
VALUES ('DS-MES-013', 'GXP-MES-NOVOLIFE-01',
    'Role-based least-privilege access Technical design: Server-side authorisation shall evaluate role, operation, object scope, environment and current workflow state using a deny-by-default policy. The role-permission catalogue shall be version-controlled and client visibility shall not substitute for enforcement.')
ON CONFLICT (id) DO NOTHING;
INSERT INTO design_elements (id, system_id, description)
VALUES ('DS-MES-014', 'GXP-MES-NOVOLIFE-01',
    'Controlled access lifecycle Technical design: Provisioning, modification and revocation shall use an approval-backed entitlement record with requested role/scope, effective dates, approver, source and implementation status. Revocation shall invalidate active access within the approved service objective and retain the entitlement history.')
ON CONFLICT (id) DO NOTHING;
INSERT INTO design_elements (id, system_id, description)
VALUES ('DS-MES-015', 'GXP-MES-NOVOLIFE-01',
    'Privileged and service-account control Technical design: Privileged administration and non-interactive service access shall use dedicated identities separated from routine business use, scoped to named functions and monitored. Credential storage/rotation technology, break-glass design and certificate/key values remain Verify and shall be documented in the configuration baseline.')
ON CONFLICT (id) DO NOTHING;
INSERT INTO design_elements (id, system_id, description)
VALUES ('DS-MES-016', 'GXP-MES-NOVOLIFE-01',
    'Segregation and periodic access review Technical design: A segregation-of-duties ruleset shall identify incompatible role/action combinations and evaluate new or changed access before activation. Periodic access review shall use a point-in-time entitlement/usage snapshot with reviewer decisions, conflicts, due dates and closure evidence.')
ON CONFLICT (id) DO NOTHING;
INSERT INTO design_elements (id, system_id, description)
VALUES ('DS-MES-017', 'GXP-MES-NOVOLIFE-01',
    'Authorised electronic-signature application Technical design: The signature service shall re-authenticate or otherwise invoke the approved signing control at the configured event, re-evaluate signer authority and record state, and create a signature envelope bound to the exact record/object version. The cryptographic or platform binding mechanism remains Verify.')
ON CONFLICT (id) DO NOTHING;
INSERT INTO design_elements (id, system_id, description)
VALUES ('DS-MES-018', 'GXP-MES-NOVOLIFE-01',
    'Signature meaning and content Technical design: Each signing event shall reference a controlled meaning code whose human-readable meaning is displayed before confirmation and persisted with signer identity, signed-at time and contextual statement. Meaning shall not be inferred solely from screen position or workflow state.')
ON CONFLICT (id) DO NOTHING;
INSERT INTO design_elements (id, system_id, description)
VALUES ('DS-MES-019', 'GXP-MES-NOVOLIFE-01',
    'Permanent signature-to-record linkage Technical design: Signature metadata and the signed record version shall share an immutable linkage identifier and lifecycle relationship. Copy, archive, restore and permitted migration functions shall preserve the linkage and expose any invalid or incomplete relationship.')
ON CONFLICT (id) DO NOTHING;
INSERT INTO design_elements (id, system_id, description)
VALUES ('DS-MES-020', 'GXP-MES-NOVOLIFE-01',
    'Automatic audit-trail capture Technical design: A central audit-event service shall receive regulated create, change, correction, deletion-attempt, security, signature, configuration and interface events with object, actor/source, authoritative time, action, reason, prior/new value where applicable and outcome. Event emission shall be part of, or reliably coupled to, the business transaction.')
ON CONFLICT (id) DO NOTHING;
INSERT INTO design_elements (id, system_id, description)
VALUES ('DS-MES-021', 'GXP-MES-NOVOLIFE-01',
    'Audit-trail protection and retention Technical design: The audit store shall expose append-only application interfaces, segregate administrative privileges and apply controlled retention, archive and integrity-check processes. No application or administrator function shall silently edit or purge a retained regulated event.')
ON CONFLICT (id) DO NOTHING;
INSERT INTO design_elements (id, system_id, description)
VALUES ('DS-MES-022', 'GXP-MES-NOVOLIFE-01',
    'Audit-trail search and review presentation Technical design: Audit presentation shall support authorised filtering by object, batch, user/source, event class and time while preserving event chronology and before/after/reason context. Export shall carry provenance and match the displayed governed population.')
ON CONFLICT (id) DO NOTHING;
INSERT INTO design_elements (id, system_id, description)
VALUES ('DS-MES-023', 'GXP-MES-NOVOLIFE-01',
    'Risk-based audit-trail review evidence Technical design: A review-control service shall derive the due population from approved risk-based rules, assign review ownership and retain scope, reviewer, findings, disposition and completion evidence. The reviewed event range shall be frozen or reproducibly queryable.')
ON CONFLICT (id) DO NOTHING;
INSERT INTO design_elements (id, system_id, description)
VALUES ('DS-MES-024', 'GXP-MES-NOVOLIFE-01',
    'ALCOA+ data lifecycle Technical design: The data layer shall enforce stable identifiers, mandatory metadata, referential relationships, permitted lifecycle states and atomic persistence for GxP objects. Source authority and provenance shall be explicit; silent defaulting, untracked overwrite and orphan records shall be prevented.')
ON CONFLICT (id) DO NOTHING;
INSERT INTO design_elements (id, system_id, description)
VALUES ('DS-MES-025', 'GXP-MES-NOVOLIFE-01',
    'Authoritative and consistent time Technical design: Applications and interfaces shall consume an approved enterprise time service through a defined abstraction, store canonical time with timezone/offset context and render local time without changing chronology. Drift/unavailability shall create monitored degraded-state evidence; exact tolerance remains Verify.')
ON CONFLICT (id) DO NOTHING;
INSERT INTO design_elements (id, system_id, description)
VALUES ('DS-MES-026', 'GXP-MES-NOVOLIFE-01',
    'Controlled correction of GxP data Technical design: A correction shall create a new attributable transaction linked to the prior value and shall retain reason, actor, time, affected record version and required approval/signature. The prior value shall remain retrievable and the correction shall propagate to dependent views through controlled recalculation or invalidation.')
ON CONFLICT (id) DO NOTHING;
INSERT INTO design_elements (id, system_id, description)
VALUES ('DS-MES-027', 'GXP-MES-NOVOLIFE-01',
    'Preservation through transfer, retention, and migration Technical design: Transfer, archive, restore and any approved migration shall use versioned data packages with object counts, identifiers, schema/mapping version and integrity/reconciliation evidence. Missing, extra, transformed or rejected records shall remain visible and require controlled disposition.')
ON CONFLICT (id) DO NOTHING;
INSERT INTO design_elements (id, system_id, description)
VALUES ('DS-MES-028', 'GXP-MES-NOVOLIFE-01',
    'ERP inbound orders and master data Technical design: The ERP inbound adapter shall receive the authorised order/master-data contract through CMP-MES-INT-001, validate schema and mapping version, persist correlation/idempotency state and place the candidate in staging before the release gate. All 9 ERP IS requirements remain the detailed contract authority.')
ON CONFLICT (id) DO NOTHING;
INSERT INTO design_elements (id, system_id, description)
VALUES ('DS-MES-029', 'GXP-MES-NOVOLIFE-01',
    'ERP outbound manufacturing confirmation Technical design: The ERP outbound publisher shall derive confirmation events only from authorised MES states, construct a versioned payload from governed records and retain technical/business acknowledgement, retry and reconciliation state. No uncertain delivery state shall be reported as business success.')
ON CONFLICT (id) DO NOTHING;
INSERT INTO design_elements (id, system_id, description)
VALUES ('DS-MES-030', 'GXP-MES-NOVOLIFE-01',
    'LIMS sample request and status transfer Technical design: The LIMS sample-request publisher shall allocate a stable request identity tied to batch/step and send a versioned request only from the configured execution state. Acknowledgement/status shall update the existing request state rather than create a second business request.')
ON CONFLICT (id) DO NOTHING;
INSERT INTO design_elements (id, system_id, description)
VALUES ('DS-MES-031', 'GXP-MES-NOVOLIFE-01',
    'LIMS result and disposition receipt Technical design: The LIMS result consumer shall authenticate the source, correlate request/sample identity, validate result/disposition version and mapping and expose only the permitted current state to MES decision logic. Late, superseded, unmatched or conflicting content shall be quarantined.')
ON CONFLICT (id) DO NOTHING;
INSERT INTO design_elements (id, system_id, description)
VALUES ('DS-MES-032', 'GXP-MES-NOVOLIFE-01',
    'Controlled commands to automation Technical design: The automation command gateway shall require valid batch/step/equipment context, authorised service scope, allowed command type/value and an explicit acknowledgement/final-state model. Ambiguous or timed-out outcomes shall invoke the approved safe-failure behavior and prohibit blind replay.')
ON CONFLICT (id) DO NOTHING;
INSERT INTO design_elements (id, system_id, description)
VALUES ('DS-MES-033', 'GXP-MES-NOVOLIFE-01',
    'Automation data receipt Technical design: The automation ingest path shall associate measurements, statuses, alarms and events with equipment, batch/step, sequence, quality, source time and receipt time before acceptance. Invalid or late values shall follow the configured exception rule and never overwrite retained history.')
ON CONFLICT (id) DO NOTHING;
INSERT INTO design_elements (id, system_id, description)
VALUES ('DS-MES-034', 'GXP-MES-NOVOLIFE-01',
    'Historian and reporting publication Technical design: The historian/reporting publisher shall emit authorised, versioned record events with stable source identity, event time, quality/provenance and publication state. Late correction, duplicate and replay handling shall preserve chronology and enable source-to-target reconciliation.')
ON CONFLICT (id) DO NOTHING;
INSERT INTO design_elements (id, system_id, description)
VALUES ('DS-MES-035', 'GXP-MES-NOVOLIFE-01',
    'Enterprise identity integration Technical design: The identity adapter shall map approved enterprise subjects, attributes and group/entitlement changes to MES identities without creating access from unmatched or excess attributes. Provisioning, revocation, reconciliation and service-unavailability states shall be explicit and monitored.')
ON CONFLICT (id) DO NOTHING;
INSERT INTO design_elements (id, system_id, description)
VALUES ('DS-MES-036', 'GXP-MES-NOVOLIFE-01',
    'Common interface integrity and failure control Technical design: CMP-MES-INT-001 shall provide shared contract validation, mapping/version control, correlation and idempotency, technical/business acknowledgement, retry/replay authorisation, quarantine, reconciliation, audit and monitoring services. Family-specific processing shall reuse these controls without obscuring business ownership.')
ON CONFLICT (id) DO NOTHING;
INSERT INTO design_elements (id, system_id, description)
VALUES ('DS-MES-037', 'GXP-MES-NOVOLIFE-01',
    'Risk-based backup coverage Technical design: A component/data-class backup matrix shall define protected configuration, application data, audit/signature evidence, integration state and report definitions with owner, method, schedule, retention and encryption/access expectations. Exact products, schedules and retention remain Verify.')
ON CONFLICT (id) DO NOTHING;
INSERT INTO design_elements (id, system_id, description)
VALUES ('DS-MES-038', 'GXP-MES-NOVOLIFE-01',
    'Complete and accurate restoration Technical design: Restore shall use a controlled orchestration sequence into an isolated or approved target, validate package integrity and reconstruct application/data/interface state before service exposure. Post-restore record, signature, audit and reconciliation checks shall determine acceptability.')
ON CONFLICT (id) DO NOTHING;
INSERT INTO design_elements (id, system_id, description)
VALUES ('DS-MES-039', 'GXP-MES-NOVOLIFE-01',
    'Coordinated service recovery Technical design: Recovery design shall order enterprise dependencies, database, integration, application and reporting services; preserve a safe MES execution state while dependencies are unavailable; and control restart/reconciliation of active batches and queues. Exact RTO/RPO and topology remain Verify.')
ON CONFLICT (id) DO NOTHING;
INSERT INTO design_elements (id, system_id, description)
VALUES ('DS-MES-040', 'GXP-MES-NOVOLIFE-01',
    'Backup and recovery verification and monitoring Technical design: Backup/recovery monitoring shall capture job outcome, protected object, age, capacity, restore-test due state and unresolved exception with routing and escalation. Verification evidence shall be linked to the relevant baseline and retained independently from transient tool dashboards.')
ON CONFLICT (id) DO NOTHING;
INSERT INTO design_elements (id, system_id, description)
VALUES ('DS-MES-041', 'GXP-MES-NOVOLIFE-01',
    'Operational execution reporting Technical design: Operational views shall use governed read models keyed to current order/batch state and display source time, refresh/as-of time, status and exception indicators. Cached or delayed data shall be visibly distinguished from authoritative execution state.')
ON CONFLICT (id) DO NOTHING;
INSERT INTO design_elements (id, system_id, description)
VALUES ('DS-MES-042', 'GXP-MES-NOVOLIFE-01',
    'Quality and review-by-exception reporting Technical design: Quality and review-by-exception views shall derive a reproducible batch population and join exceptions, signatures, audit events and completion evidence by stable identifiers. Reviewer decisions and drill-back shall operate on the same frozen/effective record version.')
ON CONFLICT (id) DO NOTHING;
INSERT INTO design_elements (id, system_id, description)
VALUES ('DS-MES-043', 'GXP-MES-NOVOLIFE-01',
    'Interface and exception reconciliation reporting Technical design: The reconciliation dashboard shall read the integration transaction ledger and present family, direction, state, age, source/target identities, retry/quarantine status and accountable owner. Counts and unresolved items shall be reproducible for a defined time window.')
ON CONFLICT (id) DO NOTHING;
INSERT INTO design_elements (id, system_id, description)
VALUES ('DS-MES-044', 'GXP-MES-NOVOLIFE-01',
    'Controlled report and extract provenance Technical design: Report and extract generation shall persist report definition/version, parameters, source cut-off, generated-at time, generator identity, record counts and output integrity/protection context. A user shall be able to trace output values to governed source data.')
ON CONFLICT (id) DO NOTHING;
INSERT INTO design_elements (id, system_id, description)
VALUES ('DS-MES-045', 'GXP-MES-NOVOLIFE-01',
    'Operational monitoring and alerting Technical design: Components shall emit a common health-event schema covering availability, latency/capacity, security, backup, time, interface and data-quality conditions to CMP-ENT-MON-001. Alert rules shall retain source, severity, threshold/version, routing, acknowledgement and resolution state; numeric limits remain Verify.')
ON CONFLICT (id) DO NOTHING;
INSERT INTO design_elements (id, system_id, description)
VALUES ('DS-MES-046', 'GXP-MES-NOVOLIFE-01',
    'Incident and problem control Technical design: Incident-safe behavior shall expose controlled maintenance/degraded states, preserve regulated transactions, prevent unsafe progression and provide evidence needed for triage and recovery. Incident/problem identifiers are not created here; the design defines only the data and control hooks.')
ON CONFLICT (id) DO NOTHING;
INSERT INTO design_elements (id, system_id, description)
VALUES ('DS-MES-047', 'GXP-MES-NOVOLIFE-01',
    'Controlled change and configuration baseline Technical design: Configuration and custom-code artifacts shall be versioned in approved repositories and promoted through DEV, TEST/VAL and PROD using an authorised build/release manifest, segregation and verification gates. Direct production change shall be prohibited except through a separately governed emergency process.')
ON CONFLICT (id) DO NOTHING;
INSERT INTO design_elements (id, system_id, description)
VALUES ('DS-MES-048', 'GXP-MES-NOVOLIFE-01',
    'Supplier and service-provider assurance Technical design: Supplier/product evidence shall be indexed by component, release, support status and applicable control claim, with acceptance criteria and impact links to design, risk and verification. Received packages shall be verified for identity/integrity before controlled use.')
ON CONFLICT (id) DO NOTHING;
INSERT INTO design_elements (id, system_id, description)
VALUES ('DS-MES-049', 'GXP-MES-NOVOLIFE-01',
    'Periodic evaluation of continued fitness Technical design: A maintained-state evidence view shall aggregate approved baseline, changes, incidents/problems, access/audit reviews, backup/recovery, security/vulnerability, capacity, supplier notices and training status for periodic evaluation. The review shall retain scope, sources, findings, actions and conclusion.')
ON CONFLICT (id) DO NOTHING;
INSERT INTO design_elements (id, system_id, description)
VALUES ('DS-MES-050', 'GXP-MES-NOVOLIFE-01',
    'Role-based training and controlled guidance Technical design: Role activation and controlled guidance shall reference approved role/curriculum and training-status evidence or an approved procedural control before independent regulated work. Changed functionality/role mappings shall trigger impact to training materials and authorisation state.')
ON CONFLICT (id) DO NOTHING;
