# Roadmap: GxP Sentinel

## Overview

GxP Sentinel proves one thesis end to end: AI can investigate a GxP system, but no AI claim is ever trusted until it's independently, deterministically verified against real database state and real OPA policy evaluation. This roadmap maps 1:1 onto `Sentinel-Build-Map.md`'s Stage 0–7 ticket breakdown (superseding an earlier independently-derived 6-phase vertical-MVP roadmap — see PROJECT.md Key Decisions). Each GSD phase below corresponds exactly to one Build-Map stage, in the same order, carrying that stage's own Gate forward as the phase's primary success criterion, expanded with the observable outcomes each stage's ticket contracts promise. This is a horizontal, layered build order rather than a vertical-slice one: Phase 1 stands up the environment; Phase 2 lays the full schema/policy/API/frontend-shell foundation; Phase 3 wires the real agents and C1 verification (the hero loop, backend-only); Phase 4 adds the evidence graph, Blast Radius, and the verified-finding card UI; Phase 5 adds RBAC, injection detection, controlled remediation, and the hash-chained audit trail; Phase 6 assembles the Command Centre and Ask GxP Copilot product experience — the point at which the full Monitor→Investigate→Trust→Remediate→Audit loop first becomes walkable end to end without a developer narrating gaps; Phase 7 hardens the system adversarially; Phase 8 freezes for submission. Every v1 requirement still maps to exactly one phase; ticket-level detail from stages that also carry v2-territory work (e.g. Stage 2's A1/A3–A6 agents, Stage 3's ALCOA+ extension, Stage 5's Trust Centre/Supplier Intelligence/Assurance Lab) is retained as phase context without inventing new v1 requirements.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Environment** - `docker-compose up -d postgres qdrant opa` succeeds; all three health checks green
- [ ] **Phase 2: Foundation** - Schema loads, seed data present, one Rego rule evaluates via raw OPA REST call, API skeleton returns 200 on `/api/health`
- [ ] **Phase 3: Intelligence & Retrieval** - A real query enters A0, fans out to real (non-stub) A1–A6, C1 produces a non-trivial confidence score sourced from real DB + OPA state
- [ ] **Phase 4: Evidence & Impact** - NetworkX graph builds from live Postgres state; Blast Radius returns correct downstream nodes for a seeded change record
- [ ] **Phase 5: Safety & Remediation** - A prompt-injection payload is blocked deterministically by C2; a proposed write sits PENDING until approved; a tampered audit row is detected by `verify_chain()`
- [ ] **Phase 6: Product Experience** - The full Monitor → Investigate → Trust → Remediate → Audit loop is walkable without a developer narrating gaps
- [ ] **Phase 7: Integration & Hardening** - Nothing in the demo path breaks under adversarial input; demo-state reset is one command
- [ ] **Phase 8: Freeze** - No new features; bug-fix pass, rehearsal, and submission packaging only

## Phase Details

### Phase 1: Environment
**Goal**: The environment stands up from one command — Docker Compose brings Postgres, Qdrant, and OPA up healthy, on a repo structure ready for Stage 1 work. (Build-Map Stage 0, Gate: "`docker-compose up -d postgres qdrant opa` succeeds; all three health checks green.")
**Mode:** mvp
**Depends on**: Nothing (first phase)
**Requirements**: ENV-01
**Ticket context (Build-Map Stage 0)**: SENT-0-01 (repo scaffold + branching convention), SENT-0-02 (Docker Compose: postgres/qdrant/opa)
**Success Criteria** (what must be TRUE):
  1. Running `docker-compose up -d postgres qdrant opa` is the only setup step, and it brings all three services up healthy on ports 5432/6333/8181.
  2. The repo has a documented structure and a worktree/branching convention in place, satisfying Rule 10 (no two agents editing the same critical file) before any Stage 1 ticket starts.
**Plans**: 4 plans in 3 waves

Plans:
- [ ] 01-01-PLAN.md — Tracer: one-command bring-up proven end-to-end with Postgres, plus the mechanical ENV-01 health gate (wave 1)
- [ ] 01-02-PLAN.md — Repo scaffold (D-01 four tiers), root README, and BRANCHING.md Rule 10 file-ownership allocation — SENT-0-01 (wave 1)
- [ ] 01-03-PLAN.md — Qdrant on a curl-capable derived image and OPA on the debug tag, both healthy with real HTTP probes — SENT-0-02 (wave 2)
- [ ] 01-04-PLAN.md — Named-volume persistence proof (D-05) and cold-start gate from destroyed volumes, plus infra/README.md (wave 3)

