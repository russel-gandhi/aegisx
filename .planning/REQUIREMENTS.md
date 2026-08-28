# Requirements: AegisX AI

**Defined:** 2026-08-19
**Core Value:** Deterministic evidence verification (C1) — AI investigates, but is never blindly trusted; every important conclusion is independently verified with deterministic evidence.

## v1 Requirements

Requirements for the hackathon build. Ordered by the user's own demo hierarchy: Tier 1 (must work) → Tier 2 (makes it impressive) → Tier 3 (polish). Each maps to roadmap phases.

### Environment

- [x] **ENV-01**: `docker-compose up -d postgres qdrant opa` brings up all three services healthy on ports 5432/6333/8181
- [x] **ENV-02**: Postgres schema (full DDL from Bible Section 4.1) is loaded with FK constraints verified
- [x] **ENV-03**: Synthetic seed data for `GXP-MFG-DEMO-01` and `BUS-IT-DEMO-02` is populated, including deliberately-injected findings (e.g. overdue `DataSync Solutions` supplier)
- [x] **ENV-04**: FastAPI skeleton with Pydantic schemas (`AgentFinding`, `ActionProposal`, `AgentState`) is importable and `/api/health` returns 200

### Deterministic Policy Layer

- [x] **POL-01**: All 10 Rego rules from Bible Section 3.3 are implemented and independently unit-tested via `opa test` against positive and negative fixtures
- [x] **POL-02**: `evaluate_opa_policy()` calls the real OPA REST endpoint; `python_fallback_rules()` stub exists for when OPA is unreachable

### Agent Orchestration

- [x] **ORC-01**: LangGraph `StateGraph` compiles with the exact topology `C2 → A0 → [A1…A6 in parallel via Send] → C1 → A7 → C3`
- [ ] **ORC-02**: A0 Orchestrator classifies intent and fans out to a subset of A1–A6; on a 2000ms timeout it falls back to the full `["A1".."A6"]` set (tested explicitly)
- [x] **ORC-03**: A2 Compliance Agent produces real `AgentFinding` output via deterministic checks (`verify_urs_approved`, `verify_periodic_eval_current`, `verify_test_traceability`)

### Evidence Verification (the hero loop)

- [ ] **EVID-01**: C1 Evidence & Grounding Verifier fans in on findings and calls `calculate_confidence()` against the real DB record and real OPA evaluation — never a mock
- [ ] **EVID-02**: When an LLM claim contradicts DB/OPA truth, C1 returns `INSUFFICIENT_EVIDENCE` (contradiction case explicitly tested)
- [x] **EVID-03**: A verified finding renders CLAIM / EVIDENCE / RULE / DETERMINISTIC CHECK / CONFIDENCE, sourced from server-trusted data — never LLM-generated UI
- [ ] **EVID-04**: End-to-end hero loop works: user asks "Is GXP-MFG-DEMO-01 audit ready?" → A0 routes → A2 produces a claim → C1 verifies it against real evidence → verified finding is shown

### Blast Radius

- [x] **GRAPH-01**: NetworkX evidence graph is built directly from live Postgres state
- [x] **GRAPH-02**: Blast Radius traversal returns correct downstream-impact nodes (affected tests/controls/systems) for a seeded change record
- [x] **GRAPH-03**: Evidence graph renders in-browser via React Flow from a graph API endpoint

### Controlled Remediation

- [x] **REM-01**: A7 Remediation Agent synthesizes an `ActionProposal`/CAPA narrative from already-verified findings only (never unverified claims)
- [x] **REM-02**: C3 Action Gateway routes actions by category (READ / DRAFT / MOCK_WRITE_LOW_RISK / GXP_RELEVANT_WRITE / PROHIBITED)
- [x] **REM-03**: GxP-relevant writes sit `PENDING` in `action_proposals` until human approval; approval dialog renders only from server-trusted proposal metadata
- [x] **REM-04**: Human approval queue works end-to-end: proposal → WebSocket push → approve → audit-logged → executed

