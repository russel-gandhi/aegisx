# AegisX AI — Build Map with Tickets

Each ticket follows Rule 3 (explicit contract before implementation) and is tagged:
- **Owner**: `Opus` (architecture/critical-path) or `Sonnet` (bounded implementation) per Section 16.2–16.4
- **Priority**: P0 / P1 / P2 per Section 16.8
- **Review**: `Standard` or `Critical` (Critical = unit + negative + edge-case + integration + Opus/human review, per Rule 6)

Ticket IDs: `SENT-<stage>-<number>`. Dependencies reference other ticket IDs — don't start a ticket until its deps are closed and tested.

---

## Stage 0 — Environment
**Gate:** `docker-compose up -d postgres qdrant opa` succeeds; all three health checks green.

| ID | Ticket | Contract | Owner | Pri | Review |
|---|---|---|---|---|---|
| SENT-0-01 | Repo scaffold + branching convention | Deliver repo structure, `.gitignore`, worktree/branch convention doc (Rule 10: no two agents editing same critical file) | Opus | P0 | Standard |
| SENT-0-02 | Docker Compose: postgres, qdrant, opa | All three services healthy on 5432/6333/8181; `docker-compose up -d` is the only setup step | Sonnet | P0 | Standard |

---

## Stage 1 — Foundation (target: Days 1–4)
**Gate:** schema loads, seed data present, one Rego rule evaluates via raw OPA REST call, API skeleton returns 200 on `/api/health`.

| ID | Ticket | Contract | Owner | Pri | Review |
|---|---|---|---|---|---|
| SENT-1-01 | Postgres DDL — full schema | All tables from Section 4.1 (`gxp_systems`, `documents`, `document_chunks`, `requirements`, `risks`, `design_elements`, `test_cases`, `test_results`, `incidents`, `access_reviews`, `access_records`, `suppliers`, `audit_events`, `action_proposals`) created; FK constraints verified | Sonnet | P0 | Standard |
| SENT-1-02 | Seed synthetic data | `GXP-MFG-DEMO-01` + `BUS-IT-DEMO-02` fully populated per Section 5, including the deliberately-injected findings (e.g. `DataSync Solutions` overdue supplier) | Sonnet | P0 | Standard |
| SENT-1-03 | All 10 Rego rules | Each rule from Section 3.3 implemented, unit-tested with `opa test` against synthetic positive + negative fixtures, independent of the app | Sonnet (rules) / Opus (policy review) | P0 | **Critical** |
| SENT-1-04 | OPA Docker sidecar wired to app | `evaluate_opa_policy()` (Section 3.4) calls the real REST endpoint; `python_fallback_rules()` stub exists for the unreachable case | Sonnet | P0 | Standard |
| SENT-1-05 | FastAPI skeleton + Pydantic schemas | All schemas from Section 4.3, `AgentFinding`, `ActionProposal`, `AgentState` typed and importable; `/api/health` live | Sonnet | P0 | Standard |
| SENT-1-06 | LangGraph `StateGraph` skeleton | Graph from Section 1.2 compiles with stub node returns (empty findings ok at this stage); edges match the C2→A0→[A1-A6]→C1→A7→C3 topology exactly | Opus (design) / Sonnet (impl) | P0 | Standard |
| SENT-1-07 | React/Vite/Tailwind shell | App boots, routing scaffolded for the 7 pages in Section 11, React Flow canvas mounted with placeholder nodes | Sonnet | P0 | Standard |
| SENT-1-08 | WebSocket connection pattern | `/api/copilot/stream/{session_id}` accepts a connection and echoes a test event end-to-end (backend → browser) | Sonnet | P0 | Standard |
| SENT-1-09 | CI test runner | Every PR from Stage 2 onward runs schema + Rego + basic API tests automatically | Sonnet | P1 | Standard |

**Dependencies:** all Stage 1 tickets depend on Stage 0 being closed. SENT-1-04 depends on SENT-1-03. SENT-1-06 depends on SENT-1-05.

---

## Stage 2 — Intelligence & Retrieval (target: Days 5–8)
**Gate:** a real query enters A0, fans out to real (non-stub) A1–A6, C1 produces a non-trivial confidence score sourced from real DB + OPA state.

