---
phase: 04
slug: evidence-impact
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-08-21
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

*Filled in by the planner as tasks are authored — see PLAN.md `must_haves` and per-task `<verify>` blocks for the authoritative mapping.*

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| TBD | TBD | TBD | GRAPH-01/02/03, EVID-03 | — | N/A | unit/integration | TBD | TBD | ⬜ pending |

---

## Wave 0 Requirements

- [ ] `backend/tests/test_evidence_graph.py` — stubs for GRAPH-01 (graph construction from Postgres)
- [ ] `backend/tests/test_blast_radius.py` — stubs for GRAPH-02/GRAPH-03 (blast radius traversal)
- [ ] `networkx==3.6.1` — not currently in backend/requirements.txt; must be installed as part of Wave 0 (flagged `[SUS]` by legitimacy gate due to unknown-downloads stats only — assessed false positive in 04-RESEARCH.md, but add a `checkpoint:human-verify` task before the `pip install networkx==3.6.1` step per protocol)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Evidence graph renders correctly in-browser via React Flow | EVID-03 | Visual layout/rendering correctness is not meaningfully assertable by automated test | Open the system detail page, confirm nodes/edges render for a system with seeded evidence, and Blast Radius highlighting appears when a change record is inspected |
| Assurance Card visual layout (CLAIM/EVIDENCE/RULE/DETERMINISTIC CHECK/CONFIDENCE) | EVID-03 | UI rendering fidelity to server-trusted fields is visually verified | Trigger a verified finding via the copilot flow and confirm the card displays all five fields sourced from `verification_results` |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