### Safety Gateway

- [x] **SAFE-01**: C2 enforces RBAC (IT System Manager / QA-Compliance / Auditor) exactly per the Bible's permission matrix, with zero LLM in the decision path
- [x] **SAFE-02**: C2 detects prompt injection via entropy + regex, with zero LLM in the decision path; blocks known jailbreak phrases from the Bible deterministically

### Audit Trail

- [x] **AUDIT-01**: Hash-chained append-only audit trail records finding/verification/approval events
- [x] **AUDIT-02**: `verify_chain()` is implemented alongside the chain (not after) and detects tampering
- [x] **AUDIT-03**: `/api/audit/demonstrate-tamper` executes a raw SQL modification and `verify_chain()` correctly flags it

### Frontend Shell

- [x] **UI-01**: React + TypeScript + Vite + Tailwind app boots with routing scaffolded and a React Flow canvas mounted
- [x] **UI-02**: `/api/copilot/stream/{session_id}` WebSocket accepts a connection and streams live agent state end-to-end
- [x] **UI-03**: Command Centre dashboard shows a readiness dial and health mini-cards
- [x] **UI-04**: Ask GxP Copilot page provides chat + live agent topology visualization

### Advanced Retrieval (pulled forward from v2, Phase 06.1 — user directive, 2026-08-28)

- [ ] **AGT-01**: A1 System Knowledge agent (Qdrant RAG) with hybrid dense+sparse retrieval, fusion, and cross-encoder reranking — *moved from v2; see below, no longer deferred*
- [ ] **HARD-04**: RAG retrieval precision evaluation — *moved from v2; see below, no longer deferred*
- [ ] **RAG-01**: Real document ingestion (upload → parse → structure-aware chunk → index) for PDF/DOCX/CSV/plain-text
- [ ] **RAG-02**: `document_chunks` schema extended with section/page/parent_chunk_id/chunk_index/metadata (documented Bible deviation)
- [ ] **RAG-03**: Hybrid retrieval (Qdrant dense + BM25 lexical) with explicit fusion, per Bible Section 15
- [ ] **RAG-04**: Cross-encoder reranking stage between candidate fusion and evidence filtering
- [ ] **RAG-05**: Evidence filtering + context assembly with full provenance (Bible Section 15.7 fields), never dumping the raw candidate pool to the LLM
- [ ] **RAG-06**: Copilot wired to the real compiled `StateGraph` (`compiled_graph.ainvoke`) instead of the readiness-only stub; honest "insufficient evidence" when retrieval finds nothing above threshold
- [ ] **RAG-07**: Evidence inspection UI (source/section/page/retrieval method) per `UI_SPEC.md` Section 11, reusing the `AssuranceCard` provenance pattern

## v2 Requirements

Deferred — Tier 3 polish and system breadth beyond the hero loop, acknowledged but not required for a credible demo.

### Extended Agents

- ~~**AGT-01**: A1 System Knowledge agent (Qdrant RAG) with hybrid dense+sparse retrieval, fusion, and cross-encoder reranking~~ — **moved to v1, Phase 06.1** (2026-08-28 scope override)
- **AGT-02**: A3 Risk agent (DeepSeek R1 risk scoring)
- **AGT-03**: A4 Change agent (change impact traversal)
- **AGT-04**: A5 Incident agent (Groq Llama classification)
- **AGT-05**: A6 Access agent (overdue review / orphaned account detection)
- **AGT-06**: Multi-provider LLM router across Gemini/DeepSeek/Groq/OpenRouter with per-response `model_id` attribution

### Extended Verification

- **VERF-01**: ALCOA+ 9-dimension scoring extension of C1
- **VERF-02**: Assurance Cards (Claim / Evidence IDs / ALCOA+ score / Confidence / Model Attribution)
- **VERF-03**: Deterministic Verification Centre + FSM engine visualization

### Extended Frontend