### Phase 2: Foundation
**Goal**: The full schema, seed data, policy layer, API skeleton, orchestration skeleton, frontend shell, and WebSocket pattern are all in place, giving Phase 3's real agents a real substrate to build on. (Build-Map Stage 1, Gate: "schema loads, seed data present, one Rego rule evaluates via raw OPA REST call, API skeleton returns 200 on `/api/health`.")
**Mode:** mvp
**Depends on**: Phase 1 (all Stage 1 tickets depend on Stage 0 being closed)
**Requirements**: ENV-02, ENV-03, ENV-04, POL-01, POL-02, ORC-01, UI-01
**Ticket context (Build-Map Stage 1)**: SENT-1-01 (Postgres DDL), SENT-1-02 (seed data), SENT-1-03 (all 10 Rego rules, Critical review), SENT-1-04 (OPA sidecar wiring, depends on SENT-1-03), SENT-1-05 (FastAPI skeleton + Pydantic schemas), SENT-1-06 (LangGraph `StateGraph` skeleton, depends on SENT-1-05), SENT-1-07 (React/Vite/Tailwind shell), SENT-1-08 (WebSocket connection pattern), SENT-1-09 (CI test runner)
**Success Criteria** (what must be TRUE):
  1. All tables from Bible Section 4.1 (`gxp_systems`, `documents`, `document_chunks`, `requirements`, `risks`, `design_elements`, `test_cases`, `test_results`, `incidents`, `access_reviews`, `access_records`, `suppliers`, `audit_events`, `action_proposals`) exist with FK constraints verified, and `GXP-MFG-DEMO-01` + `BUS-IT-DEMO-02` are fully seeded, including the deliberately-injected `DataSync Solutions` overdue-supplier finding.
  2. All 10 Rego rules from Section 3.3 are implemented and pass `opa test` against positive and negative fixtures, independent of the app; `evaluate_opa_policy()` calls the real OPA REST endpoint, and a `python_fallback_rules()` stub exists for when OPA is unreachable.
  3. FastAPI boots with all Section 4.3 Pydantic schemas (`AgentFinding`, `ActionProposal`, `AgentState`) typed and importable, and `/api/health` returns 200.
  4. The LangGraph `StateGraph` compiles with stub node returns (empty findings acceptable at this stage), its edges matching the `C2 → A0 → [A1…A6 via Send] → C1 → A7 → C3` topology exactly.
  5. The React/Vite/Tailwind app boots with routing scaffolded for all 7 pages and a React Flow canvas mounted with placeholder nodes, and `/api/copilot/stream/{session_id}` accepts a WebSocket connection and echoes a test event end-to-end (backend → browser).
**Plans**: 8 plans in 3 waves

Plans:
- [ ] 02-01-PLAN.md — Postgres DDL (27 tables, 21 FKs) + Section 5 seed data with the 10 injected gaps — SENT-1-01, SENT-1-02 (wave 1)
- [ ] 02-02-PLAN.md — All 10 Rego rules in Rego v1 syntax + `opa test` fixtures, Critical review — SENT-1-03 (wave 1)
- [ ] 02-03-PLAN.md — FastAPI skeleton, Section 4.3 Pydantic schemas, `/api/health`, pytest harness — SENT-1-05 (wave 1)
- [ ] 02-04-PLAN.md — React/Vite/Tailwind v4 shell, 8 Section 11 routes, React Flow v12 canvas — SENT-1-07 (wave 1)
- [ ] 02-05-PLAN.md — `evaluate_opa_policy()` against the live sidecar + `python_fallback_rules()` stub — SENT-1-04 (wave 2)
- [ ] 02-06-PLAN.md — LangGraph `StateGraph` skeleton with structural topology assertions — SENT-1-06 (wave 2)
- [ ] 02-07-PLAN.md — `/api/copilot/stream/{session_id}` WebSocket route + browser client — SENT-1-08 (wave 2)
- [ ] 02-08-PLAN.md — GitHub Actions CI running every schema, seed, Rego, backend, and frontend gate — SENT-1-09 (wave 3)
**UI hint**: yes