| ID | Ticket | Contract | Owner | Pri | Review |
|---|---|---|---|---|---|
| SENT-2-01 | A0 Orchestrator | Intent classification via Gemini 2.5 Flash, `Send` fan-out per Section 1.2, 2000ms timeout → full `["A1"..."A6"]` fallback tested explicitly | Sonnet | P0 | Standard |
| SENT-2-02 | A2 Compliance agent (build first — highest demo visibility) | Real implementation: `verify_urs_approved`, `verify_periodic_eval_current`, `verify_test_traceability` deterministic checks + `AgentFinding` output matching Section 2 schema | Sonnet | P0 | Standard |
| SENT-2-03 | A1 System Knowledge agent | Qdrant `search_qdrant_documents` tool call + UUID validation against `gxp_systems`; abstain-on-timeout behavior implemented and tested | Sonnet | P0 | Standard |
| SENT-2-04 | A3 Risk agent | DeepSeek R1 call against `get_risk_rubric()`, `calculate_risk_score()` deterministic scorer, downgrade-to-Gemini-Flash fallback on >10s timeout tested | Sonnet | P0 | Standard |
| SENT-2-05 | A4 Change agent | `traverse_change_impact()` tool + direct-metadata-only fallback path when graph traversal is skipped | Sonnet | P0 | Standard |
| SENT-2-06 | A5 Incident agent | Groq Llama 3.3 70B classification + `time.diff` overdue-RCA rule; bypass-to-rule-only fallback tested | Sonnet | P0 | Standard |
| SENT-2-07 | A6 Access agent | Overdue review query + orphaned-privileged-account query; OpenRouter fallback tested | Sonnet | P0 | Standard |
| SENT-2-08 | Qdrant ingestion pipeline | Document chunking + embedding per Section 9.1, collection config matches Section 4.2 | Sonnet | P0 | Standard |
| SENT-2-09 | Hybrid retrieval — dense + sparse | Dense (Qdrant) and sparse (BM25) retrieval both return results independently, per Section 15.2 | Sonnet | P0 | Standard |
| SENT-2-10 | Fusion + cross-encoder reranking | Fusion combines dense/sparse; reranker reorders top-k per Section 15.3 | Sonnet | P1 | Standard |
| SENT-2-11 | Parent-context retrieval | Chunk hits resolve back to full parent document context per Section 15.4 | Sonnet | P1 | Standard |
| SENT-2-12 | C1 Evidence Verifier — real wiring | `calculate_confidence()` consumes real `db_record` + real `opa_evaluation`, not mocks; contradiction case (LLM claim vs DB/OPA truth) verified to actually produce `INSUFFICIENT_EVIDENCE` | Opus (algorithm review) / Sonnet (impl) | P0 | **Critical** |

**Dependencies:** SENT-2-01 depends on SENT-1-06. SENT-2-02 through 2-07 depend on SENT-2-01 + SENT-1-05. SENT-2-12 depends on SENT-2-02–07 and SENT-1-03/04.

---

## Stage 3 — Evidence & Impact (target: Days 9–11)
**Gate:** NetworkX graph builds from live Postgres state; Blast Radius returns correct downstream nodes for a seeded change record.

| ID | Ticket | Contract | Owner | Pri | Review |
|---|---|---|---|---|---|
| SENT-3-01 | Evidence Graph construction | NetworkX graph built directly from Postgres state per Section 10.1; persisted per architecture diagram (Section 1.1) | Opus (algorithm) / Sonnet (impl) | P0 | **Critical** |
| SENT-3-02 | React Flow evidence graph visualization | Graph renders in-browser from `/api/systems/{id}/evidence-graph` JSON | Sonnet | P0 | Standard |
| SENT-3-03 | Blast Radius traversal | Downstream-impact query answers the graph questions specified in Section 14.3; test cases written directly from those questions | Opus (design) / Sonnet (impl) | P0 | **Critical** |
| SENT-3-04 | Blast Radius UI | Visual impact-radius display wired to SENT-3-03 | Sonnet | P0 | Standard |
| SENT-3-05 | Assurance Cards | Claim / Evidence IDs / ALCOA+ score / Confidence / Model Attribution card per Section 11.2 | Sonnet | P0 | Standard |
| SENT-3-06 | Deterministic Verification Centre | Verification models + flow from Section 14.2 implemented and demo-testable | Opus (design) / Sonnet (impl) | P1 | Standard |
| SENT-3-07 | FSM engine + visualization | State-machine verification engine and its UI component | Opus (design) / Sonnet (impl) | P1 | Standard |
| SENT-3-08 | ALCOA+ extended verification (extends C1, no new subsystem) | 9-dimension check (Section 16.12) implemented as an extension of C1 — explicitly reuses `AgentFinding`/`ALCOAScore`, no new agent/page/table | Opus (review — scope constraint is explicit in the bible) / Sonnet (impl) | P0/P1 | **Critical** |

