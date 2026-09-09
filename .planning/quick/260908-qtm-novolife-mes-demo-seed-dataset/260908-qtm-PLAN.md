---
id: 260908-qtm
slug: novolife-mes-demo-seed-dataset
date: 2026-09-08
mode: quick
---

# Seed the NOVOLIFE MES PAS-X demo dataset from the 34-document source package

Seed a third demo system — `GXP-MES-NOVOLIFE-01` (Novo Life MES PAS-X) —
into `infra/postgres/seed/` using entity IDs and text lifted verbatim from the
34 `.docx` files in `Dummy_data/`, so that Evidence Investigation, CAPA, and
Blast Radius all render substantial, mutually-consistent content.

## Why seed data and not response stubs

C1 deterministic evidence verification is the product thesis (CLAUDE.md). Faking
assurance cards, CAPA text, or graph edges in the route/UI layer would mean
hand-typing C1 confidence grades, OPA rule ids, and graph relationships that
nothing computed — exactly the failure this product exists to prevent. Seeding
rows instead keeps A2 → C1 → OPA and the NetworkX traversal fully real; only the
*data* is added. Decided with the user 2026-09-08.

## Ground truth already established (do not re-derive)

**Doc ID scheme** (from `NL-MES-URS-001` §4.3 controlled trace direction):

```
NL-MES-SYS-001 -> URS-MES-### -> RSK-MES-### -> FS-MES-###
  -> INT-MES-* / DS-MES-### / CI-MES-### -> TC-MES-[TYPE]-###
  -> result / exception -> report -> SOP / guide / SLA
```

420 distinct entity IDs exist across the doc set: 50 `URS-MES-###`, 50
`CI-MES-###`, ~50 `DS-MES-###`, ~50 `FS-MES-###`, `RSK-MES-###`,
`TC-MES-IQ-###`, 6 `DUMMY-DEV-MES-00#` deviations, 8 `DUMMY-DEF-MES-00#`
defects, plus `CHG-MES-001`, `INT-MES-ERP-001` etc. Extracted plain text for all
35 docs is already staged at:

```
<scratchpad>/docs/*.txt
```

(one `.txt` per `.docx`, paragraphs then table rows as `cell | cell | cell`).
Regenerate with `backend/.venv/Scripts/python.exe` + `python-docx` if lost.

**Schema** — `infra/postgres/initdb/001_schema.sql` (27 tables) plus additive
migrations `002`–`006`. Relevant column lists are in that file; `action_proposals`
gains `justification, finding_id, session_id, model_id, created_at, approved_by,
approved_at, execution_result` from `003_action_proposals_workflow.sql`.

**Graph consumption** — `backend/app/graph/evidence_graph.py` `NODE_SPECS`
(15 node types) and `EDGE_SPECS` (7 relation types). Blast-radius richness comes
only from rows in those 15 tables plus `change_affects`. `design_elements`,
`test_results`, and `supplier_assessments` are currently **empty** in the seed —
they are the highest-leverage additions.

**A2 checks** — `backend/app/agents/a2_compliance.py` `A2_CHECKS` is exactly
four functions: `verify_urs_approved` (ANNEX11-S4-DOC-001),
`verify_periodic_eval_current` (ANNEX11-S11-PE-001), `verify_test_traceability`
(ANNEX11-S4-TRC-001), `verify_no_stale_documents` (ANNEX11-S4-DOC-001).

## Known constraint — state this in SUMMARY.md, do not "fix" it

Evidence Investigation renders **exactly four** assurance cards, one per
`A2_CHECKS` entry, no matter how much data is seeded. Seeding changes *what each
card cites*, not *how many cards appear*. Adding a fifth check is scope
expansion (CLAUDE.md Rule 7) and is **out of scope here**. The deliverable is
four cards citing real NOVOLIFE documents/requirements instead of the current
thin `DOC-2026-OM-99` / `URS-042` fixtures.

## Tasks

### T1 — `infra/postgres/seed/004_novolife_system.sql`

`gxp_systems` row: `GXP-MES-NOVOLIFE-01`, name "Novo Life MES PAS-X
Manufacturing Execution System", `description` from `NL-MES-SYS-001` §1.2
intended use, owner per the docs' IT System Manager role, `lifecycle_state`
`'OPERATIONAL'`, `gxp_impact TRUE`, `readiness_score` 0 (let the app compute
posture; do not guess), `last_backup_test_ns` from the BRVR report date.

All 35 `documents` rows, one per `.docx`, `id` = the doc's own `NL-MES-*-001`
identifier where the doc states one (else a stable id derived from the filename
code), `doc_type` = the filename's type code (URS, FS, DS, CS, IS, TRM, …),
`title` = the doc's own title line, `version` `'v0.1'`, `status` per the doc's
own controlled-status statement.

