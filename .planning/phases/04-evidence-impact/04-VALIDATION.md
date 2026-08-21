---
phase: 04
slug: evidence-impact
status: planned
nyquist_compliant: true
wave_0_complete: false
created: 2026-08-21
updated: 2026-08-21
---

# Phase 04 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (backend/tests, config: backend/pytest.ini) |
| **Config file** | backend/pytest.ini |
| **Quick run command** | `cd backend && pytest tests/ -k "graph or blast_radius or evidence" -q` |
| **Full suite command** | `cd backend && pytest -q` |
| **Estimated runtime** | ~30-60 seconds |

---

## Sampling Rate

- **After every task commit:** Run the quick run command
- **After every plan wave:** Run the full suite command
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

Authored 2026-08-21. The per-task `<verify>` blocks in each PLAN.md are authoritative; this table is the phase-level index.

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| Checkpoint | 04-01 | 1 | — | T-04-SC | `networkx` legitimacy verified by a human before install (`blocking-human`) | manual gate | n/a | n/a | ⬜ pending |
| 04-01 T1 | 04-01 | 1 | GRAPH-01 | T-04-01, T-04-02, T-04-04, T-04-06 | `$1` placeholders only; frozen table/relation allowlists; property-column allowlist | unit + negative + edge + integration | `cd backend && .venv/Scripts/python -m pytest tests/test_evidence_graph.py tests/test_routes_evidence_graph.py -q` | ❌ created by task | ⬜ pending |
| 04-01 T2 | 04-01 | 1 | GRAPH-03 | — | Canvas is presentational; no fetch, no traversal in the browser | component render | `cd frontend && npm run test` | ❌ created by task | ⬜ pending |
| Checkpoint | 04-02 | 2 | — | — | One-way `change_affects` shape confirmed by a human (`blocking-human`) | manual gate | n/a | n/a | ⬜ pending |
| 04-02 T1 | 04-02 | 2 | GRAPH-01 | T-04-07 | Additive migration; `001_schema.sql` untouched; schema/seed gates updated in the same commit | infra gate | `bash infra/apply-migrations.sh && bash infra/apply-seed.sh && bash infra/verify-schema.sh && bash infra/verify-seed.sh` | ✅ scripts exist | ⬜ pending |
| 04-02 T2 | 04-02 | 2 | GRAPH-01 | T-04-01, T-04-02, T-04-04 | `entity_type` validated against a frozen allowlist, never concatenated into SQL | unit + negative + edge + integration (Critical) | `cd backend && .venv/Scripts/python -m pytest tests/test_evidence_graph.py -q` | ✅ after 04-01 | ⬜ pending |
| 04-03 T1 | 04-03 | 2 | EVID-03 | T-04-01, T-04-08 | Confidence read from C1's verification result, never the finding placeholder | integration + negative + edge | `cd backend && .venv/Scripts/python -m pytest tests/test_routes_findings.py -q` | ❌ created by task | ⬜ pending |
| 04-03 T2 | 04-03 | 2 | EVID-03 | T-04-09, T-04-10 | Card renders only prop fields; no client-side defaulting or grading | component render | `cd frontend && npm run test` | ❌ created by task | ⬜ pending |
| 04-04 T1 | 04-04 | 3 | GRAPH-02 | T-04-06 | Pure NetworkX reachability; deterministic total-ordered ranking | unit + integration | `cd backend && .venv/Scripts/python -m pytest tests/test_blast_radius.py -q` | ❌ created by task | ⬜ pending |
| 04-04 T2 | 04-04 | 3 | GRAPH-02 | — | Cycle, self-loop, diamond, disconnected-component and absent-node behavior proven | negative + edge (Critical) | `cd backend && .venv/Scripts/python -m pytest tests/test_blast_radius.py -q` | ✅ after 04-04 T1 | ⬜ pending |
| 04-04 T3 | 04-04 | 3 | GRAPH-02 | T-04-01, T-04-11 | Unknown node returns 404 not 500; `node_id` never reaches SQL | route integration | `cd backend && .venv/Scripts/python -m pytest tests/test_routes_evidence_graph.py tests/test_blast_radius.py -q` | ✅ after 04-01 | ⬜ pending |
| 04-05 T1 | 04-05 | 4 | GRAPH-02, GRAPH-03 | T-04-09, T-04-01 | Panel renders server-supplied array lengths only; no browser traversal | component + page render | `cd frontend && npm run test` | ❌ created by task | ⬜ pending |
| 04-05 T2 | 04-05 | 4 | GRAPH-02 | T-04-10 | Link built from server-supplied `entity_id`→`node_id` mapping; card component untouched | page render | `cd frontend && npm run test` | ✅ after 04-03 | ⬜ pending |

---

## Wave 0 Requirements

Every gap below is closed by the plan/task named beside it — each test file is created
by the same task whose `<verify><automated>` command runs it, so no task ships with a
`MISSING` automated verify.

- [ ] `backend/tests/test_evidence_graph.py` — GRAPH-01 → created by **04-01 Task 1**, expanded to the Critical bar by **04-02 Task 2**
- [ ] `backend/tests/test_routes_evidence_graph.py` — GRAPH-03 backend half → created by **04-01 Task 1**, extended by **04-02 Task 2** and **04-04 Task 3**
- [ ] `backend/tests/test_blast_radius.py` — GRAPH-02 → created by **04-04 Task 1**, brought to the Critical bar by **04-04 Task 2**
- [ ] `backend/tests/test_routes_findings.py` — EVID-03 backend half → created by **04-03 Task 1**
- [ ] `frontend/src/__tests__/EvidenceGraph.test.tsx` — GRAPH-03 frontend half → created by **04-01 Task 2**, extended by **04-05 Task 1**
- [ ] `frontend/src/__tests__/AssuranceCard.test.tsx` — EVID-03 frontend half → created by **04-03 Task 2**, extended by **04-05 Task 2**
- [ ] `frontend/src/__tests__/BlastRadiusPanel.test.tsx` — GRAPH-02 frontend half → created by **04-05 Task 1**
- [ ] `infra/postgres/seed/003_change_affects_fixture.sql` — fixture prerequisite for every GRAPH-02 assertion → created by **04-02 Task 1**
- [ ] `networkx==3.6.1` — absent from `backend/requirements.txt`; installed by **04-01 Task 1**, gated by the `blocking-human` legitimacy checkpoint that precedes it (flagged `[SUS]` for unknown-downloads stats only — assessed a false positive in 04-RESEARCH.md, but the checkpoint is mandatory per protocol)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Evidence graph renders correctly in-browser via React Flow | EVID-03 | Visual layout/rendering correctness is not meaningfully assertable by automated test | Open the system detail page, confirm nodes/edges render for a system with seeded evidence, and Blast Radius highlighting appears when a change record is inspected |
| Assurance Card visual layout (CLAIM/EVIDENCE/RULE/DETERMINISTIC CHECK/CONFIDENCE) | EVID-03 | UI rendering fidelity to server-trusted fields is visually verified | Trigger a verified finding via the copilot flow and confirm the card displays all five fields sourced from `verification_results` |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies — 12 of 12 non-checkpoint tasks carry `<verify><automated>`
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references — every test file is created by the task whose verify command runs it
- [x] No watch-mode flags — `npm run test` is `vitest run`, `pytest -q` is single-shot
- [x] Feedback latency < 60s — module-scoped `-k`/path-filtered pytest runs and a single vitest pass
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** planner-signed 2026-08-21 (plans 04-01 through 04-05)