**Dependencies:** all of Stage 3 depends on Stage 2 (real agents + C1) being closed, since Blast Radius and Evidence Graph consume A1–A6 findings.

---

## Stage 4 — Safety & Remediation (target: Days 12–14)
**Gate:** a prompt-injection payload is blocked deterministically by C2 (never by an LLM judgment call); a proposed write sits in `PENDING` until approved; a tampered audit row is detected by `verify_chain()`.

| ID | Ticket | Contract | Owner | Pri | Review |
|---|---|---|---|---|---|
| SENT-4-01 | C2 RBAC permission matrix | `IT System Manager` / `QA/Compliance` / `Auditor` scopes enforced exactly per Section 2, C2 | Opus (design) / Sonnet (impl) | P0 | **Critical** |
| SENT-4-02 | C2 prompt-injection detection | Entropy + regex detection, explicitly zero LLM involvement in the decision path; test with known jailbreak phrases from Section 2 | Opus (design) / Sonnet (impl) | P0 | **Critical** |
| SENT-4-03 | C3 Action Gateway — category routing | READ / DRAFT / MOCK_WRITE_LOW_RISK / GXP_RELEVANT_WRITE / PROHIBITED routing exactly per Section 2, C3; approval dialog built only from server-trusted `ActionProposal` metadata (never LLM-generated UI) | Opus (design) / Sonnet (impl) | P0 | **Critical** |
| SENT-4-04 | Human approval queue + WebSocket push | `action_proposals` table → WS push → approve → audit-logged → execute, full loop tested | Sonnet | P0 | Standard |
| SENT-4-05 | A7 Remediation agent + CAPA generation | Gemini 2.5 Flash (Thinking ON) synthesis of `ActionProposal` from verified findings; empty-array fallback tested | Sonnet | P0 | Standard |
| SENT-4-06 | Hash-chained audit trail | Append-only chain per Section 7.1; `verify_chain()` implemented alongside the chain, not after | Opus (design) / Sonnet (impl) | P0 | **Critical** |
| SENT-4-07 | Tamper-detection test + demo endpoint | `/api/audit/demonstrate-tamper` executes a raw SQL modification; `verify_chain()` correctly flags it | Sonnet | P0 | **Critical** |
| SENT-4-08 | Action / Approval Centre UI | Full queue UI per Section 11.6 | Sonnet | P0 | Standard |

**Dependencies:** SENT-4-03/04/05 depend on SENT-2-12 (C1) and SENT-1-06 (graph topology). SENT-4-07 depends on SENT-4-06.

---

## Stage 5 — Product Experience (target: Days 15–17)
**Gate:** the full Monitor → Investigate → Trust → Remediate → Audit loop is walkable without a developer narrating gaps.