Deliberately set **at least one** document to `'SUPERSEDED'` and keep the URS at
its true non-`APPROVED` simulated status, so `verify_no_stale_documents` and
`verify_urs_approved` each have a real row to cite. Do not invent an approval
that the docs do not claim.

### T2 — `infra/postgres/seed/005_novolife_traceability.sql`

`requirements` — all 50 `URS-MES-001..050` with `req_text` = the doc's own
"Requirement." sentence, `test_case_id` pointing at the `TC-MES-IQ-###` the TRM
traces it to. Leave the traceability gaps the TRM itself records (unlinked or
DRAFT test cases) intact — those gaps are what `verify_test_traceability` cites.

`test_cases` — the `TC-MES-IQ-###` set from `NL-MES-IQTC-001`, `status` per the
IQ Report. `test_results` — pass/fail + tester per `NL-MES-IQR-001` and the
`DUMMY-RUN-MES-IQ-###` run records.

`design_elements` — the `DS-MES-###` set (currently zero rows exist anywhere).

### T3 — `infra/postgres/seed/006_novolife_operations.sql`

`risks` from `NL-MES-ITRA-001` / `NL-MES-ITRRA-001` (`RSK-MES-###`);
`incidents` from `NL-MES-INC-001`; `changes` + `change_actions` from
`NL-MES-CHG-001` (`CHG-MES-001`); `suppliers` + `supplier_assessments` from
`NL-MES-SUPA-001`; `access_reviews` + `access_records` from `NL-MES-AMRR-001`;
`periodic_evaluations` from `NL-MES-ITPSE-001`.

The 6 `DUMMY-DEV-MES-00#` deviations and 8 `DUMMY-DEF-MES-00#` defects have no
dedicated table — map them onto `incidents` (severity from the doc's
Major/Minor grading) rather than inventing a table. Say so in a comment.

`change_affects` rows linking `CHG-MES-001` to the REQUIREMENT / TEST_CASE /
DOCUMENT / DESIGN_ELEMENT / RISK entities it touches — only those five
`entity_type` values are legal (`CHANGE_AFFECTS_ENTITY_TYPES`). This is what
makes Blast Radius traverse beyond one hop.

### T4 — `infra/postgres/seed/007_novolife_capa.sql`

Pre-seeded `action_proposals` rows: `status`
`'PENDING'`, `finding_id` matching the finding ids A2 emits, `justification` +
`payload` written from the corresponding doc's own CAPA/remediation language,
`model_id` `'seeded'` so it is never mistaken for LLM output. These render in
the Actions queue without an LLM call; the live "Generate CAPA" button still
works and still goes through A7.

### T5 — Frontend system options

Add `GXP-MES-NOVOLIFE-01` to the static `SYSTEM_OPTIONS` arrays in
`frontend/src/pages/FindingInvestigation.tsx` and
`frontend/src/pages/BlastRadius.tsx`, and to `KNOWLEDGE_SYSTEM_IDS` in
`Knowledge.tsx` if it gates the same way. Without this the seeded system is
unreachable from the UI.

### T6 — Verify

`bash infra/apply-seed.sh` against a running stack, then confirm:
- `GET /api/systems` lists the new system
- `GET /api/systems/GXP-MES-NOVOLIFE-01/findings` returns 4 cards whose
  `evidence_ids` are NOVOLIFE ids, each with a real C1 `confidence`
- `GET /api/systems/GXP-MES-NOVOLIFE-01/evidence-graph` node/edge count is
  materially larger than `GXP-MFG-DEMO-01`'s
- blast radius from `CHANGE:CHG-MES-001` reaches more than one hop
- the Actions queue shows the seeded PENDING CAPA proposals

If Docker is not running, say so plainly in SUMMARY.md and mark verification
incomplete — do not claim a passing check that was never executed.

## Constraints

- **Do not modify** `001_seed.sql`, `002_urs_fixture.sql`, or
  `003_change_affects_fixture.sql` — `001` is byte-identical to Bible Section 5
  and load-bearing for existing tests. New files only.
- **Do not touch** `a2_compliance.py`, `c1_verifier.py`, `evidence_graph.py`,
  `findings.py`, `actions.py`, or any Rego policy. Data only. (CLAUDE.md Rules
  7 and 10.)
- Every INSERT ends with `ON CONFLICT (id) DO NOTHING`, matching `001_seed.sql`'s
  re-runnability convention.
- Regulatory citations come from the Bible Section 14 map only — the seed asserts
  no citation of its own (Rule 13).
- Names, IDs, and text come from the docs. Where a doc does not state a value,
  leave the column NULL or note it in a comment rather than inventing one — the
  docs' own "Verify:" markers exist for exactly this reason.
