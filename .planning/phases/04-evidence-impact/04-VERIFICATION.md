---
phase: 04-evidence-impact
verified: 2026-08-23T02:00:00Z
status: human_needed
score: 4/4 roadmap truths verified (live, behavioral evidence); 4 human-verification items outstanding (visual browser confirmation, self-declared incomplete by every plan's own SUMMARY.md)
behavior_unverified: 0
overrides_applied: 0
human_verification:
  - test: "Open http://localhost:3000/blast-radius with GXP-MFG-DEMO-01 selected and the graph rebuilt. Confirm 14 nodes and 9 labelled edges render visibly on the React Flow canvas."
    expected: "Nodes and edges are visually present, readable, and match the API response (verified programmatically: 14 nodes, 9 edges)."
    why_human: "Visual rendering quality/layout cannot be confirmed by grep or unit test; jsdom component tests prove the DOM contains the right elements but not that a human sees a legible graph in a real browser. Plan 04-01's own <human-check> task was never executed by a human (self-declared in 04-01-SUMMARY.md D4)."
  - test: "Click the CHANGE:CR-2026-089 node on /blast-radius. Confirm the detail panel and impact summary (Direct 4, Indirect 2, Affected controls 0, Potential GxP impact HIGH) render correctly, and that clicking the SYSTEM node shows an explicit no-downstream-impact state."
    expected: "Click-through updates both panels with the exact values the live API confirmed (verified via curl in this session)."
    why_human: "Plan 04-05's own <human-check> task for this exact walkthrough was never executed by a human (self-declared in 04-05-SUMMARY.md D5 rationale)."
  - test: "Open http://localhost:3000/findings for GXP-MFG-DEMO-01. Confirm two Assurance Cards render with readable CLAIM/EVIDENCE/RULE/DETERMINISTIC CHECK/CONFIDENCE sections and visually distinct confidence badges, and that each card shows a working 'Blast Radius' link."
    expected: "Two MEDIUM-confidence cards render (verified via live API in this session), each linking to /blast-radius?node=... for its evidence."
    why_human: "Plan 04-03's and 04-05's own <human-check> tasks for this walkthrough were never executed by a human (self-declared in 04-03-SUMMARY.md D6 and 04-05-SUMMARY.md D4 rationale)."
  - test: "Pasting a deep link such as http://localhost:3000/blast-radius?node=CHANGE%3ACR-2026-089 loads the page with that node pre-selected, no click required."
    expected: "The page issues exactly one blast-radius request on mount and shows the node already selected."
    why_human: "Same self-declared gap as above — automated tests exercise this via jsdom/stubbed fetch, not a real browser navigation."
---

# Phase 4: Evidence & Impact Verification Report

**Phase Goal:** The NetworkX evidence graph builds from live Postgres state and Blast Radius traversal returns correct downstream-impacted nodes, both wired into the browser, and a verified finding renders as a real evidence card. (Build-Map Stage 3)

**Verified:** 2026-08-23
**Status:** human_needed
**Re-verification:** No — initial verification

## Goal Achievement

This verification did not trust SUMMARY.md claims. All four Roadmap Success Criteria were independently re-executed against the live system in this session: full backend test suite run from scratch (198 tests), full frontend test suite run from scratch (64 tests), a live `uvicorn` + Postgres instance was started, the evidence graph was rebuilt, and the Blast Radius and Assurance Card endpoints were hit directly with `curl` and their JSON compared byte-for-byte against the values claimed in the plans/summaries. All matched exactly.

### Observable Truths (Roadmap Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | The NetworkX evidence graph is constructed directly from live Postgres state, persisted per the architecture diagram | ✓ VERIFIED | Live `POST /api/systems/GXP-MFG-DEMO-01/evidence-graph/rebuild` (this session) returned `{"node_count":14,"edge_count":9}`, matching plan 04-02's target exactly. `grep -rn "call_llm\|llm_router" backend/app/graph/evidence_graph.py backend/app/routes/*.py` returns no matches — zero LLM in the graph path (Bible §1.3). `graph_nodes`/`graph_edges` are populated only by `persist_graph`, confirmed by reading `backend/app/graph/evidence_graph.py` in full. |
| 2 | Blast Radius traversal answers the graph questions from Section 14.3 correctly for a seeded change record, returning the correct set of downstream-impacted tests, controls, and systems | ✓ VERIFIED | Live `GET /api/systems/GXP-MFG-DEMO-01/blast-radius?node_id=CHANGE:CR-2026-089` (this session) returned `direct_dependencies` length 4, `indirect_dependencies` length 2, `affected_requirements: [REQUIREMENT:URS-042]`, `affected_tests: [TEST_CASE:TC-2026-042]`, `affected_controls: []`, `affected_systems: [SYSTEM:GXP-MFG-DEMO-01]`, `potential_gxp_impact: HIGH`, `highest_impact_downstream: REQUIREMENT:URS-042` — byte-identical to Bible §14.3's worked example prediction and to the plan's stated targets. `backend/tests/test_blast_radius.py` contains one named test per each of the nine Graph Questions plus cycle/self-loop/diamond/disconnected-component edge cases; all 198 backend tests (including this file) pass live in this session. |
| 3 | The evidence graph renders in-browser via React Flow from `/api/systems/{id}/evidence-graph`, and the Blast Radius UI visually displays the impact radius wired to that traversal | ✓ VERIFIED (code + jsdom rendering evidence); visual confirmation is a human-verification item | `frontend/src/pages/BlastRadius.tsx` calls `fetchEvidenceGraph`/`fetchBlastRadius` (confirmed by direct grep of source, not SUMMARY claims); `EvidenceGraphCanvas.tsx` passes real API data into `@xyflow/react`'s `<ReactFlow>` with `onNodeClick` wired to `handleNodeClick` → `fetchBlastRadius`. 64/64 frontend vitest tests pass live in this session, including jsdom-rendered assertions that clicking a node issues exactly one blast-radius request and updates `NodeDetailPanel`/`BlastRadiusPanel`. No LLM/mock/hardcoded data found in these components (`grep -rn "fetch(\|apiGet" BlastRadiusPanel.tsx NodeDetailPanel.tsx EvidenceGraphCanvas.tsx` returns no matches — they are presentation-only, reading only props). A real Chrome-rendered visual confirmation was attempted in this session but browser tooling was unavailable; every plan's own `<human-check>` step for this exact walkthrough was also never executed by a human, per each SUMMARY.md's self-declared rationale. |
| 4 | A verified finding renders as an Assurance Card showing CLAIM / EVIDENCE / RULE / DETERMINISTIC CHECK / CONFIDENCE, sourced entirely from server-trusted data, never LLM-generated UI | ✓ VERIFIED (code + jsdom rendering evidence); visual confirmation is a human-verification item | Live `GET /api/systems/GXP-MFG-DEMO-01/assurance-cards` (this session) returned exactly two cards (`verify_periodic_eval_current`, `verify_test_traceability`), both `confidence: MEDIUM`, with real evidence ids (`PE-2024-01`, `URS-042`), real rule ids (`ANNEX11-S11-PE-001`, `ANNEX11-S4-TRC-001`), and `deterministic_check.db_record_found`/`opa_corroborated` both `true` — matching plan 04-03's predicted values exactly. `AssuranceCard.tsx` is confirmed presentation-only (`grep` for fetch/apiGet returns no matches); confidence is read from C1's `verify_finding()` result, never the finding's `UNVERIFIED` placeholder (`backend/tests/test_routes_findings.py` asserts this negatively across both seeded systems). Visual confirmation (card layout, colour distinction) is a self-declared open item in 04-03-SUMMARY.md and 04-05-SUMMARY.md. |

**Score:** 4/4 roadmap truths independently re-verified with live, behavioral evidence (not SUMMARY-claim trust). 0 failed. 4 outstanding items are self-declared, plan-mandated `<human-check>` visual walkthroughs that were never executed by a human in any of the five plans — see Human Verification Required below.

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/app/graph/evidence_graph.py` | build_graph/persist_graph/load_graph, NODE_SPECS (15 types), EDGE_SPECS, blast_radius(), assess_gxp_impact, rank_highest_impact | ✓ VERIFIED | Exists, imported and exercised by 198/198 passing backend tests; zero LLM calls (grep confirmed) |
| `backend/app/routes/evidence_graph.py` | rebuild/read/blast-radius endpoints | ✓ VERIFIED | Registered in `app/main.py` via `include_router`; live-hit in this session, returned correct data |
| `backend/app/routes/findings.py` | GET assurance-cards endpoint | ✓ VERIFIED | Registered in `app/main.py`; live-hit in this session, returned correct data |
| `infra/postgres/initdb/002_change_affects.sql` | change_affects table | ✓ VERIFIED | `bash infra/verify-schema.sh` passes: 28 tables, `change_affects` present |
| `infra/postgres/seed/003_change_affects_fixture.sql` | DE-2026-DB-01 + 3 change_affects rows | ✓ VERIFIED | `bash infra/verify-seed.sh` passes: `SEED OK`, all Phase-4 fixture assertions green |
| `frontend/src/components/EvidenceGraphCanvas.tsx` | React Flow rendering, click-through | ✓ VERIFIED | Presentational, wired via props; grep confirms no fetch |
| `frontend/src/components/AssuranceCard.tsx` | 5-section card | ✓ VERIFIED | Presentational; renders exactly the fields tested |
| `frontend/src/components/BlastRadiusPanel.tsx` | 4-line impact summary | ✓ VERIFIED | Presentational; renders server-supplied array lengths only, grep confirms no reachability computation |
| `frontend/src/components/NodeDetailPanel.tsx` | node detail rendering | ✓ VERIFIED | Presentational |
| `frontend/src/pages/BlastRadius.tsx`, `FindingInvestigation.tsx` | routes wired to fetch + render | ✓ VERIFIED | Both confirmed via grep to call the real fetch functions; routes registered in `routes.tsx` |

### Key Link Verification

| From | To | Via | Status | Details |
|------|-----|-----|--------|---------|
| `requirements.test_case_id` (Postgres) | `VERIFIED_BY` edge in graph | `build_graph` FK read | ✓ WIRED | Live rebuild confirmed edge present |
| `change_affects` row | `AFFECTS` edge | `_add_change_affects_edges` | ✓ WIRED | Live blast-radius response shows 3 AFFECTS edges from CR-2026-089's change_affects rows plus 1 HAS_ACTION |
| `graph_edges` cache | `blast_radius()` traversal | `load_graph` → `nx.descendants` | ✓ WIRED | Live endpoint response matches test-asserted values exactly |
| React Flow `onNodeClick` | `fetchBlastRadius` | `BlastRadius.tsx` handler | ✓ WIRED | Confirmed by grep of source; jsdom test asserts exactly one request per click |
| `AssuranceCard.evidence_ids` | `/blast-radius?node=` link | `entity_id → node_id` lookup in `FindingInvestigation.tsx` | ✓ WIRED | Confirmed by grep of source; live API confirms `PE-2024-01`/`URS-042` resolve to real graph nodes |
| `app.routes.evidence_graph` / `app.routes.findings` routers | `app.main:app` | `include_router` | ✓ WIRED | Confirmed by reading `backend/app/main.py` in full |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|---------------------|--------|
| `EvidenceGraphCanvas` | nodes/edges | `fetchEvidenceGraph` → live Postgres via `graph_nodes`/`graph_edges` | Yes (live-confirmed: 14 nodes, 9 edges) | ✓ FLOWING |
| `BlastRadiusPanel` | direct/indirect counts, impact | `fetchBlastRadius` → `blast_radius()` over `load_graph` | Yes (live-confirmed exact Bible §14.3 answer) | ✓ FLOWING |
| `AssuranceCard` | confidence, evidence, rule | `fetchAssuranceCards` → C1 `verify_finding()` against real DB+OPA | Yes (live-confirmed MEDIUM/MEDIUM, real evidence ids) | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| Full backend suite | `cd backend && .venv/Scripts/python -m pytest -q` | 198 passed, 0 failed (73.8s) | ✓ PASS |
| Full frontend suite | `cd frontend && npm run test` | 64 passed, 0 failed (5 files) | ✓ PASS |
| Evidence graph rebuild (live) | `curl -X POST .../evidence-graph/rebuild` | `{"node_count":14,"edge_count":9}` | ✓ PASS |
| Blast Radius (live) | `curl .../blast-radius?node_id=CHANGE:CR-2026-089` | Exact Bible §14.3 answer (4 direct, 2 indirect, HIGH, REQUIREMENT:URS-042) | ✓ PASS |
| Assurance Cards (live) | `curl .../assurance-cards` | Exactly 2 cards, both MEDIUM, real evidence/rule ids | ✓ PASS |
| Zero LLM in graph path | `grep -rn "call_llm\|llm_router" backend/app/graph/evidence_graph.py backend/app/routes/evidence_graph.py backend/app/routes/findings.py` | No matches | ✓ PASS |
| Schema/seed gates | `bash infra/verify-schema.sh && bash infra/verify-seed.sh` | `SCHEMA OK` (28 tables, 22 FKs), `SEED OK` (all Phase-4 fixtures) | ✓ PASS |
| Real browser click-through (blast-radius, findings) | N/A — browser automation unavailable in this verification session | Not executed | ? SKIP → routed to human verification |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|--------------|--------|----------|
| GRAPH-01 | 04-01, 04-02 | NetworkX evidence graph built from live Postgres | ✓ SATISFIED | Live rebuild + full test suite |
| GRAPH-02 | 04-04, 04-05 | Blast Radius returns correct downstream nodes | ✓ SATISFIED | Live traversal matches Bible §14.3 exactly |
| GRAPH-03 | 04-01, 04-05 | Evidence graph renders in-browser via React Flow | ✓ SATISFIED (code); visual confirmation outstanding | Component/page tests pass; no human browser confirmation done |
| EVID-03 | 04-03 | Verified finding renders as Assurance Card | ✓ SATISFIED (code); visual confirmation outstanding | Live API + component tests pass; no human browser confirmation done |

**Note (process hygiene, not a functional gap):** `.planning/REQUIREMENTS.md` still lists all four requirements as unchecked `- [ ]` with coverage-table status `Pending` (lines 32, 37-39, 133-136), and `.planning/STATE.md` frontmatter still shows `current_phase: 04`, `status: executing`, `completed_plans: 18` (not 23) and a `last_updated` timestamp of 2026-08-21 — a day before the phase's own commits (dated 2026-08-22/23 per `git log`). This is stale tracking-document bookkeeping that the phase-completion step evidently never ran; it does not reflect the actual (verified, working) state of the code. Flagged as a WARNING for the human to close out (update REQUIREMENTS.md and STATE.md), not a BLOCKER — the underlying functionality is real and verified.

### Anti-Patterns Found

None. `grep` for `TBD|FIXME|XXX|TODO|HACK|PLACEHOLDER|not yet implemented|coming soon` across all Phase 4 backend and frontend files modified in this phase returned no matches. No hardcoded empty-data stubs found in the rendering path — every component confirmed to read only from props/fetched state.

### Human Verification Required

Every plan in this phase (04-01, 04-03, 04-05) included its own mandatory `<human-check>` verification step asking a human to visually confirm the rendered UI in a real browser. Every one of the five SUMMARY.md files self-declares this step was **not** performed — only scripted `curl`/`fetch` checks and jsdom-rendered component tests were run instead. This verification session attempted to close that gap using browser automation tooling, but it was unavailable in this environment. The underlying data and wiring are proven correct (see Behavioral Spot-Checks and Key Link Verification above); what remains unconfirmed is purely the human-perceptible rendering quality.

### 1. Evidence graph renders visibly on `/blast-radius`

**Test:** Start backend + frontend, `POST` the rebuild endpoint for `GXP-MFG-DEMO-01`, open `http://localhost:3000/blast-radius` in a browser.
**Expected:** 14 nodes and 9 labelled edges are visible and legible on the React Flow canvas; switching the system selector to `BUS-IT-DEMO-02` shows the empty-state message.
**Why human:** Visual layout/legibility cannot be confirmed by grep or a jsdom unit test.

### 2. Node click-through and impact summary render correctly

**Test:** Click the `CHANGE:CR-2026-089` node on `/blast-radius`.
**Expected:** Detail panel shows the change's description/status; impact summary reads Direct 4, Indirect 2, Affected controls 0, Potential GxP impact HIGH; clicking the `SYSTEM` node shows an explicit no-downstream-impact message.
**Why human:** Same class of gap — the values are proven correct via API and jsdom tests, but a human has not confirmed the rendered page.

### 3. Assurance Cards render correctly on `/findings`

**Test:** Open `http://localhost:3000/findings` for `GXP-MFG-DEMO-01`.
**Expected:** Two cards render with all five EVID-03 sections plus ALCOA+ grid and model attribution; a Blast Radius link is present on each card and navigates correctly.
**Why human:** Same class of gap.

### 4. Deep link pre-selection works in a real browser

**Test:** Paste `http://localhost:3000/blast-radius?node=CHANGE%3ACR-2026-089` directly into the address bar.
**Expected:** The page loads with that node already selected and its impact summary displayed, no click required.
**Why human:** Automated tests exercise this via a stubbed router/fetch, not real browser navigation.

### Gaps Summary

No functional gaps were found. All four Roadmap Success Criteria for Phase 4 are backed by live, independently-reproduced evidence in this session (not SUMMARY.md trust): the evidence graph is real and derived entirely from live Postgres state with zero LLM involvement; Blast Radius correctly answers all nine Bible §14.3 Graph Questions for the seeded `CR-2026-089` change record, matching the Bible's own worked example; both are wired into real, non-stub frontend code with genuine fetch calls and no hardcoded data; and the Assurance Card surfaces exactly the fields EVID-03 requires, sourced from C1's real verification result. 198/198 backend tests and 64/64 frontend tests pass live.

The only open item is a human-perceptible visual confirmation that every one of the five plans itself scheduled as a mandatory `<human-check>` step and that none of them actually executed — this is not a code defect, it is an outstanding manual QA step the phase's own plans require before being considered fully closed. A secondary, non-blocking item is that `.planning/REQUIREMENTS.md` and `.planning/STATE.md` were never updated to reflect the phase's actual (verified-complete) status.

---

_Verified: 2026-08-23_
_Verifier: Claude (gsd-verifier)_
