# Requirements: GxP Sentinel

**Defined:** 2026-08-19
**Core Value:** Deterministic evidence verification (C1) — AI investigates, but is never blindly trusted; every important conclusion is independently verified with deterministic evidence.

## v1 Requirements

Requirements for the hackathon build. Ordered by the user's own demo hierarchy: Tier 1 (must work) → Tier 2 (makes it impressive) → Tier 3 (polish). Each maps to roadmap phases.

### Environment

- [ ] **ENV-01**: `docker-compose up -d postgres qdrant opa` brings up all three services healthy on ports 5432/6333/8181
- [ ] **ENV-02**: Postgres schema (full DDL from Bible Section 4.1) is loaded with FK constraints verified
- [ ] **ENV-03**: Synthetic seed data for `GXP-MFG-DEMO-01` and `BUS-IT-DEMO-02` is populated, including deliberately-injected findings (e.g. overdue `DataSync Solutions` supplier)
- [ ] **ENV-04**: FastAPI skeleton with Pydantic schemas (`AgentFinding`, `ActionProposal`, `AgentState`) is importable and `/api/health` returns 200

### Deterministic Policy Layer

- [ ] **POL-01**: All 10 Rego rules from Bible Section 3.3 are implemented and independently unit-tested via `opa test` against positive and negative fixtures
- [ ] **POL-02**: `evaluate_opa_policy()` calls the real OPA REST endpoint; `python_fallback_rules()` stub exists for when OPA is unreachable

### Agent Orchestration

- [ ] **ORC-01**: LangGraph `StateGraph` compiles with the exact topology `C2 → A0 → [A1…A6 in parallel via Send] → C1 → A7 → C3`
- [ ] **ORC-02**: A0 Orchestrator classifies intent and fans out to a subset of A1–A6; on a 2000ms timeout it falls back to the full `["A1".."A6"]` set (tested explicitly)
- [ ] **ORC-03**: A2 Compliance Agent produces real `AgentFinding` output via deterministic checks (`verify_urs_approved`, `verify_periodic_eval_current`, `verify_test_traceability`)

### Evidence Verification (the hero loop)

- [ ] **EVID-01**: C1 Evidence & Grounding Verifier fans in on findings and calls `calculate_confidence()` against the real DB record and real OPA evaluation — never a mock
- [ ] **EVID-02**: When an LLM claim contradicts DB/OPA truth, C1 returns `INSUFFICIENT_EVIDENCE` (contradiction case explicitly tested)
- [ ] **EVID-03**: A verified finding renders CLAIM / EVIDENCE / RULE / DETERMINISTIC CHECK / CONFIDENCE, sourced from server-trusted data — never LLM-generated UI
- [ ] **EVID-04**: End-to-end hero loop works: user asks "Is GXP-MFG-DEMO-01 audit ready?" → A0 routes → A2 produces a claim → C1 verifies it against real evidence → verified finding is shown

### Blast Radius

- [ ] **GRAPH-01**: NetworkX evidence graph is built directly from live Postgres state
- [ ] **GRAPH-02**: Blast Radius traversal returns correct downstream-impact nodes (affected tests/controls/systems) for a seeded change record
- [ ] **GRAPH-03**: Evidence graph renders in-browser via React Flow from a graph API endpoint

### Controlled Remediation

- [ ] **REM-01**: A7 Remediation Agent synthesizes an `ActionProposal`/CAPA narrative from already-verified findings only (never unverified claims)
- [ ] **REM-02**: C3 Action Gateway routes actions by category (READ / DRAFT / MOCK_WRITE_LOW_RISK / GXP_RELEVANT_WRITE / PROHIBITED)
- [ ] **REM-03**: GxP-relevant writes sit `PENDING` in `action_proposals` until human approval; approval dialog renders only from server-trusted proposal metadata
- [ ] **REM-04**: Human approval queue works end-to-end: proposal → WebSocket push → approve → audit-logged → executed

### Safety Gateway

- [ ] **SAFE-01**: C2 enforces RBAC (IT System Manager / QA-Compliance / Auditor) exactly per the Bible's permission matrix, with zero LLM in the decision path
- [ ] **SAFE-02**: C2 detects prompt injection via entropy + regex, with zero LLM in the decision path; blocks known jailbreak phrases from the Bible deterministically

### Audit Trail

- [ ] **AUDIT-01**: Hash-chained append-only audit trail records finding/verification/approval events
- [ ] **AUDIT-02**: `verify_chain()` is implemented alongside the chain (not after) and detects tampering
- [ ] **AUDIT-03**: `/api/audit/demonstrate-tamper` executes a raw SQL modification and `verify_chain()` correctly flags it

### Frontend Shell

- [ ] **UI-01**: React + TypeScript + Vite + Tailwind app boots with routing scaffolded and a React Flow canvas mounted
- [ ] **UI-02**: `/api/copilot/stream/{session_id}` WebSocket accepts a connection and streams live agent state end-to-end
- [ ] **UI-03**: Command Centre dashboard shows a readiness dial and health mini-cards
- [ ] **UI-04**: Ask GxP Copilot page provides chat + live agent topology visualization

## v2 Requirements

Deferred — Tier 3 polish and system breadth beyond the hero loop, acknowledged but not required for a credible demo.

### Extended Agents

- **AGT-01**: A1 System Knowledge agent (Qdrant RAG) with hybrid dense+sparse retrieval, fusion, and cross-encoder reranking
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
- **HARD-04**: RAG retrieval precision evaluation
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
| Direct mapping to Sentinel-Build-Map.md ticket IDs | User chose independent phase derivation; Build-Map stays a reference for ticket-level contracts, not the roadmap source |
| Fancy frontend polish (FSM animations, Trust Centre, ALCOA+ UI, guided demo) | User's own Tier 3 classification — build only after Tier 1/2 are solid |

## Traceability

Populated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| ENV-01 | TBD | Pending |
| ENV-02 | TBD | Pending |
| ENV-03 | TBD | Pending |
| ENV-04 | TBD | Pending |
| POL-01 | TBD | Pending |
| POL-02 | TBD | Pending |
| ORC-01 | TBD | Pending |
| ORC-02 | TBD | Pending |
| ORC-03 | TBD | Pending |
| EVID-01 | TBD | Pending |
| EVID-02 | TBD | Pending |
| EVID-03 | TBD | Pending |
| EVID-04 | TBD | Pending |
| GRAPH-01 | TBD | Pending |
| GRAPH-02 | TBD | Pending |
| GRAPH-03 | TBD | Pending |
| REM-01 | TBD | Pending |
| REM-02 | TBD | Pending |
| REM-03 | TBD | Pending |
| REM-04 | TBD | Pending |
| SAFE-01 | TBD | Pending |
| SAFE-02 | TBD | Pending |
| AUDIT-01 | TBD | Pending |
| AUDIT-02 | TBD | Pending |
| AUDIT-03 | TBD | Pending |
| UI-01 | TBD | Pending |
| UI-02 | TBD | Pending |
| UI-03 | TBD | Pending |
| UI-04 | TBD | Pending |

**Coverage:**
- v1 requirements: 29 total
- Mapped to phases: 0 (pending roadmap creation)
- Unmapped: 29 ⚠️

---
*Requirements defined: 2026-08-19*
*Last updated: 2026-08-19 after initial definition*