- **FE-01**: Audit Readiness gap dashboard (filterable finding matrix + Evidence Confidence Heat Map)
- **FE-02**: Supplier Intelligence view
- **FE-03**: Assurance Lab (7-scenario interactive prompt-injection demo)
- **FE-04**: Trust Centre (LLM provider config, Rego bundle version, live chain integrity widget)
- **FE-05**: Inspection Readiness Simulator (timed 10-question challenge)
- **FE-06**: Guided Tour (8-step)
- **FE-07**: Evidence Pack PDF export

### Hardening

- **HARD-01**: End-to-end adversarial testing beyond seeded test phrases (injection, RBAC boundary tests)
- **HARD-02**: Multiple hash-chain tamper vectors beyond the single demo endpoint
- **HARD-03**: Graph traversal edge cases (cycles, missing nodes, disconnected subgraphs)
- ~~**HARD-04**: RAG retrieval precision evaluation~~ — **moved to v1, Phase 06.1** (2026-08-28 scope override)
- **HARD-05**: Demo-state reset script (one command)
- **HARD-06**: Latency/performance pass across the A0→C3 loop

## Out of Scope

Explicitly excluded from v1. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Supplier Intelligence view | User: "nobody notices" if removed — Tier 3, deferred to v2 |
| Inspection Readiness Simulator | User: "nobody notices" if removed — Tier 3, deferred to v2 |
| Multi-provider LLM routing (full) | Single working provider path proves the C1 loop; full router adds cost without proving core value |
| Full A1/A3–A6 agent breadth | Only A2 Compliance is required for the minimum killer demo; others are v2 expansion |
| Fancy frontend polish (FSM animations, Trust Centre, ALCOA+ UI, guided demo) | User's own Tier 3 classification — build only after Tier 1/2 are solid |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| ENV-01 | Phase 1 | Complete |
| ENV-02 | Phase 2 | Complete |
| ENV-03 | Phase 2 | Complete |
| ENV-04 | Phase 2 | Complete |
| POL-01 | Phase 2 | Complete |
| POL-02 | Phase 2 | Complete |
| ORC-01 | Phase 2 | Complete |
| UI-01 | Phase 2 | Complete |
| ORC-02 | Phase 3 | Pending |
| ORC-03 | Phase 3 | Complete |
| EVID-01 | Phase 3 | Pending |
| EVID-02 | Phase 3 | Pending |
| EVID-04 | Phase 3 | Pending |
| EVID-03 | Phase 4 | Done |
| GRAPH-01 | Phase 4 | Done |
| GRAPH-02 | Phase 4 | Done |
| GRAPH-03 | Phase 4 | Done |
| SAFE-01 | Phase 5 | Complete |
| SAFE-02 | Phase 5 | Complete |
| AUDIT-01 | Phase 5 | Complete |
| AUDIT-02 | Phase 5 | Complete |
| AUDIT-03 | Phase 5 | Complete |
| REM-01 | Phase 5 | Complete |
| REM-02 | Phase 5 | Complete |
| REM-03 | Phase 5 | Complete |
| REM-04 | Phase 5 | Complete |
| UI-02 | Phase 5 | Complete |
| UI-03 | Phase 6 | Complete |
| UI-04 | Phase 6 | Complete |

**Coverage:**

- v1 requirements: 29 total
- Mapped to phases: 29/29 ✓
- Unmapped: 0

**Phases with no v1 requirements:** Phase 7 (Integration & Hardening) and Phase 8 (Freeze) carry no v1 requirement mappings — they validate/harden the capabilities delivered in Phases 1–6 and correspond to the v2 Hardening items (HARD-01 through HARD-06) above, per AegisX-Build-Map.md Stages 6–7.

---
*Requirements defined: 2026-08-19*
*Last updated: 2026-08-19 after roadmap revision (8 phases mapped 1:1 onto AegisX-Build-Map.md Stage 0-7, superseding the earlier independently-derived 6-phase roadmap; 29/29 v1 requirements re-mapped, 100% coverage)*