| ID | Ticket | Contract | Owner | Pri | Review |
|---|---|---|---|---|---|
| SENT-5-01 | Command Centre dashboard | Readiness dial + 6 health mini-cards + prototype banner, per Section 11.1 | Sonnet | **P0** | Standard |
| SENT-5-02 | Ask GxP Copilot (chat + live topology) | Chat + React Flow agent topology with Waiting/Running/Complete state coloring, per Section 11.2 | Sonnet | P1 | Standard |
| SENT-5-03 | Audit Readiness gap dashboard | Filterable finding matrix + Evidence Confidence Heat Map, per Section 11.3 | Sonnet | P1 | Standard |
| SENT-5-04 | Supplier Intelligence view | Registry + qualification status + reassessment dates, `DataSync Solutions` finding surfaced, per Section 11.5 | Sonnet | P1 (first cut candidate per bible's own cut order) | Standard |
| SENT-5-05 | Assurance Lab (7 scenarios) | Interactive prompt-injection demo (upload compromised doc → C2 quarantines it → audit event generated), per Section 11.7 | Sonnet | P1 | Standard |
| SENT-5-06 | Trust Centre | LLM provider config, active Rego bundle version, live Audit Chain Integrity widget wired to `verify_chain()`, per Section 11.8 | Sonnet | P1 | Standard |
| SENT-5-07 | Inspection Readiness Simulator | Timed 10-question 483-style challenge, <30s response target, per Section 11.9 | Sonnet | P1 | Standard |
| SENT-5-08 | Guided Tour (8-step) | Implements the exact step sequence in Section 14.4 — build this to double as demo scaffolding, not a separate artifact | Sonnet | P0 | Standard |
| SENT-5-09 | Evidence Pack export (PDF) | WeasyPrint HTML→PDF for `/api/reports/evidence-pack` | Sonnet | P1 | Standard |

**Dependencies:** SENT-5-01/08 depend on all of Stage 4. SENT-5-02–07 can parallelize once their respective backend pieces (Stage 2–4) are closed.

---

## Stage 6 — Integration & Hardening (target: Days 18–19)
**Gate:** nothing in the demo path breaks under adversarial input; demo-state reset is one command.

| ID | Ticket | Contract | Owner | Pri | Review |
|---|---|---|---|---|---|
| SENT-6-01 | End-to-end flow tests | Full Monitor→Investigate→Trust→Remediate→Audit loop scripted and passing | Sonnet | P0 | **Critical** |
| SENT-6-02 | C2 adversarial testing | Injection attempts beyond the seeded test phrases; RBAC boundary tests (each role attempting out-of-scope actions) | Opus (review) / Sonnet (exec) | P0 | **Critical** |
| SENT-6-03 | Hash-chain tamper testing | Multiple tamper vectors beyond the demo endpoint's single case | Sonnet | P0 | **Critical** |
| SENT-6-04 | Graph traversal edge cases | Cycles, missing nodes, disconnected subgraphs against Blast Radius | Sonnet | P1 | Standard |
| SENT-6-05 | RAG retrieval evaluation | Precision check: does hybrid retrieval actually surface the right chunks for the 3 core scenarios? | Sonnet | P1 | Standard |
| SENT-6-06 | Demo-state reset script | One command restores seed data + clears session/audit state between run-throughs | Sonnet | P0 | Standard |
| SENT-6-07 | Performance/reliability pass | Latency budget check across the A0→C3 loop under the WS streaming path | Sonnet | P1 | Standard |

**Dependencies:** all of Stage 6 depends on Stage 5 being feature-complete for P0 items.

---

## Stage 7 — Freeze (target: Day 20)
**No new features from this point.**

| ID | Ticket | Contract | Owner | Pri | Review |
|---|---|---|---|---|---|
| SENT-7-01 | Bug-fix pass only | Triage against Stage 6 findings, fix P0 blockers only | Sonnet | P0 | Standard |
| SENT-7-02 | Visual polish | Non-functional UI fixes only | Sonnet | P1 | Standard |
| SENT-7-03 | Timed demo rehearsal | Full run against the 7-minute script (Section 15), timed | — | P0 | Standard |
| SENT-7-04 | Backup demo recording | Full video capture in case of live-environment failure | — | P0 | Standard |
| SENT-7-05 | Final bible-reconciliation review | Opus review of any drift between shipped code and the Project Bible (Rule 14) — resolve before Q&A, not during it | Opus | P0 | **Critical** |
| SENT-7-06 | Submission assets | Whatever the hackathon portal requires, packaged | — | P0 | Standard |

---

## Reading this ticket set

- **Critical-review tickets are your MuleShield-rule checkpoints.** Every one touches something a judge or a demo failure could expose as fake: C1/C2/C3, the hash-chain, OPA rules, Blast Radius. Don't let "compiles and returns something" pass as done on these — that's the exact failure mode the MuleShield post-mortem flagged.
- **P0 tickets in Stage 5 (Command Centre, Guided Tour) are the only P0 frontend work.** Everything else in that stage is genuinely P1 — if Days 15–17 compress, that's where to cut first, matching the bible's own cut order (Supplier Intelligence, then graph-animation polish).
- No story points here — the bible doesn't give per-agent time budgets beyond phase gates. If you want, I can size these against your actual team size and hours for this hackathon.