### Phase 3: Intelligence & Retrieval
**Goal**: A real query enters A0, is classified and routed, fans out to real (non-stub) agents, and C1 produces a non-trivial confidence score sourced from real DB + OPA state — the backend hero loop is real, not mocked. (Build-Map Stage 2, Gate: "a real query enters A0, fans out to real (non-stub) A1–A6, C1 produces a non-trivial confidence score sourced from real DB + OPA state.")
**Mode:** mvp
**Depends on**: Phase 2 (SENT-2-01 depends on SENT-1-06; SENT-2-02–07 depend on SENT-2-01 + SENT-1-05)
**Requirements**: ORC-02, ORC-03, EVID-01, EVID-02, EVID-04
**Ticket context (Build-Map Stage 2 — v1-required tickets plus v2-territory tickets retained as context, not new v1 requirements)**: SENT-2-01 (A0 Orchestrator), SENT-2-02 (A2 Compliance agent — highest demo visibility), SENT-2-12 (C1 real wiring, Critical review, depends on SENT-2-02–07 and SENT-1-03/04); v2-territory in this same stage: SENT-2-03 (A1 System Knowledge/RAG), SENT-2-04 (A3 Risk), SENT-2-05 (A4 Change), SENT-2-06 (A5 Incident), SENT-2-07 (A6 Access), SENT-2-08/09/10/11 (Qdrant ingestion, hybrid retrieval, fusion/reranking, parent-context retrieval)
**Success Criteria** (what must be TRUE):
  1. A0 Orchestrator classifies intent via Gemini 2.5 Flash and fans out via `Send` to a subset of A1–A6; forcing a 2000ms+ delay demonstrably falls back to the full `["A1".."A6"]` set (tested explicitly).
  2. A2 Compliance Agent produces a real `AgentFinding` from live DB state via `verify_urs_approved` / `verify_periodic_eval_current` / `verify_test_traceability`, matching the Section 2 schema.
  3. C1 Evidence & Grounding Verifier fans in and calls `calculate_confidence()` against the real DB record and real OPA evaluation (never a mock), returning VERIFIED with a confidence score for a true claim.
  4. Feeding C1 a claim that contradicts DB/OPA truth demonstrably returns `INSUFFICIENT_EVIDENCE` (contradiction case explicitly tested).
  5. The backend hero loop runs end to end: submitting "Is GXP-MFG-DEMO-01 audit ready?" drives A0 → A2 → C1 and produces a verified finding sourced entirely from real DB/OPA state.
**Plans**: TBD

### Phase 4: Evidence & Impact
**Goal**: The NetworkX evidence graph builds from live Postgres state and Blast Radius traversal returns correct downstream-impacted nodes, both wired into the browser, and a verified finding renders as a real evidence card. (Build-Map Stage 3, Gate: "NetworkX graph builds from live Postgres state; Blast Radius returns correct downstream nodes for a seeded change record.")
**Mode:** mvp
**Depends on**: Phase 3 (all of Stage 3 depends on Stage 2 — real agents + C1 — being closed, since Blast Radius and Evidence Graph consume A1–A6 findings)
**Requirements**: EVID-03, GRAPH-01, GRAPH-02, GRAPH-03
**Ticket context (Build-Map Stage 3 — v1-required tickets plus v2-territory tickets retained as context, not new v1 requirements)**: SENT-3-01 (Evidence Graph construction, Critical), SENT-3-02 (React Flow evidence graph visualization), SENT-3-03 (Blast Radius traversal, Critical), SENT-3-04 (Blast Radius UI), SENT-3-05 (Assurance Cards); v2-territory in this same stage: SENT-3-06 (Deterministic Verification Centre), SENT-3-07 (FSM engine + visualization), SENT-3-08 (ALCOA+ extended verification, Critical — extends C1, explicitly no new subsystem)
**Success Criteria** (what must be TRUE):
  1. The NetworkX evidence graph is constructed directly from live Postgres state (Section 10.1), persisted per the architecture diagram.
  2. Blast Radius traversal answers the graph questions from Section 14.3 correctly for a seeded change record, returning the correct set of downstream-impacted tests, controls, and systems.
  3. The evidence graph renders in-browser via React Flow from the `/api/systems/{id}/evidence-graph` endpoint, and the Blast Radius UI visually displays the impact radius wired to that traversal.
  4. A verified finding renders as an Assurance Card showing CLAIM / EVIDENCE / RULE / DETERMINISTIC CHECK / CONFIDENCE, sourced entirely from server-trusted data, never LLM-generated UI.
