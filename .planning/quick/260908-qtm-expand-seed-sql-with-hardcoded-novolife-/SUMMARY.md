---
id: 260908-qtm
slug: expand-seed-sql-with-hardcoded-novolife-
date: 2026-09-08
mode: quick
status: complete
---

# Summary — NOVOLIFE MES PAS-X demo dataset

Seeded a third demo system, `GXP-MES-NOVOLIFE-01` ("Novo Life MES PAS-X
Manufacturing Execution System"), from the 34 `Dummy_data/*.docx` files, so that
Evidence Investigation, CAPA, and Blast Radius render substantial,
mutually-consistent, document-grounded content.

**No backend Python and no Rego policy was modified.** A2 → C1 → OPA and the
NetworkX traversal are untouched; only data is hardcoded. This was the explicit
point of the approach (see PLAN.md "Why seed data and not response stubs").

## Commits

| Commit | Task | Contents |
|---|---|---|
| `1e42f9b` | T1 | `004_novolife_system.sql` — system + 35 documents |
| `f6f56b2` | T2 | `005_novolife_traceability.sql` — requirements/tests/design |
| `c9a7951` | T3 | `006_novolife_operations.sql` — risk/incident/access/supplier/change |
| `bbc28bb` | T4 | `007_novolife_capa.sql` — 4 pre-seeded CAPA proposals |
| `09d0aef` | T5 | frontend system pickers |

The executor hit a session usage limit immediately after `09d0aef` and before
writing this file. All five task commits had already landed with a clean working
tree; the orchestrator completed T6 verification and this summary.

## Rows seeded (384 total)

| Table | Rows | | Table | Rows |
|---|---|---|---|---|
| `documents` | 35 | | `risks` | 26 |
| `requirements` | 50 | | `incidents` | 15 |
| `test_cases` | 82 | | `access_records` | 30 |
| `test_results` | 46 | | `change_actions` | 12 |
| `design_elements` | 50 | | `change_affects` | 28 |
| `gxp_systems` | 1 | | `changes` / `suppliers` / `supplier_assessments` / `access_reviews` / `periodic_evaluations` | 1 each |
| `action_proposals` | 4 | | | |

`design_elements`, `test_results`, and `supplier_assessments` previously had
**zero rows anywhere** in the seed. Populating them is most of the Blast Radius
gain.

## T6 verification — executed live

Docker stack was up (`gxp-sentinel-postgres-1`, `-opa-1`, `-qdrant-1` all
healthy) and the backend was serving on :8000, so every check below was actually
run, not inferred.

**Seed applies cleanly.** All four files applied via `psql -v ON_ERROR_STOP=1`
with exit 0 — no unknown column, no FK violation, no constraint error. Re-running
is a no-op (`ON CONFLICT DO NOTHING`), confirming idempotency.

**Referential integrity.**

- dangling `requirements.test_case_id` → **0**
- `requirements` with NULL `test_case_id` → **0**
- `change_affects` rows whose `entity_id` does not resolve → **0** across all
  four `entity_type`s used (DOCUMENT 9, DESIGN_ELEMENT 8, REQUIREMENT 8, RISK 3)
- every `entity_type` used is inside `CHANGE_AFFECTS_ENTITY_TYPES`
- every `*_ns` column is within a plausible nanosecond epoch range (no
  seconds/milliseconds magnitude errors) → **0** out-of-range across
  `risks`, `incidents`, `test_results`, `gxp_systems`

**Evidence Investigation** — `GET /api/systems/GXP-MES-NOVOLIFE-01/assurance-cards`
returns 4 cards, each citing a real NOVOLIFE record with a real C1 grade:

| Check | Evidence | Confidence | OPA corroborated |
|---|---|---|---|
| `verify_urs_approved` | `NL-MES-URS-001` | INSUFFICIENT_EVIDENCE | false |
| `verify_periodic_eval_current` | `DUMMY-ITPSE-MES-001` | HIGH | true |
| `verify_test_traceability` | `URS-MES-001` | MEDIUM | true |
| `verify_no_stale_documents` | `NL-MES-DRR-001` | INSUFFICIENT_EVIDENCE | false |

The two `INSUFFICIENT_EVIDENCE` results are **expected, not a seed defect**: both
checks generalize beyond what the closed Rego bundle expresses, a documented
asymmetry in `a2_compliance.py`'s own module docstring (routed to SENT-7-05).
C1 correctly refuses to corroborate them. This is the product thesis visibly
working, and is worth showing rather than hiding.

**Blast Radius** — evidence graph grew from **50 nodes / 45 edges**
(`GXP-MFG-DEMO-01`) to **352 nodes / 213 edges**. Traversal from
`CHANGE:DUMMY-CHG-MES-001` returns 40 direct + 9 indirect dependencies —
multi-hop confirmed — classified as 8 requirements, 8 tests, 3 risks, 12 changes,
1 system, `potential_gxp_impact: HIGH`, `highest_impact_downstream:
RISK:RSK-MES-011`.

**CAPA** — all 4 seeded proposals render via `GET /api/actions`, category
correctly derived as `GXP_RELEVANT_WRITE`, justifications quoting the source docs
directly (e.g. `NL-MES-ITPSE-001`'s "solution not in control, not validated, not
fit for operational use, and not released"). Three are `PENDING_APPROVAL`, one
pre-`APPROVED` so the approved state is demonstrable.

Critically, the seeded `finding_id` values were verified to be an **exact set
match** against the `finding_id`s the live A2 pipeline emits — so each seeded
CAPA binds to its real finding rather than floating unattached. `model_id` is
`'seeded'` on all four, so they can never be mistaken for LLM output. The live
"Generate CAPA" button still goes through A7 unchanged.

## Deviations from PLAN.md

1. **`status` value.** The plan said `'PENDING'`; the executor correctly used
   `'PENDING_APPROVAL'`, which is what `c3_gateway.py` writes and what
   `approve_action`/`reject_action` gate on. The plan was wrong; the code is right.
2. **`test_cases` count is 82, not 50.** The doc set contains both the
   `TC-MES-IQ-###` executed IQ set and a planned UAT set. Both were seeded.
3. **Deviations/defects mapped onto `incidents`.** As the plan directed — there is
   no dedicated table and inventing one would be scope expansion.
4. **`readiness_score` left at 0.** Per the plan, the app computes posture; no
   value was guessed.

## Known constraint (restated — do not "fix" this by accident)

**Evidence Investigation renders exactly four assurance cards, always.** One per
`A2_CHECKS` entry in `backend/app/agents/a2_compliance.py`. Seed volume changes
*what each card cites*, never *how many cards appear*. Adding a fifth check is
scope expansion under CLAUDE.md Rule 7 and was deliberately excluded. If more
cards are wanted, that is a separate, properly-contracted ticket.

## Not verified

The backend pytest suite was started against the worktree but had not finished at
the time of writing. The worktree has no `node_modules`, so the frontend Vitest
suite was not run there; the T5 edits are additive entries to `SYSTEM_OPTIONS` /
`KNOWLEDGE_SYSTEM_IDS`, and the existing frontend tests select systems by explicit
value with no length assertions, so the regression risk is low but unproven.

Work is on branch `worktree-agent-a5c8918176f34d723` and has not been merged to
`bugFix`.
