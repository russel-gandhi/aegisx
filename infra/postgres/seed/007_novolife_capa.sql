-- infra/postgres/seed/007_novolife_capa.sql
--
-- Quick task 260908-qtm, part 4 of 4. Additive demo data for
-- GXP-MES-NOVOLIFE-01; see 004_novolife_system.sql's header for why these
-- files exist and the provenance discipline they follow. Applied last by
-- infra/apply-seed.sh's sorted filename order, after the rows these
-- proposals cite already exist.
--
-- Four pre-seeded `action_proposals` rows, one per finding A2 emits for
-- this system, so the approval queue has content on a cold start without
-- any LLM call. The live "Generate CAPA" button is untouched and still runs
-- the real A7 -> C3 path; these rows sit alongside whatever it produces.
--
-- What these rows are and are NOT. They are stored CAPA prose, which is
-- exactly what `action_proposals.justification`/`payload` hold for a real
-- A7 proposal too -- routes/actions.py reads both back verbatim and
-- guarantees "no LLM prose assembled at read time". They are NOT a
-- shortcut around C1: no confidence grade, ALCOA+ score, OPA rule
-- evaluation or graph edge is written anywhere in these four files. The
-- assurance cards these proposals hang off are still computed live by
-- a2_compliance -> c1_verifier -> OPA against the rows seeded in 004-006.
-- `model_id` is the literal 'seeded' so nothing can mistake this text for
-- model output, and so a reader of the audit trail can tell the two apart.
--
-- `finding_id` matching. Each value below is what
-- `a2_compliance.finding_id_for_check` will actually derive at request
-- time, given the rows 004-006 seed. Its rule is
-- f"A2-{rule_id}-{record_id}" where record_id is the id of the row that
-- check's own SQL returns, so:
--
--   verify_urs_approved          -> the one doc_type='URS' row  -> NL-MES-URS-001
--   verify_periodic_eval_current -> latest due_date_ns          -> DUMMY-ITPSE-MES-001
--   verify_test_traceability     -> first failing requirement   -> URS-MES-001
--   verify_no_stale_documents    -> first stale doc by id       -> NL-MES-DRR-001
--
-- Two of the four share the ANNEX11-S4-DOC-001 rule id (verify_urs_approved
-- and verify_no_stale_documents both cite it -- see a2_compliance.py's own
-- docstring for why), which is why the record segment is what keeps the two
-- finding ids distinct. If a later change edits which row any of those four
-- queries returns, the corresponding proposal's `finding_id` stops
-- matching and it simply stops being associated with a card; it does not
-- corrupt anything.
--
-- `status` is 'PENDING_APPROVAL', a deliberate deviation from this task's
-- PLAN.md, which said 'PENDING'. routes/actions.py's approve and reject
-- routes both hard-check `row["status"] != "PENDING_APPROVAL"` and 409 on
-- anything else, and c3_gateway.persist_proposal writes that exact literal,
-- so 'PENDING' would render four proposals that can never be actioned.
--
-- `action_type` is 'CREATE_CAPA_RECORD' -- A7's own `A7_ACTION_TYPE`, which
-- c3_gateway.ACTION_CATEGORIES maps to GXP_RELEVANT_WRITE, one of the two
-- QUEUED_CATEGORIES that reach the human approval queue. `category` is
-- deliberately not stored (the 003_action_proposals_workflow.sql schema
-- decision derives it from action_type at read time).
--
-- `payload` matches `a7_remediation._build_capa_payload` exactly:
-- finding_id, regulatory_citations, evidence_ids, and a `capa` object with
-- the four CAPA_NARRATIVE_FIELDS plus the two server-computed fields.
-- `capa.owner` is A7's own A7_DEFAULT_OWNER. `capa.due_date` is fixed at
-- 2026-10-08 rather than computed: A7 derives it as 30 days from the
-- request, and a static file cannot call a clock, so the value is 30 days
-- from this seed's authoring date and will read as historic once that
-- passes. `justification` is composed in
-- `a7_remediation._compose_justification`'s exact "Root cause: ...
-- Corrective action: ... Preventive action: ... Effectiveness check: ..."
-- shape so a seeded proposal and a live one render identically.
--
-- `session_id`, `approved_by`, `approved_at` and `execution_result` are all
-- left unset: nothing has approved or executed these. `created_at` takes
-- its `DEFAULT now()`, which also gives the queue's `ORDER BY created_at
-- ASC, id ASC` a sane ordering.
--
-- All CAPA prose below is transcribed or paraphrased from the source
-- package's own remediation register -- URR-ACT-001/007, PSE-ACT-001..018,
-- TRM-GAP-007, DUMMY-DRF-MES-009 and the DRR's section 5.2 closure rule --
-- with the citing finding named per proposal. No regulatory clause text is
-- asserted here; the rule ids are the ones a2_compliance already carries
-- from the Bible's Section 14 map (CLAUDE.md Rule 13).
--
-- Every INSERT ends with a conflict-safe upsert-noop guard on the `id`
-- primary key.
--
-- Routed to SENT-7-05 for AegisX-AI-Project-Bible-v6.md reconciliation.

-- verify_urs_approved. Remediation language from NL-MES-URR-001's own
-- findings and action register: URR-FND-001 (Major, Open), URR-FND-010
-- (Major, Open) and URR-ACT-001.
INSERT INTO action_proposals
    (id, action_type, target_system, payload, status, justification,
     finding_id, model_id)
VALUES (
    'AP-SEED-NOVOLIFE-01',
    'CREATE_CAPA_RECORD',
    'GXP-MES-NOVOLIFE-01',
    '{"finding_id": "A2-ANNEX11-S4-DOC-001-NL-MES-URS-001", "regulatory_citations": ["ANNEX11-S4-DOC-001"], "evidence_ids": ["NL-MES-URS-001"], "capa": {"root_cause": "NL-MES-URS-001 is not in an approved state: NL-MES-URR-001 records URR-FND-001 (Major, Open) \"Historical URS trace/status fields are stale -- URS retains ''Not yet assigned/not yet assessed'' while later ITRRA/FS/DS/CS/IQ records contain links\" and URR-FND-010 (Major, Open) \"Source-document status updates are not transacted\", with an overall release recommendation of HOLD / DEFER - DO NOT RELEASE.", "corrective_action": "Execute URR-ACT-001: process the open change to harmonise the 50 URS risk, trace and status fields with the current ITRRA/FS/DS/CS/TRM evidence, then obtain the controlled approval the URR withheld.", "preventive_action": "Apply NL-MES-TRM-001''s own maintained-state trigger \"Requirement/specification approved or changed -> impact-assess URS/FS/DS/CI/INT/risk/test/operations links; version affected rows\" so a downstream record can no longer overtake the URS without the URS row being reissued under change control.", "effectiveness_check": "Re-run verify_urs_approved (ANNEX11-S4-DOC-001) against NL-MES-URS-001 after the harmonisation change closes; the check passes only when the row''s status is APPROVED, and C1 re-scores the finding from the same live row.", "due_date": "2026-10-08T00:00:00", "owner": "IT System Manager"}}'::jsonb,
    'PENDING_APPROVAL',
    'Root cause: NL-MES-URS-001 is not in an approved state: NL-MES-URR-001 records URR-FND-001 (Major, Open) "Historical URS trace/status fields are stale -- URS retains ''Not yet assigned/not yet assessed'' while later ITRRA/FS/DS/CS/IQ records contain links" and URR-FND-010 (Major, Open) "Source-document status updates are not transacted", with an overall release recommendation of HOLD / DEFER - DO NOT RELEASE. Corrective action: Execute URR-ACT-001: process the open change to harmonise the 50 URS risk, trace and status fields with the current ITRRA/FS/DS/CS/TRM evidence, then obtain the controlled approval the URR withheld. Preventive action: Apply NL-MES-TRM-001''s own maintained-state trigger "Requirement/specification approved or changed -> impact-assess URS/FS/DS/CI/INT/risk/test/operations links; version affected rows" so a downstream record can no longer overtake the URS without the URS row being reissued under change control. Effectiveness check: Re-run verify_urs_approved (ANNEX11-S4-DOC-001) against NL-MES-URS-001 after the harmonisation change closes; the check passes only when the row''s status is APPROVED, and C1 re-scores the finding from the same live row.',
    'A2-ANNEX11-S4-DOC-001-NL-MES-URS-001',
    'seeded'
)
ON CONFLICT (id) DO NOTHING;

-- verify_periodic_eval_current. Remediation language from
-- NL-MES-ITPSE-001's own action plan (PSE-ACT-001..018) and its
-- next-frequency decision.
INSERT INTO action_proposals
    (id, action_type, target_system, payload, status, justification,
     finding_id, model_id)
VALUES (
    'AP-SEED-NOVOLIFE-02',
    'CREATE_CAPA_RECORD',
    'GXP-MES-NOVOLIFE-01',
    '{"finding_id": "A2-ANNEX11-S11-PE-001-DUMMY-ITPSE-MES-001", "regulatory_citations": ["ANNEX11-S11-PE-001"], "evidence_ids": ["DUMMY-ITPSE-MES-001"], "capa": {"root_cause": "NL-MES-ITPSE-001 concluded \"solution not in control, not validated, not fit for operational use, and not released\" and left all eighteen of its actions (PSE-ACT-001..018) open -- \"No action is represented as implemented, tested, accepted, or closed\" -- while mandating a reassessment before any activation. Nothing has discharged that obligation since 12 Aug 2026.", "corrective_action": "Close the twelve pre-activation actions the report itself gates on, starting with PSE-ACT-001 (complete the six AMRR reject actions and reconcile 30/30 access assignments), PSE-ACT-006 (control implementation evidence and residual risk evaluation for all 26 shared risks) and PSE-ACT-007 (reissue the validation summary), then re-run the evaluation.", "preventive_action": "Execute PSE-ACT-017: define the controlled ITPSE evidence repositories, search criteria and 60-day production timeline for future cycles, and carry every open action forward per PSE-ACT-009 rather than restarting the register each period.", "effectiveness_check": "Re-run verify_periodic_eval_current (ANNEX11-S11-PE-001); it compares the stored due_date_ns against the current time, so it passes only once a reassessment with a future due date is actually recorded. Rego rule 7 corroborates the same row independently.", "due_date": "2026-10-08T00:00:00", "owner": "IT System Manager"}}'::jsonb,
    'PENDING_APPROVAL',
    'Root cause: NL-MES-ITPSE-001 concluded "solution not in control, not validated, not fit for operational use, and not released" and left all eighteen of its actions (PSE-ACT-001..018) open -- "No action is represented as implemented, tested, accepted, or closed" -- while mandating a reassessment before any activation. Nothing has discharged that obligation since 12 Aug 2026. Corrective action: Close the twelve pre-activation actions the report itself gates on, starting with PSE-ACT-001 (complete the six AMRR reject actions and reconcile 30/30 access assignments), PSE-ACT-006 (control implementation evidence and residual risk evaluation for all 26 shared risks) and PSE-ACT-007 (reissue the validation summary), then re-run the evaluation. Preventive action: Execute PSE-ACT-017: define the controlled ITPSE evidence repositories, search criteria and 60-day production timeline for future cycles, and carry every open action forward per PSE-ACT-009 rather than restarting the register each period. Effectiveness check: Re-run verify_periodic_eval_current (ANNEX11-S11-PE-001); it compares the stored due_date_ns against the current time, so it passes only once a reassessment with a future due date is actually recorded. Rego rule 7 corroborates the same row independently.',
    'A2-ANNEX11-S11-PE-001-DUMMY-ITPSE-MES-001',
    'seeded'
)
ON CONFLICT (id) DO NOTHING;

-- verify_test_traceability. Remediation language from URR-ACT-007,
-- NL-MES-TRM-001's TRM-GAP-007 and the DRR finding
-- DUMMY-DRF-MES-009 / gate PV-G5 those two both cite.
INSERT INTO action_proposals
    (id, action_type, target_system, payload, status, justification,
     finding_id, model_id)
VALUES (
    'AP-SEED-NOVOLIFE-03',
    'CREATE_CAPA_RECORD',
    'GXP-MES-NOVOLIFE-01',
    '{"finding_id": "A2-ANNEX11-S4-TRC-001-URS-MES-001", "regulatory_citations": ["ANNEX11-S4-TRC-001"], "evidence_ids": ["URS-MES-001"], "capa": {"root_cause": "Every one of the 50 requirements traces only to a provisional planned test ID. NL-MES-TRM-001 records \"Actual results | 0 | 0 | No execution evidence claimed\", \"50 of 50 results are Not Run\", and defines a provisional test ID as a \"Reserved fictional planning identifier subject to approved plan/protocol control\". The 32 passed IQ cases are installation evidence and do not verify requirements.", "corrective_action": "Execute URR-ACT-007: perform risk-based functional, negative, boundary, challenge, end-to-end and acceptance verification in the intended context, and close TRM-GAP-007 by approving the verification plan, protocol, detailed steps, prerequisites and acceptance criteria that gate PV-G5 requires.", "preventive_action": "Apply NL-MES-TRM-001''s \"Verification plan/protocol approved\" trigger -- replace the provisional planning state with controlled protocol and case references and a declared full/partial coverage statement -- so a reserved planning identifier can never again stand in for executed test evidence.", "effectiveness_check": "Re-run verify_test_traceability (ANNEX11-S4-TRC-001) across all 50 requirements; it passes only when every requirement resolves to a linked, non-DRAFT test case. Rego rule 5 corroborates the DRAFT condition against the same rows.", "due_date": "2026-10-08T00:00:00", "owner": "IT System Manager"}}'::jsonb,
    'PENDING_APPROVAL',
    'Root cause: Every one of the 50 requirements traces only to a provisional planned test ID. NL-MES-TRM-001 records "Actual results | 0 | 0 | No execution evidence claimed", "50 of 50 results are Not Run", and defines a provisional test ID as a "Reserved fictional planning identifier subject to approved plan/protocol control". The 32 passed IQ cases are installation evidence and do not verify requirements. Corrective action: Execute URR-ACT-007: perform risk-based functional, negative, boundary, challenge, end-to-end and acceptance verification in the intended context, and close TRM-GAP-007 by approving the verification plan, protocol, detailed steps, prerequisites and acceptance criteria that gate PV-G5 requires. Preventive action: Apply NL-MES-TRM-001''s "Verification plan/protocol approved" trigger -- replace the provisional planning state with controlled protocol and case references and a declared full/partial coverage statement -- so a reserved planning identifier can never again stand in for executed test evidence. Effectiveness check: Re-run verify_test_traceability (ANNEX11-S4-TRC-001) across all 50 requirements; it passes only when every requirement resolves to a linked, non-DRAFT test case. Rego rule 5 corroborates the DRAFT condition against the same rows.',
    'A2-ANNEX11-S4-TRC-001-URS-MES-001',
    'seeded'
)
ON CONFLICT (id) DO NOTHING;

-- verify_no_stale_documents. Remediation language from the DRR's own
-- section 5.2 closure rule and finding DUMMY-DRF-MES-009.
INSERT INTO action_proposals
    (id, action_type, target_system, payload, status, justification,
     finding_id, model_id)
VALUES (
    'AP-SEED-NOVOLIFE-04',
    'CREATE_CAPA_RECORD',
    'GXP-MES-NOVOLIFE-01',
    '{"finding_id": "A2-ANNEX11-S4-DOC-001-NL-MES-DRR-001", "regulatory_citations": ["ANNEX11-S4-DOC-001"], "evidence_ids": ["NL-MES-DRR-001"], "capa": {"root_cause": "NL-MES-DRR-001 is no longer the current basis for downstream reliance. Its own section 5.2 states that a finding changing verification scope requires the DRR to be re-opened or superseded before downstream reliance; DUMMY-DRF-MES-009 (\"Issue the dedicated 16-field traceability matrix and assign controlled test-case IDs before protocol approval/execution\", gate PV-G5) is recorded Open and \"Not closed in this report\", and NL-MES-TRM-001 was issued the day after the DRR without the DRR being re-opened.", "corrective_action": "Re-open NL-MES-DRR-001 against the issued NL-MES-TRM-001, close DUMMY-DRF-MES-009 through the DRR''s own closure rule (identify the controlled evidence, update affected source specifications and traceability, assess impact, record the System Owner and Quality decisions), and reissue the review as the current design baseline.", "preventive_action": "Apply the DRR''s own reliance rule as a standing gate: no downstream protocol approval or execution proceeds against a design review whose PV gates (PV-G1..PV-G5) are still open, so a superseded review cannot be cited as current governing evidence.", "effectiveness_check": "Re-run verify_no_stale_documents (ANNEX11-S4-DOC-001) for this system; it passes only when no document row remains in SUPERSEDED, WITHDRAWN or OBSOLETE state, and C1 re-derives the finding from the live documents row rather than from this stored text.", "due_date": "2026-10-08T00:00:00", "owner": "IT System Manager"}}'::jsonb,
    'PENDING_APPROVAL',
    'Root cause: NL-MES-DRR-001 is no longer the current basis for downstream reliance. Its own section 5.2 states that a finding changing verification scope requires the DRR to be re-opened or superseded before downstream reliance; DUMMY-DRF-MES-009 ("Issue the dedicated 16-field traceability matrix and assign controlled test-case IDs before protocol approval/execution", gate PV-G5) is recorded Open and "Not closed in this report", and NL-MES-TRM-001 was issued the day after the DRR without the DRR being re-opened. Corrective action: Re-open NL-MES-DRR-001 against the issued NL-MES-TRM-001, close DUMMY-DRF-MES-009 through the DRR''s own closure rule (identify the controlled evidence, update affected source specifications and traceability, assess impact, record the System Owner and Quality decisions), and reissue the review as the current design baseline. Preventive action: Apply the DRR''s own reliance rule as a standing gate: no downstream protocol approval or execution proceeds against a design review whose PV gates (PV-G1..PV-G5) are still open, so a superseded review cannot be cited as current governing evidence. Effectiveness check: Re-run verify_no_stale_documents (ANNEX11-S4-DOC-001) for this system; it passes only when no document row remains in SUPERSEDED, WITHDRAWN or OBSOLETE state, and C1 re-derives the finding from the live documents row rather than from this stored text.',
    'A2-ANNEX11-S4-DOC-001-NL-MES-DRR-001',
    'seeded'
)
ON CONFLICT (id) DO NOTHING;