**Plans**: TBD
**UI hint**: yes

### Phase 5: Safety & Remediation
**Goal**: Every request is deterministically gated by RBAC and injection detection before it reaches an agent; a proposed GxP-relevant write sits PENDING until a human approves it and the approval is audit-logged; and a tampered audit row is detected by `verify_chain()` — zero LLM in any of the three decision paths. (Build-Map Stage 4, Gate: "a prompt-injection payload is blocked deterministically by C2 (never by an LLM judgment call); a proposed write sits in `PENDING` until approved; a tampered audit row is detected by `verify_chain()`.")
**Mode:** mvp
**Depends on**: Phase 3 (SENT-4-03/04/05 depend on SENT-2-12, C1) and Phase 2 (SENT-4-03/04/05 also depend on SENT-1-06, graph/topology)
**Requirements**: SAFE-01, SAFE-02, AUDIT-01, AUDIT-02, AUDIT-03, REM-01, REM-02, REM-03, REM-04, UI-02
**Ticket context (Build-Map Stage 4)**: SENT-4-01 (C2 RBAC permission matrix, Critical), SENT-4-02 (C2 prompt-injection detection, Critical), SENT-4-03 (C3 Action Gateway category routing, Critical), SENT-4-04 (human approval queue + WebSocket push), SENT-4-05 (A7 Remediation agent + CAPA generation), SENT-4-06 (hash-chained audit trail, Critical), SENT-4-07 (tamper-detection test + demo endpoint, Critical, depends on SENT-4-06), SENT-4-08 (Action / Approval Centre UI)
**Success Criteria** (what must be TRUE):
  1. C2 enforces the RBAC permission matrix (IT System Manager / QA-Compliance / Auditor) exactly per the Bible's permission matrix, with zero LLM in the decision path.
  2. C2 detects and blocks known jailbreak/injection phrases from the Bible via entropy + regex, deterministically, with zero LLM in the decision path.
  3. C3 Action Gateway routes a proposed action to its correct category (READ / DRAFT / MOCK_WRITE_LOW_RISK / GXP_RELEVANT_WRITE / PROHIBITED); a GxP-relevant write sits `PENDING` in `action_proposals` until a human approves it, and the approval dialog in the Action/Approval Centre UI renders only from server-trusted `ActionProposal` metadata, never LLM-generated UI.
  4. A7 Remediation Agent synthesizes an `ActionProposal`/CAPA narrative only from already-verified (C1-passed) findings, never an unverified claim; the `/api/copilot/stream/{session_id}` WebSocket pushes the pending proposal live, and a human approving it is audit-logged and the action executes end to end.
  5. Finding/verification/approval events are recorded as they occur in a hash-chained, append-only audit trail with `verify_chain()` implemented alongside the chain (not bolted on after); hitting `/api/audit/demonstrate-tamper` executes a raw SQL modification against an audit row, and `verify_chain()` correctly flags the chain as tampered.
**Plans**: TBD
**UI hint**: yes

### Phase 6: Product Experience
**Goal**: A user lands on a Command Centre dashboard showing real system health at a glance, converses with the Ask GxP Copilot while watching the live agent investigation happen, and can walk the full Monitor→Investigate→Trust→Remediate→Audit loop unaided. (Build-Map Stage 5, Gate: "the full Monitor → Investigate → Trust → Remediate → Audit loop is walkable without a developer narrating gaps.")
**Mode:** mvp
**Depends on**: Phase 5 (SENT-5-01/08, the two P0 tickets, depend on all of Stage 4 being closed); Phases 3–4 for the backend pieces the remaining Stage 5 pages consume (SENT-5-02–07 parallelize once Stage 2–4 are closed)
**Requirements**: UI-03, UI-04
**Ticket context (Build-Map Stage 5 — v1-required P0 tickets plus v2-territory P1 tickets retained as context, not new v1 requirements)**: SENT-5-01 (Command Centre dashboard, P0), SENT-5-08 (Guided Tour 8-step, P0 — doubles as demo scaffolding); v2-territory in this same stage: SENT-5-02 (Ask GxP Copilot chat + live topology), SENT-5-03 (Audit Readiness gap dashboard), SENT-5-04 (Supplier Intelligence view), SENT-5-05 (Assurance Lab, 7 scenarios), SENT-5-06 (Trust Centre), SENT-5-07 (Inspection Readiness Simulator), SENT-5-09 (Evidence Pack PDF export)
**Success Criteria** (what must be TRUE):
  1. The Command Centre dashboard shows a readiness dial, 6 health mini-cards, and a prototype banner reflecting real, live aggregate system state (Section 11.1).
  2. The Ask GxP Copilot page provides a chat interface where a user can type the hero query and get a response, with the verified finding card from Phase 4 rendering inline in the conversation.
  3. While a query is in flight, the live agent topology visualization shows each A0–A6 agent node transition Waiting → Running → Complete in real time over the WebSocket stream.
  4. The Guided Tour walks the exact 8-step sequence in Section 14.4, and a user can complete the full Monitor→Investigate→Trust→Remediate→Audit loop through it without a developer narrating gaps.
**Plans**: TBD
**UI hint**: yes

### Phase 7: Integration & Hardening
**Goal**: Nothing in the demo path breaks under adversarial input, and restoring demo state is a single command — the system is hardened for judged demo conditions. (Build-Map Stage 6, Gate: "nothing in the demo path breaks under adversarial input; demo-state reset is one command.")
**Mode:** mvp
**Depends on**: Phase 6 (all of Stage 6 depends on Stage 5 being feature-complete for P0 items)
**Requirements**: None — this phase validates Phases 1–6 hold under adversarial and edge-case conditions; it introduces no new v1 capability. Its ticket scope corresponds to the v2 Hardening items (HARD-01 through HARD-06) already deferred in REQUIREMENTS.md.
**Ticket context (Build-Map Stage 6)**: SENT-6-01 (end-to-end flow tests, Critical), SENT-6-02 (C2 adversarial testing, Critical), SENT-6-03 (hash-chain tamper testing, Critical), SENT-6-04 (graph traversal edge cases), SENT-6-05 (RAG retrieval evaluation), SENT-6-06 (demo-state reset script), SENT-6-07 (performance/reliability pass)
**Success Criteria** (what must be TRUE):
  1. The full Monitor→Investigate→Trust→Remediate→Audit loop is scripted end-to-end and passes as an automated test.
  2. C2 survives injection attempts beyond the seeded test phrases, and each role (IT System Manager / QA-Compliance / Auditor) is tested attempting out-of-scope actions and is correctly, deterministically blocked.
  3. The hash chain is tested against multiple tamper vectors beyond the single demo endpoint and correctly flags each one; Blast Radius is tested against graph edge cases (cycles, missing nodes, disconnected subgraphs).
  4. A single command restores seed data and clears session/audit state between demo run-throughs.
**Plans**: TBD

### Phase 8: Freeze
**Goal**: No new features ship from this point — only P0 bug fixes, non-functional visual polish, a timed rehearsal against the 7-minute demo script, a backup recording, a final bible-reconciliation review, and submission packaging. (Build-Map Stage 7, no new-feature gate — "No new features from this point.")
**Mode:** mvp
**Depends on**: Phase 7
**Requirements**: None — freeze phase; bug-fix and submission packaging only, no new capability introduced.
**Ticket context (Build-Map Stage 7)**: SENT-7-01 (bug-fix pass only, P0 blockers), SENT-7-02 (visual polish, non-functional), SENT-7-03 (timed demo rehearsal against Section 15 script), SENT-7-04 (backup demo recording), SENT-7-05 (final bible-reconciliation review, Critical, Opus — Rule 14), SENT-7-06 (submission assets)
**Success Criteria** (what must be TRUE):
  1. Only P0 blockers triaged against Stage 6 findings are fixed; no new features are introduced.
  2. A full run against the 7-minute demo script (Section 15) is rehearsed and timed, and a backup demo video is recorded in case of live-environment failure.
  3. An Opus review reconciles any drift between shipped code and the Project Bible (Rule 14) and resolves it before Q&A, and hackathon submission assets are packaged per the portal's requirements.
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Environment | 0/4 | Planned | - |
| 2. Foundation | 0/8 | Planned | - |
| 3. Intelligence & Retrieval | 0/TBD | Not started | - |
| 4. Evidence & Impact | 0/TBD | Not started | - |
| 5. Safety & Remediation | 0/TBD | Not started | - |
| 6. Product Experience | 0/TBD | Not started | - |
| 7. Integration & Hardening | 0/TBD | Not started | - |
| 8. Freeze | 0/TBD | Not started | - |
