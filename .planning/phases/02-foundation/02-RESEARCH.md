# Phase 2: Foundation - Research

**Researched:** 2026-08-20
**Domain:** Postgres DDL, OPA/Rego policy engine, FastAPI + Pydantic + LangGraph skeleton, Vite/React/Tailwind/React Flow frontend shell, WebSocket streaming pattern
**Confidence:** HIGH (all schema/rule/schema-model claims verified by reading the Bible directly this session; package versions verified against live registries; one CRITICAL syntax-compatibility finding verified against OPA's own migration docs)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
None stated as `## Decisions` — CONTEXT.md places everything under Claude's Discretion (see below). Treat the phase boundary itself (Build-Map Stage 1, tickets SENT-1-01 through SENT-1-09) as the binding scope: when a ticket contract and the Bible disagree, the Bible wins (CLAUDE.md Rule 14).

### Claude's Discretion
All implementation choices are at Claude's discretion, guided by:
- The Bible's DDL, Pydantic models, and Rego rule specs (Section references in Sentinel-Build-Map.md ticket contracts) are the source of truth for schema/API shape — do not invent alternative schemas.
- BRANCHING.md §4 Stage 1 file ownership table governs which paths belong to which ticket — respect it so parallel plan waves in this phase don't collide on files.
- Deterministic-first constraint (CLAUDE.md, Bible §1.3) applies from this phase forward: no LLM evaluates compliance/RBAC/injection decisions, even in skeleton form.
- SENT-1-03 (Rego rules) and SENT-1-06 (LangGraph StateGraph design) are Critical-review-level tickets per BRANCHING.md — plan and execute with correspondingly stronger test coverage (unit + negative + edge-case + integration), not a smoke test.

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope. Real (non-stub) agent logic, C1 confidence scoring, and the evidence graph are explicitly Phase 3+ scope, not this phase.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| ENV-02 | Postgres schema (full DDL from Bible Section 4.1) loaded, FK constraints verified | See "Postgres Schema" section — exact DDL transcribed verbatim below, with a resolved ambiguity between the Build-Map's abbreviated table list and the Bible's full ~20-table DDL |
| ENV-03 | Synthetic seed data for both demo systems, including injected findings | See "Seed Data" section — exact INSERT statements transcribed verbatim from Bible Section 5 |
| ENV-04 | FastAPI skeleton with Pydantic schemas importable, `/api/health` returns 200 | See "FastAPI Skeleton" section |
| POL-01 | All 10 Rego rules implemented, unit-tested via `opa test` | See "Rego Policy Layer" section — includes a CRITICAL syntax-compatibility pitfall (Rego v0 vs v1) that blocks this requirement if not caught |
| POL-02 | `evaluate_opa_policy()` calls real OPA REST endpoint; `python_fallback_rules()` stub exists | See "Rego Policy Layer" > "Python OPA Integration" |
| ORC-01 | LangGraph `StateGraph` compiles with exact `C2 → A0 → [A1…A6 via Send] → C1 → A7 → C3` topology | See "LangGraph StateGraph Skeleton" section |
| UI-01 | React/Vite/Tailwind app boots, routing scaffolded, React Flow canvas mounted | See "Frontend Shell" section |
</phase_requirements>

## Summary

Phase 2 is pure scaffolding: every ticket contract (SENT-1-01 through SENT-1-09) asks for structure that *compiles/loads/returns 200*, not working business logic. The Bible gives exact, copy-paste-ready specifications for the DDL (Section 4.1), the seed INSERTs (Section 5), all 10 Rego rules (Section 3.3), the Pydantic models (Section 4.3), and the LangGraph skeleton (Section 1.2) — the planner's job is to transcribe these verbatim into the right files, not to redesign them.

Two verified findings materially change how this phase must be executed relative to a literal reading of the Bible:

1. **The Bible's Rego rule syntax will not parse on the OPA version already running in this repo.** The Bible's 10 rules use Rego v0 partial-set syntax (`violation[{...}] { ... }`), but `docker-compose.yml` already runs `openpolicyagent/opa:1.19.1-debug` (certified healthy in Phase 1), and OPA v1.0+ defaults to Rego v1, which requires `contains` and `if` keywords. Pasting the Bible's rules as-is will fail `opa test` and the REST evaluation. The fix is mechanical (add `contains`/`if`, rule *logic* is unchanged) — full corrected example given below for the rule recommended for the phase gate.
2. **`react-flow-renderer` (the name the Bible section 10.3 uses) and even `reactflow` (the more recent name) are both superseded.** The current package is `@xyflow/react` (v12.x). `npm view react-flow-renderer` returns an explicit deprecation notice pointing at `reactflow`, which itself has been renamed again to `@xyflow/react`. Use `@xyflow/react`.

Everything else — the DDL, the seed data, the Pydantic models, the StateGraph stub-node pattern, the API table, the WebSocket route shape — is directly transcribable from the Bible with no reinterpretation needed.

**Primary recommendation:** Transcribe the Bible's DDL/seed/Rego/Pydantic/StateGraph content verbatim into the correct files (per BRANCHING.md's file-ownership table), fix only the two verified compatibility issues above (Rego v1 syntax, `@xyflow/react` package name), and treat the phase gate's "one Rego rule evaluates via raw OPA REST call" as satisfied by rule #1 (`ANNEX11-S4-DOC-001`, O&M document DRAFT) since the seed data (`DOC-2026-OM-99`) is purpose-built to trigger it.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Schema + seed data | Database / Storage | — | Postgres owns all persistent GxP state; Section 4.1/5 are DB-tier artifacts exclusively |
| Compliance rule evaluation (10 Rego rules) | API / Backend (OPA sidecar, called from backend) | — | OPA is a separate deterministic service; FastAPI backend is the only caller in this phase (raw REST call is also acceptable directly against OPA for the gate check) |
| Pydantic schema validation | API / Backend | — | All `AgentFinding`/`ActionProposal`/`AgentState` types live in `backend/`, validated at the FastAPI boundary |
| LangGraph orchestration skeleton | API / Backend | — | Runs server-side inside the FastAPI process; no client-visible surface in this phase beyond the WS echo |
| WebSocket live state streaming | API / Backend (server) + Browser / Client (consumer) | — | Route lives in `backend/`; the client that renders state lives in `frontend/` — this is the one capability genuinely split across two tiers in Stage 1 |
| React Flow canvas / routing shell | Browser / Client | — | Pure SPA concern; no backend dependency at skeleton stage beyond the health check |
| CI test runner | Build / CI (no runtime tier) | — | `.github/workflows/` orchestrates `pytest`/`opa test`/health-check, doesn't run inside the app's request path |

## Standard Stack

### Backend (Python)

| Library | Version (verified) | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `fastapi` | 0.141.1 latest on PyPI [VERIFIED: pip index versions, 2026-08-20] | HTTP API framework, Pydantic-native routing | Named explicitly in CLAUDE.md and Bible Section 12 |
| `pydantic` | 2.13.4 latest on PyPI [VERIFIED: pip index versions] | Data validation / schema models (Section 4.3) | Bible's model definitions use v2-style `Field(default_factory=...)`, compatible with Pydantic 2.x |
| `uvicorn` | 0.52.4 latest on PyPI [VERIFIED: pip index versions] | ASGI server to run the FastAPI app | De facto standard ASGI server for FastAPI |
| `langgraph` | 1.2.11 latest on PyPI [VERIFIED: pip index versions] | `StateGraph` orchestration engine (Section 1.2) | Named explicitly by the Bible; core primitives (`StateGraph`, `Send`, `add_conditional_edges`) confirmed unchanged from 0.x → 1.x [CITED: docs.langchain.com/oss/python/migrate/langgraph-v1 — "core graph primitives of state, nodes, and edges remain unchanged"] |
| `langchain-core` | 1.6.0 latest on PyPI [VERIFIED: pip index versions] | `BaseMessage`, `add_messages` reducer used by `AgentState` | Direct dependency of the Bible's Section 1.2 code sample |
| `httpx` | 0.28.1 latest on PyPI [VERIFIED: pip index versions] | Async HTTP client for `evaluate_opa_policy()` | Named explicitly in Bible Section 3.4's code sample |

### Frontend (Node)

| Library | Version (verified) | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `vite` | 8.2.2 latest on npm [VERIFIED: npm view, 2026-08-20] | Dev server / build tool | Named explicitly in CLAUDE.md and Bible Section 11 |
| `react` / `react-dom` | 19.2.8 latest on npm [VERIFIED: npm view] | UI library | Named explicitly in CLAUDE.md |
| `typescript` | current stable via `vite` React-TS template [ASSUMED — not independently version-checked, low risk] | Type safety | Named explicitly in CLAUDE.md ("React + TypeScript") |
| `tailwindcss` | 4.3.4 latest on npm [VERIFIED: npm view] — **major version jump from the v3 era CLAUDE.md/Bible implicitly assume** | Utility CSS | Named explicitly; see State of the Art table below for the v4 setup change |
| `@tailwindcss/vite` | ships alongside `tailwindcss` v4, same major version [CITED: tailwindcss.com official docs, "Installing Tailwind CSS with Vite"] | Vite-native Tailwind v4 plugin | v4's supported Vite integration path — no PostCSS config needed |
| `@xyflow/react` | 12.11.3 latest on npm [VERIFIED: npm view; CITED: reactflow.dev/learn/troubleshooting/migrate-to-v12] | Graph/flow canvas (React Flow) | Bible section 10.3 says "react-flow-renderer"; that package is deprecated (`npm view react-flow-renderer deprecated` returns an explicit notice), superseded first by `reactflow`, now by `@xyflow/react` — use the current name |

### Testing (new in this phase — nothing exists yet)

| Library | Purpose | When to Use |
|---------|---------|-------------|
| `pytest` | Backend unit/integration tests (schema load, Pydantic import, Rego-via-REST smoke test, `/api/health`) | Every backend ticket in this phase (Wave 0 gap — see Validation Architecture) |
| `opa test` (built into the OPA binary, no separate package) | Rego rule unit tests, positive + negative fixtures | SENT-1-03, Critical-review ticket |
| `vitest` [ASSUMED — standard Vite-ecosystem test runner, not explicitly named by the Bible] | Frontend component/route smoke tests | SENT-1-07/1-08 if the planner wants automated frontend coverage; Vite's own scaffolding docs recommend it as the default pairing |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `@xyflow/react` | `reactflow` (unscoped, deprecated but still installable) | Would still work today but is explicitly the deprecated intermediate name; no reason to pick it over the current package |
| `pytest` | `unittest` (stdlib) | Bible/CLAUDE.md don't mandate a framework; `pytest` is the ecosystem default for FastAPI projects and is what SENT-1-09's CI runner will most naturally invoke |

**Installation:**
```bash
# backend/ (from repo root)
python -m venv backend/.venv
backend/.venv/Scripts/pip install fastapi "pydantic>=2" uvicorn[standard] langgraph langchain-core httpx pytest
# NOTE: use a project-local venv, not the global Anaconda env this research session
# found on PATH (pip 25.3 from C:\Anaconda3) — avoids version drift against other projects.

# frontend/ (from repo root)
npm create vite@latest frontend -- --template react-ts
cd frontend && npm install -D tailwindcss @tailwindcss/vite && npm install @xyflow/react
```

**Version verification:** All versions above were checked live against PyPI (`pip index versions <pkg>`) and npm (`npm view <pkg> version`) on 2026-08-20 — see per-row tags. Training-data version recall was not used for any pinned number in this table.

## Package Legitimacy Audit

> `gsd-tools` package-legitimacy seam was not found on this machine (checked `gsd-core/bin/gsd-tools.cjs` under repo root, `.claude/`, and `PATH` — none present). Fell back to direct registry verification (`npm view`, `pip index versions`) plus cross-checking each package against the project's own authoritative sources (CLAUDE.md, Bible) or official docs, per the package-name-provenance rule.

| Package | Registry | Age/Maturity | Downloads | Source Repo | Verdict | Disposition |
|---------|----------|-----|-----------|-------------|---------|-------------|
| `fastapi` | PyPI | Est. 2018, extremely widely used | Very high | github.com/fastapi/fastapi | OK | Approved — named in project's own CLAUDE.md |
| `pydantic` | PyPI | Est. 2017 | Very high | github.com/pydantic/pydantic | OK | Approved — named in project's own CLAUDE.md |
| `uvicorn` | PyPI | Est. 2017 | Very high | github.com/encode/uvicorn | OK | Approved — standard FastAPI companion |
| `langgraph` | PyPI | Est. 2024, official LangChain org | High | github.com/langchain-ai/langgraph | OK | Approved — named explicitly in Bible Section 1.2 |
| `langchain-core` | PyPI | Est. 2023, official LangChain org | Very high | github.com/langchain-ai/langchain | OK | Approved — dependency of Bible's code sample |
| `httpx` | PyPI | Est. 2019, Encode org (same as uvicorn/starlette) | Very high | github.com/encode/httpx | OK | Approved — named explicitly in Bible Section 3.4 |
| `vite` | npm | Est. 2020, Evan You / Vite team | Very high | github.com/vitejs/vite | OK | Approved — named in project's own CLAUDE.md |
| `react` / `react-dom` | npm | Est. 2013, Meta | Very high | github.com/facebook/react | OK | Approved — named in project's own CLAUDE.md |
| `tailwindcss` | npm | Est. 2017, Tailwind Labs | Very high | github.com/tailwindlabs/tailwindcss | OK | Approved — named in project's own CLAUDE.md; note v4 setup change below |
| `@xyflow/react` | npm | Est. 2019 as React Flow, rebranded 2024 under xyflow org | High | github.com/xyflow/xyflow | OK | Approved — official successor to the Bible's named `react-flow-renderer`; verified via `npm view` deprecation chain + official xyflow.dev/reactflow.dev docs |
| `pytest` | PyPI | Est. 2004 | Very high | github.com/pytest-dev/pytest | OK | Approved — Python ecosystem default test runner |
| `vitest` | npm | Est. 2021, Vite team | Very high | github.com/vitest-dev/vitest | OK | Approved (not in Bible; standard Vite-ecosystem pairing) — planner's discretion whether to include in this phase or defer |

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none — every package in this table is a top-tier, long-established, org-backed project. No `checkpoint:human-verify` gating required for installs in this phase.

## Postgres Schema

**Source: Bible Section 4.1, lines 587–828 [VERIFIED: GxP-Sentinel-Project-Bible-v6.md:587-828, read directly this session].** Transcribe this DDL **verbatim** into `infra/postgres/initdb/` (per BRANCHING.md §4, SENT-1-01 owns this path; per `docker-compose.yml:14`, anything in `infra/postgres/initdb/` is bind-mounted to `/docker-entrypoint-initdb.d` and runs automatically on a fresh Postgres volume).

### Ticket-vs-Bible discrepancy — resolved in favor of the Bible

SENT-1-01's contract text (and ROADMAP.md's own Success Criteria #1) lists 14 tables in parentheses: `gxp_systems, documents, document_chunks, requirements, risks, design_elements, test_cases, test_results, incidents, access_reviews, access_records, suppliers, audit_events, action_proposals`. The Bible's actual DDL block (Section 4.1) defines **20 tables** — the 14 above plus `supplier_assessments`, `periodic_evaluations`, `changes`, `change_actions`, `findings`, `evidence_refs`, `agent_messages`, `graph_nodes`, `graph_edges`, `candidate_memory`, `trusted_memory`, `users`, `sessions`. Six of the ten Rego rules and the seed data (Gap 6, 7, 10) directly depend on `suppliers`+`supplier_assessments`(unused by seed but schema-required), `periodic_evaluations`, `changes`+`change_actions` existing — so the ticket's parenthetical list is illustrative, not exhaustive. **Per CLAUDE.md ("when bible content and a ticket contract disagree, the bible wins"), create all 20 tables from the full DDL block, not just the 14 named in the ticket.**

### Full table list (verbatim from Bible, with exact column definitions)

```sql
-- Core System Registry (EU GMP Annex 11 Section 4)
CREATE TABLE gxp_systems (
    id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    system_owner VARCHAR(100) NOT NULL,
    lifecycle_state VARCHAR(50) NOT NULL,
    gxp_impact BOOLEAN DEFAULT TRUE,
    readiness_score INT DEFAULT 0,
    last_backup_test_ns BIGINT
);

CREATE TABLE documents (
    id VARCHAR(50) PRIMARY KEY,
    system_id VARCHAR(50) REFERENCES gxp_systems(id),
    doc_type VARCHAR(50),
    title VARCHAR(255),
    version VARCHAR(10),
    author VARCHAR(100),
    created_date TIMESTAMP,
    effective_date TIMESTAMP,
    status VARCHAR(50)
);

CREATE TABLE document_chunks (
    chunk_id UUID PRIMARY KEY,
    document_id VARCHAR(50) REFERENCES documents(id),
    content TEXT,
    embedding_id VARCHAR(100)
);

CREATE TABLE requirements (
    id VARCHAR(50) PRIMARY KEY,
    system_id VARCHAR(50) REFERENCES gxp_systems(id),
    req_text TEXT,
    test_case_id VARCHAR(50)
);

CREATE TABLE risks (
    id VARCHAR(50) PRIMARY KEY,
    system_id VARCHAR(50) REFERENCES gxp_systems(id),
    risk_summary TEXT,
    severity VARCHAR(20),
    probability VARCHAR(20),
    last_review_date_ns BIGINT,
    owner VARCHAR(100)
);

CREATE TABLE design_elements (
    id VARCHAR(50) PRIMARY KEY,
    system_id VARCHAR(50) REFERENCES gxp_systems(id),
    description TEXT
);

CREATE TABLE test_cases (
    id VARCHAR(50) PRIMARY KEY,
    system_id VARCHAR(50) REFERENCES gxp_systems(id),
    status VARCHAR(50)
);

CREATE TABLE test_results (
    id VARCHAR(50) PRIMARY KEY,
    test_case_id VARCHAR(50) REFERENCES test_cases(id),
    execution_date_ns BIGINT,
    pass_fail BOOLEAN,
    tester VARCHAR(100)
);

CREATE TABLE incidents (
    id VARCHAR(50) PRIMARY KEY,
    system_id VARCHAR(50) REFERENCES gxp_systems(id),
    title VARCHAR(255),
    description TEXT,
    severity VARCHAR(20),
    status VARCHAR(50),
    opened_date_ns BIGINT,
    rca_started BOOLEAN DEFAULT FALSE,
    patient_safety_relevant BOOLEAN DEFAULT FALSE
);

CREATE TABLE access_reviews (
    id VARCHAR(50) PRIMARY KEY,
    system_id VARCHAR(50) REFERENCES gxp_systems(id),
    review_type VARCHAR(50),
    scheduled_date_ns BIGINT,
    status VARCHAR(50),
    reviewer VARCHAR(100),
    accounts_in_scope INT
);

CREATE TABLE access_records (
    id VARCHAR(50) PRIMARY KEY,
    system_id VARCHAR(50) REFERENCES gxp_systems(id),
    user_id VARCHAR(50),
    is_privileged BOOLEAN,
    user_status VARCHAR(50)
);

CREATE TABLE suppliers (
    id VARCHAR(50) PRIMARY KEY,
    system_id VARCHAR(50) REFERENCES gxp_systems(id),
    name VARCHAR(255),
    reassessment_due_date_ns BIGINT,
    status VARCHAR(50)
);

CREATE TABLE supplier_assessments (
    id VARCHAR(50) PRIMARY KEY,
    supplier_id VARCHAR(50) REFERENCES suppliers(id),
    assessment_date_ns BIGINT,
    result VARCHAR(50)
);

CREATE TABLE periodic_evaluations (
    id VARCHAR(50) PRIMARY KEY,
    system_id VARCHAR(50) REFERENCES gxp_systems(id),
    due_date_ns BIGINT,
    status VARCHAR(50)
);

CREATE TABLE changes (
    id VARCHAR(50) PRIMARY KEY,
    system_id VARCHAR(50) REFERENCES gxp_systems(id),
    description TEXT,
    status VARCHAR(50),
    qa_approval_date TIMESTAMP
);

CREATE TABLE change_actions (
    id VARCHAR(50) PRIMARY KEY,
    change_id VARCHAR(50) REFERENCES changes(id),
    description TEXT,
    status VARCHAR(50)
);

CREATE TABLE findings (
    id VARCHAR(50) PRIMARY KEY,
    system_id VARCHAR(50) REFERENCES gxp_systems(id),
    agent_id VARCHAR(50),
    severity VARCHAR(20),
    status VARCHAR(50),
    description TEXT
);

CREATE TABLE evidence_refs (
    id VARCHAR(50) PRIMARY KEY,
    finding_id VARCHAR(50) REFERENCES findings(id),
    reference_type VARCHAR(50),
    reference_id VARCHAR(50)
);

CREATE TABLE action_proposals (
    id VARCHAR(50) PRIMARY KEY,
    action_type VARCHAR(50),
    target_system VARCHAR(50),
    payload JSONB,
    status VARCHAR(50)
);

-- Hash-Chained Audit Log (21 CFR Part 11.10(e))
CREATE TABLE audit_events (
    event_id VARCHAR(64) PRIMARY KEY,
    timestamp_utc TIMESTAMP,
    session_id VARCHAR(100),
    user_id VARCHAR(100),
    user_role VARCHAR(50),
    agent_id VARCHAR(50),
    action_type VARCHAR(50),
    target_system_id VARCHAR(50),
    target_record_id VARCHAR(50),
    input_hash VARCHAR(64),
    output_summary TEXT,
    evidence_ids JSONB,
    opa_rule_ids JSONB,
    model_id VARCHAR(50),
    prompt_version VARCHAR(50),
    approval_id VARCHAR(50),
    previous_event_hash VARCHAR(64),
    event_hash VARCHAR(64) NOT NULL
);

CREATE TABLE agent_messages (
    id VARCHAR(50) PRIMARY KEY,
    session_id VARCHAR(100),
    agent_id VARCHAR(50),
    message_content TEXT,
    timestamp_utc TIMESTAMP
);

CREATE TABLE graph_nodes (
    node_id VARCHAR(100) PRIMARY KEY,
    system_id VARCHAR(50) REFERENCES gxp_systems(id),
    node_type VARCHAR(50),
    properties JSONB
);

CREATE TABLE graph_edges (
    source_id VARCHAR(100) REFERENCES graph_nodes(node_id),
    target_id VARCHAR(100) REFERENCES graph_nodes(node_id),
    relation_type VARCHAR(50)
);

CREATE TABLE candidate_memory (
    id VARCHAR(50) PRIMARY KEY,
    fact_text TEXT,
    status VARCHAR(50)
);

CREATE TABLE trusted_memory (
    id VARCHAR(50) PRIMARY KEY,
    fact_text TEXT,
    approved_by VARCHAR(100)
);

CREATE TABLE users (
    id VARCHAR(50) PRIMARY KEY,
    username VARCHAR(100),
    role VARCHAR(50)
);

CREATE TABLE sessions (
    id VARCHAR(50) PRIMARY KEY,
    user_id VARCHAR(50) REFERENCES users(id),
    start_time TIMESTAMP,
    end_time TIMESTAMP
);
```

**Notable design choices (transcribed as-is, not invented):**
- Most primary keys are `VARCHAR(50)` app-generated IDs (e.g. `'GXP-MFG-DEMO-01'`), not auto-increment or `UUID DEFAULT gen_random_uuid()` — only `document_chunks.chunk_id` is `UUID`. Do not "improve" this to serial/UUID PKs across the board; the seed data (Section 5) hard-codes these string IDs as FK targets.
- Date fields split between `TIMESTAMP` (e.g. `documents.created_date`, `changes.qa_approval_date`) and `BIGINT` nanosecond-epoch columns suffixed `_ns` (e.g. `last_backup_test_ns`, `scheduled_date_ns`, `due_date_ns`, `opened_date_ns`, `last_review_date_ns`, `reassessment_due_date_ns`, `execution_date_ns`). The `_ns` columns exist specifically because the Rego rules compute against them with `time.now_ns()` / `time.diff(...)[2]` (Section 3.3) — keep them as `BIGINT`, do not convert to `TIMESTAMP`, or every Rego rule's date-diff logic breaks.
- No explicit indexes, unique constraints beyond PK, or `NOT NULL` beyond what's shown are specified by the Bible. Do not add speculative constraints not in Section 4.1 — FK constraints only, per SENT-1-01's own contract ("FK constraints verified").

## Seed Data

**Source: Bible Section 5, lines 939–997 [VERIFIED: GxP-Sentinel-Project-Bible-v6.md:939-997, read directly this session].** Owned by SENT-1-02, lands in `infra/postgres/seed/` per BRANCHING.md §4 (a directory separate from `initdb/`, since Postgres image auto-runs everything in `initdb/` — seed data should be a deliberately-invoked script, not bundled into the auto-init path, so `docker-compose down -v` / cold-start cycles don't silently re-seed without the operator choosing to).

```sql
-- GXP-MFG-DEMO-01 (Unhealthy)
INSERT INTO gxp_systems (id, name, system_owner, lifecycle_state, gxp_impact, readiness_score, last_backup_test_ns)
VALUES ('GXP-MFG-DEMO-01', 'NovaSynth Manufacturing Execution Support System', 'Jens Larsen', 'OPERATIONAL', TRUE, 61, 1709251200000000000);

-- Gap 1: O&M Document DRAFT
INSERT INTO documents (id, system_id, doc_type, title, version, author, created_date, effective_date, status)
VALUES ('DOC-2026-OM-99', 'GXP-MFG-DEMO-01', 'O&M', 'NovaSynth Operations Manual', 'v1.0', 'Sarah Jensen', '2026-08-01 10:00:00', NULL, 'DRAFT');

-- Gap 2: Access Review 98 Days Overdue (Epoch ns for May 11, 2026)
INSERT INTO access_reviews (id, system_id, review_type, scheduled_date_ns, status, reviewer, accounts_in_scope)
VALUES ('AR-2026-05', 'GXP-MFG-DEMO-01', 'QUARTERLY_PRIVILEGED', 1715424000000000000, 'PENDING', 'Marcus Aurelius', 14);

-- Gap 3: Risk Assessment Expired (Last reviewed Aug 15, 2024)
INSERT INTO risks (id, system_id, risk_summary, severity, probability, last_review_date_ns, owner)
VALUES ('RSK-2024-11', 'GXP-MFG-DEMO-01', 'Data corruption during LIMS interface sync', 'HIGH', 'OCCASIONAL', 1723718400000000000, 'Data Integrity Office');

-- Gap 4: P1 Incident Open 47 Days, No RCA (Opened July 1, 2026)
INSERT INTO incidents (id, system_id, title, description, severity, status, opened_date_ns, rca_started, patient_safety_relevant)
VALUES ('INC-849201', 'GXP-MFG-DEMO-01', 'Batch release module timeout', 'Operators unable to sign electronic batch record', 'P1', 'OPEN', 1719830400000000000, FALSE, TRUE);

-- Gap 5: URS-042 No Test Evidence
INSERT INTO requirements (id, system_id, req_text, test_case_id)
VALUES ('URS-042', 'GXP-MFG-DEMO-01', 'System shall enforce complex passwords', 'TC-2026-042');
INSERT INTO test_cases (id, system_id, status)
VALUES ('TC-2026-042', 'GXP-MFG-DEMO-01', 'DRAFT');

-- Gap 6: Supplier reassessment 6 months overdue
INSERT INTO suppliers (id, system_id, name, reassessment_due_date_ns, status)
VALUES ('SUP-2026-01', 'GXP-MFG-DEMO-01', 'DataSync Solutions', 1708214400000000000, 'APPROVED');

-- Gap 7: Periodic evaluation overdue 24 months
INSERT INTO periodic_evaluations (id, system_id, due_date_ns, status)
VALUES ('PE-2024-01', 'GXP-MFG-DEMO-01', 1704067200000000000, 'PENDING');

-- Gap 8: Backup restore test stale (triggered by gxp_systems.last_backup_test_ns above — no separate INSERT)

-- Gap 9: Orphaned privileged account (Employee departed 90 days ago)
INSERT INTO access_records (id, system_id, user_id, is_privileged, user_status)
VALUES ('ACC-2026-99', 'GXP-MFG-DEMO-01', 'U-9942', TRUE, 'DEPARTED');

-- Gap 10: Change record closed with unresolved actions
INSERT INTO changes (id, system_id, description, status, qa_approval_date)
VALUES ('CR-2026-089', 'GXP-MFG-DEMO-01', 'Database migration', 'CLOSED', '2026-08-01 12:00:00');
INSERT INTO change_actions (id, change_id, description, status)
VALUES ('CA-2026-089-1', 'CR-2026-089', 'Update SOPs post-migration', 'OPEN');

-- BUS-IT-DEMO-02 (Healthy)
INSERT INTO gxp_systems (id, name, system_owner, lifecycle_state, gxp_impact, readiness_score, last_backup_test_ns)
VALUES ('BUS-IT-DEMO-02', 'Argonaut Business Analytics Platform', 'Elena Rostova', 'OPERATIONAL', FALSE, 94, 1722470400000000000);
```

This is the **entire** seed script — Section 5 seeds only `GXP-MFG-DEMO-01`'s 10 gaps plus one healthy `BUS-IT-DEMO-02` row. Every other table (`document_chunks`, `design_elements`, `test_results`, `supplier_assessments`, `findings`, `evidence_refs`, `graph_nodes`/`graph_edges`, `candidate_memory`/`trusted_memory`, `users`, `sessions`, `agent_messages`, `action_proposals`, `audit_events`) is intentionally left empty by this ticket — do not invent additional seed rows for them; that's out of scope for SENT-1-02.

## Rego Policy Layer

**Source: Bible Section 3.3, lines 406–546 (all 10 rules) and Section 3.4, lines 548–579 (Python integration) [VERIFIED: GxP-Sentinel-Project-Bible-v6.md:406-579, read directly this session].**

### CRITICAL pitfall: Bible's Rego syntax is v0, the running OPA is v1-default

`docker-compose.yml:38-58` already runs `openpolicyagent/opa:1.19.1-debug` (image resolved and certified healthy in Phase 1 per `infra/README.md:87-91`). As of **OPA v1.0** (released ahead of this version), **Rego v1 syntax is the default parser** — partial-set rules like the Bible's `violation[{...}] { ... }` **must** use `contains` and `if` keywords, or `opa test`/`opa check` fails with `"contains" keyword is required for partial set rules` and `"if" keyword is required before rule body` [CITED: openpolicyagent.org/docs/v0-upgrade — official OPA v1.0 upgrade guide; ibm.com/support — reproduces the exact error text]. Rule *logic* (conditions, field names, severities, citations) is unaffected — only the rule *head* syntax needs the two keywords added. This is a mechanical, not semantic, transformation, so it does not conflict with "Bible wins on content disagreements" — the Bible's rule content is preserved exactly; only syntax is updated to match the OPA version this repo already runs.

**Corrected form of rule #1 (recommended minimum rule for the phase gate):**

```rego
package sentinel.gxp

# 1. ANNEX11-S4-DOC-001: O&M Manual must be approved
# Source: EU GMP Annex 11, Section 4 (Documentation)
# Input shape: {"documents": [{"id": "...", "system_id": "...", "doc_type": "O&M", "status": "DRAFT"}]}
violation contains {
    "rule_id": "ANNEX11-S4-DOC-001", "severity": "HIGH",
    "system_id": doc.system_id, "record_id": doc.id,
    "description": "O&M Document is not in APPROVED state"
} if {
    doc := input.documents[_]
    doc.doc_type == "O&M"
    doc.status != "APPROVED"
}
```

Apply the identical `contains { ... } if { ... }` transformation to all 10 rules for SENT-1-03 (all 10 are in scope for that ticket's Critical-review contract — only the syntax fix is new information, not a scope change). No `import rego.v1` line is needed or meaningful on OPA 1.19.1 — that import exists purely to opt pre-1.0 OPA versions into v1 syntax early; on an already-v1-default engine it's a no-op.

### Minimum rule for the phase gate

The phase gate only requires "one Rego rule evaluates via raw OPA REST call" — rule #1 (`ANNEX11-S4-DOC-001`) is the natural choice: the seed data's `DOC-2026-OM-99` (status `DRAFT`) is purpose-built to trigger it, and its input shape (`{"documents": [...]}`) is the simplest of the 10 (single-table, no joins). Verify with:

```bash
curl -X POST http://localhost:8181/v1/data/sentinel/gxp/violation \
  -H "Content-Type: application/json" \
  -d '{"input": {"documents": [{"id": "DOC-2026-OM-99", "system_id": "GXP-MFG-DEMO-01", "doc_type": "O&M", "status": "DRAFT"}]}}'
```
Expected: a `result` array containing one object with `rule_id: "ANNEX11-S4-DOC-001"`, `record_id: "DOC-2026-OM-99"`.

**Note:** all 10 rules are still required for the SENT-1-03 ticket contract itself (all P0, Critical review) — the gate is a minimum smoke test, not the ticket's actual scope. All 10 rule IDs, in order: `ANNEX11-S4-DOC-001` (O&M draft), `ANNEX11-S12-ACC-001` (access review >30d overdue), `ICH-Q9-RSK-001` (risk review >365d), `ANNEX11-S13-INC-001` (P1 incident >7d no RCA), `ANNEX11-S4-TRC-001` (URS/test traceability gap), `ANNEX11-S3-SUP-001` (supplier reassessment overdue), `ANNEX11-S11-PE-001` (periodic evaluation overdue), `ANNEX11-S16-BCK-001` (backup restore stale >365d), `ANNEX11-S12-ACC-002` (orphaned privileged account, CRITICAL severity), `ANNEX11-S10-CHG-001` (change closed with open actions).

### Python OPA Integration (SENT-1-04)

```python
# Source: Bible Section 3.4 — verbatim
import httpx
from typing import List, Dict, Any

async def evaluate_opa_policy(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Sends payload to OPA REST API and returns violation list."""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "http://localhost:8181/v1/data/sentinel/gxp/violation",
                json={"input": payload},
                timeout=2.0
            )
            response.raise_for_status()
            return response.json().get("result", [])
    except httpx.RequestError as e:
        print(f"OPA unreachable: {e}. Executing Python fallback rules.")
        return python_fallback_rules(payload)

def python_fallback_rules(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    # Fallback implementation mirroring Rego logic
    violations = []
    # Implementation omitted for brevity in bible, relies on standard Python conditionals.
    return violations
```

SENT-1-04's contract only requires this stub to *exist* and for `evaluate_opa_policy()` to call the real endpoint — the Bible explicitly says the fallback body is "omitted for brevity," so a genuinely empty-list stub with a `# TODO: mirror Rego rule logic (Phase 3+)` comment satisfies this ticket; do not hand-build all 10 rules' logic twice in this phase (Python + Rego) unless the planner deliberately wants belt-and-suspenders coverage now. `http://localhost:8181` matches `docker-compose.yml`'s `127.0.0.1:8181` published port — correct as-is for a backend process running on the host (not containerized) calling into the OPA container.

### Test fixture convention

OPA's own convention: `opa test <policy-dir>` recursively runs any `*_test.rego` file colocated with the rule files, using `test_<name> if { ... }` functions inside the same `package sentinel.gxp` (or a `sentinel.gxp_test` package) that assert on `violation` results for a given synthetic `input`. Recommended layout: `policies/rules.rego` (all 10 rules) + `policies/rules_test.rego` (positive + negative fixture per rule, 20 test functions minimum for SENT-1-03's Critical-review bar).

## FastAPI Skeleton

**Source: Bible Section 4.3 (Pydantic models, lines 834-937) and Section 12 (API table, lines 1404-1420) [VERIFIED: GxP-Sentinel-Project-Bible-v6.md:834-937,1404-1420, read directly this session].**

`/api/health` contract per Section 12's own table: `GET /api/health` → `{"status": "ok"}`. This is the literal, exact response shape:

```python
from fastapi import FastAPI

app = FastAPI()

@app.get("/api/health")
async def health():
    return {"status": "ok"}
```

All Pydantic models from Section 4.3 must be importable (SENT-1-05's contract). Transcribe verbatim — this is the **application-layer** (`pydantic.BaseModel`) version, distinct from the **graph-state** (`TypedDict`) version used inside the LangGraph module (Section 1.2) which has the same field names but a different base:

```python
# Source: Bible Section 4.3 — verbatim
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from datetime import datetime

class EvidenceRef(BaseModel):
    reference_type: str = Field(..., description="Document, Test Record, Access Review, etc.")
    reference_id: str
    uri: Optional[str] = None

class ALCOAScore(BaseModel):
    attributable: bool = False
    legible: bool = True
    contemporaneous: bool = False
    original: bool = False
    accurate: bool = True
    complete: bool = True
    consistent: bool = True
    enduring: bool = True
    available: bool = True

class AgentFinding(BaseModel):
    finding_id: str
    claim: str
    regulatory_citations: List[str]
    confidence_score: str  # HIGH, MEDIUM, LOW, INSUFFICIENT_EVIDENCE
    evidence_ids: List[str]
    alcoa_score: ALCOAScore
    model_attribution: str

class ActionProposal(BaseModel):
    action_type: str
    target_system: str
    payload: Dict[str, Any]
    justification: str

class AgentMessage(BaseModel):
    agent_id: str
    message: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class AuditEvent(BaseModel):
    event_id: str
    timestamp_utc: datetime
    session_id: str
    user_id: str
    user_role: str
    agent_id: str
    action_type: str
    target_system_id: str
    target_record_id: Optional[str]
    input_hash: str
    output_summary: str
    evidence_ids: List[str]
    opa_rule_ids: List[str]
    model_id: Optional[str]
    prompt_version: str
    approval_id: Optional[str]
    previous_event_hash: str
    event_hash: str

class OPAViolation(BaseModel):
    rule_id: str
    severity: str
    system_id: str
    record_id: str
    description: str

class ConfidenceAssessment(BaseModel):
    score: str
    justification: str

class CAPAProposal(BaseModel):
    root_cause: str
    corrective_action: str
    preventive_action: str
    effectiveness_check: str
    due_date: datetime
    owner: str

class AuditPackage(BaseModel):
    system_overview: Dict[str, Any]
    findings: List[AgentFinding]
    risk_summary: Dict[str, Any]
    audit_trail_valid: bool
    chain_of_custody: List[str]

class SystemReadinessScore(BaseModel):
    system_id: str
    score: int
    breakdown: Dict[str, int]

class AgentExecutionTrace(BaseModel):
    agent_id: str
    start_time: datetime
    end_time: datetime
    tools_called: List[str]
    output_produced: Any
```

**Recommended project structure (Claude's discretion — no structure mandated by the Bible beyond "the FastAPI application entrypoint and the Pydantic schema modules" per BRANCHING.md):**
```
backend/
├── app/
│   ├── main.py          # FastAPI() instance, /api/health, route registration
│   ├── schemas.py        # Section 4.3 Pydantic models (this section, verbatim)
│   ├── graph/
│   │   └── state.py       # Section 1.2 StateGraph — AgentState TypedDict, stub nodes, compiled graph
│   ├── opa_client.py      # evaluate_opa_policy() + python_fallback_rules() (SENT-1-04)
│   └── ws/
│       └── copilot.py     # /api/copilot/stream/{session_id} route (SENT-1-08)
├── tests/
│   └── test_health.py     # pytest — asserts /api/health returns 200 + {"status": "ok"}
└── requirements.txt / pyproject.toml
```

Only `/api/health` needs to be *live and returning 200* for the phase gate. Section 12's other 10 endpoints exist in the table for later phases (`/api/systems`, `/api/copilot/query`, `/api/actions/{id}/approve`, `/api/audit/*`, `/api/reports/evidence-pack`, `/api/opa/evaluate` — none required to function in Phase 2, though stub route registration is reasonable if the planner wants FastAPI's OpenAPI docs to reflect the full surface early).

## LangGraph StateGraph Skeleton

**Source: Bible Section 1.2, lines 97-196 [VERIFIED: GxP-Sentinel-Project-Bible-v6.md:97-196, read directly this session].** SENT-1-06's contract is explicit: "compiles with stub node returns (empty findings ok at this stage); edges match the topology exactly." Transcribe the Bible's code sample **as the actual implementation**, not as a reference to reimplement differently — every node in this phase is intentionally a stub:

```python
# Source: Bible Section 1.2 — verbatim
from typing import TypedDict, Annotated, List, Dict, Any, Sequence
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage
from langgraph.constants import Send
import operator

class AgentFinding(TypedDict):
    finding_id: str
    claim: str
    regulatory_citations: List[str]
    confidence_score: str
    evidence_ids: List[str]
    alcoa_score: Dict[str, bool]
    model_attribution: str

class ActionProposal(TypedDict):
    action_type: str
    target_system: str
    payload: Dict[str, Any]
    justification: str

class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    system_id: str
    user_intent: str
    active_agents: List[str]
    findings: Annotated[List[AgentFinding], operator.add]
    proposed_actions: Annotated[List[ActionProposal], operator.add]
    verification_results: Dict[str, Any]
    final_synthesis: str

async def orchestrator_a0(state: AgentState) -> Dict[str, Any]:
    return {"active_agents": ["A1", "A2", "A3", "A4", "A5", "A6"]}

async def system_knowledge_a1(state: AgentState) -> Dict[str, Any]:
    return {"findings": []}

async def compliance_a2(state: AgentState) -> Dict[str, Any]:
    return {"findings": []}

async def risk_a3(state: AgentState) -> Dict[str, Any]:
    return {"findings": []}

async def change_a4(state: AgentState) -> Dict[str, Any]:
    return {"findings": []}

async def incident_a5(state: AgentState) -> Dict[str, Any]:
    return {"findings": []}

async def access_a6(state: AgentState) -> Dict[str, Any]:
    return {"findings": []}

async def evidence_verifier_c1(state: AgentState) -> Dict[str, Any]:
    return {"verification_results": {"verified": True}}

async def remediation_a7(state: AgentState) -> Dict[str, Any]:
    return {"proposed_actions": []}

async def safety_gateway_c2(state: AgentState) -> Dict[str, Any]:
    return {"user_intent": "safe"}

async def action_gateway_c3(state: AgentState) -> Dict[str, Any]:
    return {"final_synthesis": "Execution complete. Actions queued for approval."}

def route_specialists(state: AgentState) -> List[Send]:
    return [Send(agent_name, {"messages": state["messages"], "system_id": state["system_id"]})
            for agent_name in state["active_agents"]]

graph = StateGraph(AgentState)
graph.add_node("C2", safety_gateway_c2)
graph.add_node("A0", orchestrator_a0)
graph.add_node("A1", system_knowledge_a1)
graph.add_node("A2", compliance_a2)
graph.add_node("A3", risk_a3)
graph.add_node("A4", change_a4)
graph.add_node("A5", incident_a5)
graph.add_node("A6", access_a6)
graph.add_node("C1", evidence_verifier_c1)
graph.add_node("A7", remediation_a7)
graph.add_node("C3", action_gateway_c3)

graph.set_entry_point("C2")
graph.add_edge("C2", "A0")
graph.add_conditional_edges("A0", route_specialists, ["A1", "A2", "A3", "A4", "A5", "A6"])
for agent in ["A1", "A2", "A3", "A4", "A5", "A6"]:
    graph.add_edge(agent, "C1")
graph.add_edge("C1", "A7")
graph.add_edge("A7", "C3")
graph.add_edge("C3", END)
compiled_graph = graph.compile()
```

**Verification for the gate:** `compiled_graph.ainvoke({"messages": [], "system_id": "GXP-MFG-DEMO-01", "user_intent": "", "active_agents": [], "findings": [], "proposed_actions": [], "verification_results": {}, "final_synthesis": ""})` should run to completion (all stub nodes return, no exceptions) and produce a state with `final_synthesis` set — this is the "compiles with stub node returns" bar. No real LLM call, DB call, or OPA call happens inside any of these 11 stub functions yet; that's Phase 3+ (per the CONTEXT.md deferred-scope note).

## Frontend Shell

**Source: Bible Section 11 (lines 1368-1420) [VERIFIED: GxP-Sentinel-Project-Bible-v6.md:1368-1420, read directly this session] and `frontend/README.md` ("7+ pages").**

### Discrepancy resolved: 8 documented pages, not 7

Section 11's subsection numbering skips `11.4` entirely (`11.3 Audit Readiness` is immediately followed by `11.5 Supplier Intelligence` — confirmed by direct grep, no `### 11.4` heading exists anywhere in the Bible). That leaves **8** named pages: 11.1 Command Centre, 11.2 Ask GxP Copilot, 11.3 Audit Readiness, 11.5 Supplier Intelligence, 11.6 Action/Approval Centre, 11.7 Assurance Lab, 11.8 Trust Centre, 11.9 Inspection Readiness Simulator. `11.4` is very likely the "Blast Radius" page, which does get its own ticket later (`SENT-3-04 Blast Radius UI`, Stage 3) but has no written Section 11 subsection of its own. SENT-1-07's contract says "7 pages"; `frontend/README.md` (Phase 1's own scaffolding) already hedges this as "7+ pages" — **scaffold routes for all 8 currently-documented pages now**, and leave room for a 9th (Blast Radius) route to be added in Phase 4 (Stage 3) without restructuring the router.

| Route (suggested) | Page | Section |
|---|---|---|
| `/` or `/dashboard` | Command Centre | 11.1 |
| `/copilot` | Ask GxP Copilot (chat + React Flow topology) | 11.2 |
| `/audit-readiness` | Audit Readiness gap dashboard | 11.3 |
| `/suppliers` | Supplier Intelligence | 11.5 |
| `/actions` | Action / Approval Centre | 11.6 |
| `/assurance-lab` | Assurance Lab | 11.7 |
| `/trust-centre` | Trust Centre | 11.8 |
| `/inspection-simulator` | Inspection Readiness Simulator | 11.9 |

Only **placeholder** content + a mounted `@xyflow/react` canvas with placeholder nodes is required this phase (SENT-1-07's contract: "App boots, routing scaffolded... React Flow canvas mounted with placeholder nodes"). The persistent red banner (`"PROTOTYPE — SYNTHETIC DATA — NOT VALIDATED FOR PRODUCTION GxP USE"`, Section 11.1) is cheap to add now and is explicitly called out as part of the Command Centre spec — reasonable to include in the skeleton even though full dashboard wiring is out of scope.

### Tailwind v4 setup change (State of the Art)

Tailwind v4 (current, 4.3.4) removes the `tailwind.config.js` + PostCSS + `@tailwind base/components/utilities` directive pattern that older tutorials (and possibly Claude's own training data) assume. Current pattern: install `tailwindcss` + `@tailwindcss/vite`, register the plugin in `vite.config.ts`, and add a single `@import "tailwindcss";` line to the main CSS file — no config file required to start [CITED: tailwindcss.com/docs "Installing Tailwind CSS with Vite" — official docs, checked live 2026-08-20].

```ts
// vite.config.ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
})
```
```css
/* src/index.css */
@import "tailwindcss";
```

## WebSocket Pattern

**Source: Bible Section 12 API table (line 1415: `WS | /api/copilot/stream/{session_id} | None | Stream | Streams agent execution state`) and Section 11.2 [VERIFIED: GxP-Sentinel-Project-Bible-v6.md:1370,1378,1415, read directly this session].** SENT-1-08's contract for this phase is minimal: "accepts a connection and echoes a test event end-to-end (backend → browser)" — a real echo, not real LangGraph `astream_events` streaming (that requires the real agents from Phase 3).

**Backend (FastAPI native WebSocket, no extra package needed — `fastapi`/`starlette` ships `WebSocket` support):**
```python
from fastapi import WebSocket, WebSocketDisconnect

@app.websocket("/api/copilot/stream/{session_id}")
async def copilot_stream(websocket: WebSocket, session_id: str):
    await websocket.accept()
    try:
        await websocket.send_json({"event": "connected", "session_id": session_id})
        while True:
            data = await websocket.receive_text()
            await websocket.send_json({"event": "echo", "payload": data})
    except WebSocketDisconnect:
        pass
```

**Frontend (native browser `WebSocket`, no library needed for the skeleton):**
```ts
const ws = new WebSocket(`ws://localhost:8000/api/copilot/stream/${sessionId}`)
ws.onopen = () => ws.send("test-event")
ws.onmessage = (evt) => console.log("received", JSON.parse(evt.data))
```

No auth/session validation is required at this stage (`session_id` is a path param, not yet checked against the `sessions` table — that's consistent with CONTEXT.md's deferred scope; C2 RBAC doesn't gate anything until Phase 5). Full LangGraph `astream_events` wiring (Section 11's "State management utilizes WebSockets to stream LangGraph `astream_events` directly to the browser") is Phase 6 scope (Product Experience), not this phase.

## Plan / Wave Decomposition Recommendation

Respecting BRANCHING.md §4's file-ownership table (each ticket owns disjoint paths, so collision is already prevented by allocation) and the explicit dependencies (`Sentinel-Build-Map.md:37`: "SENT-1-04 depends on SENT-1-03. SENT-1-06 depends on SENT-1-05."):

**Wave 1 — no dependencies, 4 fully parallel plans:**
- SENT-1-01 (Postgres DDL → `infra/postgres/initdb/`)
- SENT-1-03 (10 Rego rules + `opa test` fixtures → `policies/`) — Critical review
- SENT-1-05 (FastAPI skeleton + Pydantic schemas → backend app entrypoint + schema modules)
- SENT-1-07 (React/Vite/Tailwind shell → `frontend/`)

**Wave 2 — depends on Wave 1 outputs, 4 parallel plans:**
- SENT-1-02 (seed data → `infra/postgres/seed/`) — depends on SENT-1-01's schema existing [ASSUMED: not stated explicitly as a Build-Map dependency, but seed INSERTs target tables that must already exist; low risk, mechanically obvious]
- SENT-1-04 (OPA client wiring → backend OPA client module) — explicit dependency on SENT-1-03
- SENT-1-06 (LangGraph `StateGraph` skeleton → backend StateGraph module) — explicit dependency on SENT-1-05
- SENT-1-08 (WebSocket route + client → backend WS route module + frontend WS client module) — depends on both SENT-1-05 (an app to attach a route to) and SENT-1-07 (a frontend to attach a client to) [ASSUMED: same reasoning as SENT-1-02 — not stated explicitly, but mechanically required]

**Wave 3 — benefits from all of the above existing:**
- SENT-1-09 (CI test runner → `.github/workflows/`) — P1, wires `pytest` + `opa test` + `/api/health` curl check into CI; most useful once there are real test commands to invoke from Waves 1-2

This mirrors Phase 1's own pattern (`.planning/phases/01-environment/`, 4 plans across 3 waves) and keeps every plan's file set disjoint from every other plan's per BRANCHING.md — no two plans in the same wave touch the same path.

## Common Pitfalls

### Pitfall 1: Rego v0 vs v1 syntax mismatch (see "Rego Policy Layer" above)
**What goes wrong:** Pasting the Bible's `violation[{...}] { ... }` rules verbatim into a `.rego` file fails `opa test` / `opa check` on OPA 1.19.1 with `"contains" keyword is required for partial set rules`.
**Why it happens:** The Bible's code sample predates OPA's v1.0 default-syntax change; the running image (`openpolicyagent/opa:1.19.1-debug`, already certified in Phase 1) defaults to Rego v1.
**How to avoid:** Use `contains { ... } if { ... }` for every one of the 10 rules (see corrected example above). Logic stays identical to the Bible.
**Warning signs:** `opa test` output naming `if` or `contains` keyword errors; the REST evaluation returning a parse error instead of a `result` array.

### Pitfall 2: `_ns` BIGINT columns vs `time.now_ns()` units
**What goes wrong:** If seed data or Python-side inserts ever use millisecond or second epoch instead of nanosecond epoch, every Rego date-diff rule silently miscalculates (off by 10^6 or 10^9).
**Why it happens:** The `_ns` suffix is easy to skim past; Python's common epoch helpers (`time.time()`, `datetime.timestamp()`) return seconds, not nanoseconds.
**How to avoid:** Copy the seed data's literal integers verbatim (they're already correct nanosecond epochs, e.g. `1709251200000000000`); if backend code ever needs to generate a new `_ns` value, multiply seconds by `1_000_000_000`.
**Warning signs:** A Rego rule that should trigger for seeded "overdue" data doesn't, or triggers for data that shouldn't be overdue.

### Pitfall 3: React Flow package name drift
**What goes wrong:** Installing `react-flow-renderer` (the Bible's literal Section 10.3 name) installs a package whose own `npm view ... deprecated` field points you elsewhere; installing `reactflow` installs the still-working but now-legacy v11-era name.
**Why it happens:** The library rebranded twice (`react-flow-renderer` → `reactflow` → `@xyflow/react`), and the Bible was written before (or without tracking) the latest rename.
**How to avoid:** `npm install @xyflow/react`, import `{ ReactFlow }` (named import in v12, not a default import as in v11's `reactflow`).
**Warning signs:** `npm install react-flow-renderer` printing a deprecation warning at install time; import errors if v12's named-import style is mixed with v11-style default-import code copied from older tutorials.

### Pitfall 4: Tailwind v3-era scaffolding instructions
**What goes wrong:** Following an `npx tailwindcss init -p` + `tailwind.config.js` content-glob + `@tailwind base; @tailwind components; @tailwind utilities;` setup (the v3 pattern) against the installed v4 package silently produces unstyled output — v4 doesn't use those directives.
**Why it happens:** v3-era tutorials/training data are far more numerous than v4's (Jan 2025+) docs.
**How to avoid:** Use the `@tailwindcss/vite` plugin + `@import "tailwindcss";` pattern shown above; skip `tailwind.config.js` unless a specific v4 `@theme` customization is needed.
**Warning signs:** Tailwind utility classes present in JSX/HTML but rendering with zero visual effect; no build errors (the mismatch fails silently).

### Pitfall 5: Running `pip install` into the global Anaconda environment
**What goes wrong:** This machine's `pip` (25.3) resolves to `C:\Anaconda3\Lib\site-packages\pip` — a global environment shared across all projects on the machine, not a project-scoped one.
**Why it happens:** No project-local virtualenv exists yet in `backend/` (the tier is currently empty).
**How to avoid:** Create `backend/.venv` (or use `uv`/`poetry` if the planner prefers) before installing any backend dependency; document the activation step in `backend/README.md`.
**Warning signs:** `pip show fastapi` reporting a version the project never pinned, or version conflicts with an unrelated project sharing the same global Anaconda env.

### Pitfall 6: Two different `AgentFinding`/`ActionProposal` shapes
**What goes wrong:** The Bible defines `AgentFinding`/`ActionProposal` **twice** — once as `pydantic.BaseModel` (Section 4.3, for API request/response validation) and once as `typing.TypedDict` (Section 1.2, for the LangGraph state schema). They have the same field names but are not interchangeable Python types.
**Why it happens:** LangGraph state schemas conventionally use `TypedDict` (cheap, no validation overhead per graph step) while FastAPI route models conventionally use `BaseModel` (runtime validation at the API boundary) — this is a deliberate, common pattern, not a Bible inconsistency, but easy to collapse into a single class by mistake.
**How to avoid:** Keep `app/schemas.py` (Pydantic `BaseModel` versions) and `app/graph/state.py` (TypedDict versions) as separate definitions, as laid out in "FastAPI Skeleton" and "LangGraph StateGraph Skeleton" above. If a single source of truth is wanted later, convert at the API boundary explicitly (`AgentFinding(**typed_dict_instance)`), don't import one across tiers.
**Warning signs:** `mypy`/IDE errors about `TypedDict` not being a `BaseModel` subclass if code tries to pass a graph-state finding directly into a FastAPI response model.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Node.js | Frontend (Vite/React), `infra/health-check.sh` port probes | ✓ | v24.18.0 [VERIFIED: `node --version`] | — |
| npm | Frontend package install | ✓ | 9.6.3 [VERIFIED: `npm --version`] | — |
| Python | Backend (FastAPI/LangGraph) | ✓ | 3.13.9 (via `python`, not `python3`, on this shell's PATH) [VERIFIED: `python --version`] | Use `python`, not `python3`, in any scripts/docs this phase writes for Windows/Git-Bash contributors |
| pip | Backend package install | ✓ (global Anaconda env) | 25.3 [VERIFIED: `pip --version`] | Create a project-local venv per Pitfall 5 above rather than relying on the global environment |
| Docker / Docker Compose | Postgres/Qdrant/OPA (already running per Phase 1) | Not probed successfully from this shell's Git-Bash PATH (`docker` not found) — but independently certified healthy in `infra/README.md:65-91` from Phase 1's own work | — | Services are managed via Docker Desktop outside this Bash tool's PATH; no action needed for this phase since Phase 1 already stood up and certified postgres/qdrant/opa. If a fresh clone genuinely lacks Docker, that blocks the entire phase (documented in root README's Prerequisites already) |

**Missing dependencies with no fallback:** none identified that block this specific phase's new work (backend/frontend toolchains are all present; Docker unavailability would block everything but is a pre-existing, already-documented prerequisite, not new to this phase).

**Missing dependencies with fallback:** `docker` CLI not resolvable from this research session's Git-Bash shell PATH — noted above with fallback reasoning; does not block planning since the services are already certified running from Phase 1.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework (backend) | `pytest` [ASSUMED — not named by the Bible/CLAUDE.md, but the de facto FastAPI-ecosystem default; low risk] |
| Framework (policies) | `opa test` (built into the `opa` binary — no separate install) |
| Framework (frontend) | none yet — `vitest` recommended [ASSUMED] if the planner wants automated frontend coverage this phase; otherwise a manual WS-echo check suffices for SENT-1-08's contract |
| Config file | none exist yet — Wave 0 gap |
| Quick run command | `pytest backend/tests -x` / `opa test policies/` |
| Full suite command | same (no suite is large enough yet to warrant a separate "full" pass) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ENV-02 | Schema loads, FKs verified | integration | `pytest backend/tests/test_schema.py -x` (connect to `postgres:5432`, assert all 20 tables + FK constraints present via `information_schema`) | ❌ Wave 0 |
| ENV-03 | Seed data present, including injected findings | integration | `pytest backend/tests/test_seed.py -x` (assert `DOC-2026-OM-99` status=`DRAFT`, `SUP-2026-01` name=`DataSync Solutions`, etc.) | ❌ Wave 0 |
| ENV-04 | `/api/health` returns 200 | unit | `pytest backend/tests/test_health.py -x` | ❌ Wave 0 |
| POL-01 | All 10 Rego rules pass `opa test` | unit | `opa test policies/` | ❌ Wave 0 |
| POL-02 | `evaluate_opa_policy()` calls real REST endpoint | integration | `pytest backend/tests/test_opa_client.py -x` (live call against the running `opa` container) | ❌ Wave 0 |
| ORC-01 | `StateGraph` compiles, correct topology | unit | `pytest backend/tests/test_graph_topology.py -x` (assert `compiled_graph.get_graph().edges` matches the 11-node topology; `ainvoke` completes) | ❌ Wave 0 |
| UI-01 | Frontend boots, routes present, React Flow mounted | manual / smoke | `npm run dev` + manual browser check (or `vitest` route-render smoke test if the planner opts in) | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest backend/tests -x` (backend tasks) / `opa test policies/` (Rego tasks)
- **Per wave merge:** run both, plus a manual `curl localhost:8000/api/health` and `npm run build` (frontend) sanity pass
- **Phase gate:** all of the above green, plus the raw `curl` OPA REST call from "Rego Policy Layer" above

### Wave 0 Gaps
- [ ] `backend/tests/test_health.py`, `test_schema.py`, `test_seed.py`, `test_opa_client.py`, `test_graph_topology.py` — none exist yet
- [ ] `backend/tests/conftest.py` — shared fixtures (DB connection pointed at `127.0.0.1:5432`, OPA base URL `http://localhost:8181`)
- [ ] `policies/rules_test.rego` — Rego fixtures (positive + negative per rule, 20 minimum for SENT-1-03's Critical bar)
- [ ] Framework install: `pip install pytest` into a project-local `backend/.venv` (none exists yet)
- [ ] `.github/workflows/ci.yml` — doesn't exist yet (`.github/workflows/` directory itself doesn't exist); this is literally SENT-1-09's own deliverable

## Security Domain

`security_enforcement: true`, `security_asvs_level: 1`, `security_block_on: "high"` per `.planning/config.json`. This phase is scaffolding-only — no auth, no RBAC decision path, and no cryptographic chain logic are in scope (those are explicitly Phase 5 / Stage 4, per CONTEXT.md's deferred-scope note and ROADMAP.md's SAFE-01/SAFE-02/AUDIT-01 mapping). ASVS applicability is accordingly narrow this phase:

### Applicable ASVS Categories

| ASVS Category | Applies this phase | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | No | Deferred to Phase 5 (C2 RBAC, SENT-4-01) — no login/session logic exists yet; `session_id` in the WS route is an unvalidated path param this phase, by design |
| V3 Session Management | No | `sessions` table exists (empty) per DDL; no session-issuing/validating logic yet |
| V4 Access Control | No | Deferred to Phase 5 (C2 permission matrix) — every route in this phase is open, matching SENT-1-05/1-08's "skeleton" contract |
| V5 Input Validation | Yes | Pydantic `BaseModel` validation at every FastAPI route boundary (Section 4.3 models) — this is already the standard control and requires no extra library |
| V6 Cryptography | No | Deferred to Phase 5 (hash-chained audit trail, SENT-4-06) — `audit_events.event_hash`/`previous_event_hash` columns exist in the DDL this phase but no hashing logic runs yet |

### Known Threat Patterns for this stack (forward-looking, informational — not this phase's responsibility to mitigate)

| Pattern | STRIDE | Standard Mitigation | When mitigated |
|---------|--------|---------------------|-----------------|
| Prompt injection via retrieved document content or WS input | Tampering / Elevation of Privilege | Deterministic entropy + regex detection, zero LLM in the decision path (Bible Section 2, C2) | Phase 5 (SENT-4-02) |
| Unauthenticated WebSocket accepting arbitrary `session_id` | Spoofing | Session validation against the `sessions`/`users` tables before accepting the connection | Phase 5 (once C2 RBAC exists) — **acceptable gap for this phase's skeleton**, since the ticket contract explicitly only requires "accepts a connection and echoes a test event" |
| SQL injection via raw DDL/seed scripts | Tampering | This phase's DDL/seed are static, developer-authored SQL files run once at container init — no user input reaches SQL in this phase; parameterized queries become relevant once agents query the DB dynamically (Phase 3) | Not applicable this phase |
| Secrets in `.env` committed to git | Information Disclosure | `.env.example` (placeholder-only) is already the established Phase 1 pattern (`docker-compose.yml:11` fails loud if `POSTGRES_PASSWORD` is unset rather than defaulting); backend env vars (e.g. `DATABASE_URL`, future LLM API keys) should follow the same `.env.example` placeholder convention, added in its own small PR per BRANCHING.md §5 shared-file protocol | This phase, when adding new env vars |

No new subsystem or library is required to satisfy V5 for this phase — Pydantic's own validation is the standard control and is already mandated by SENT-1-05's contract.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `pytest` is the intended backend test framework | Standard Stack, Validation Architecture | Low — not specified by Bible/CLAUDE.md; `pytest` is overwhelmingly the FastAPI-ecosystem default, and switching frameworks later is cheap since no tests exist yet |
| A2 | `vitest` is the intended frontend test framework, if the planner opts into automated frontend tests this phase | Standard Stack, Validation Architecture | Low — same reasoning; Vite's own scaffolding docs pair it with Vitest by default |
| A3 | SENT-1-02 (seed data) depends on SENT-1-01 (schema) being applied first | Plan/Wave Decomposition | Low — mechanically obvious (INSERT targets must exist as tables first) but not stated as an explicit Build-Map dependency; wrong wave placement would just fail loudly at seed time, not silently |
| A4 | SENT-1-08 (WebSocket) depends on both SENT-1-05 (backend app) and SENT-1-07 (frontend shell) | Plan/Wave Decomposition | Low — same reasoning as A3; a route/client can't attach to an app/shell that doesn't exist yet |
| A5 | TypeScript version left to `npm create vite@latest ... --template react-ts`'s own current default, not independently version-pinned | Standard Stack | Low — CLAUDE.md only says "TypeScript," no version constraint stated anywhere in the Bible |
| A6 | Rule head syntax fix (`contains`/`if`) is purely mechanical and preserves all 10 rules' logic/citations exactly | Rego Policy Layer | Medium if wrong — this is the single highest-leverage claim in this document, since it's the one place this research diverges from a literal transcription of the Bible. Verified independently against OPA's own official v1.0 upgrade docs (not training-data recall alone), but the planner should still run `opa test` immediately after transcription as the actual proof, not trust this claim alone |

## Open Questions

1. **Should Phase 2 containerize `backend/`/`frontend/` in `docker-compose.yml`, or run them via host `uvicorn`/`npm run dev`?**
   - What we know: `docker-compose.yml` currently only has `postgres`/`qdrant`/`opa`; BRANCHING.md §5 treats `docker-compose.yml` changes as their own small cross-cutting PR, separate from any Stage 1 ticket.
   - What's unclear: Whether the phase gate ("`/api/health` returns 200") is meant to be checked against a host-run dev server or a containerized one.
   - Recommendation: Run both host-side for this phase (`uvicorn app.main:app --reload`, `npm run dev`) — matches the "skeleton" framing of every Stage 1 ticket contract and avoids an unplanned `docker-compose.yml` PR. Revisit containerization when a real deploy/demo-reset story (Stage 6, SENT-6-06) needs it.

2. **Does SENT-1-09 (CI) belong in this phase's Wave 3, or is it acceptable to defer slightly since it's P1 not P0?**
   - What we know: Build-Map marks it P1 (only P1 ticket in Stage 1); its contract says "Every PR from Stage 2 onward runs schema + Rego + basic API tests automatically" — implying it needs to exist before Stage 2 (Phase 3) starts, not necessarily before Phase 2's own gate is met.
   - What's unclear: Whether the phase 2 gate itself requires CI to exist, or just requires the underlying tests it would run.
   - Recommendation: Keep it in Wave 3 of this phase (as recommended above) rather than deferring to Phase 3, since "every PR from Stage 2 onward" reads as a hard requirement that CI exists by the time Stage 2 work starts.

## Sources

### Primary (HIGH confidence — read directly this session)
- `GxP-Sentinel-Project-Bible-v6.md:97-196` — Section 1.2, LangGraph StateGraph definition
- `GxP-Sentinel-Project-Bible-v6.md:198-229` — Section 1.3, Deterministic-First Decision Table
- `GxP-Sentinel-Project-Bible-v6.md:406-579` — Section 3.3/3.4, all 10 Rego rules + Python OPA integration
- `GxP-Sentinel-Project-Bible-v6.md:587-828` — Section 4.1, full Postgres DDL
- `GxP-Sentinel-Project-Bible-v6.md:834-937` — Section 4.3, Pydantic models
- `GxP-Sentinel-Project-Bible-v6.md:939-997` — Section 5, synthetic seed data
- `GxP-Sentinel-Project-Bible-v6.md:1189-1243` — Section 8, multi-provider LLM router config
- `GxP-Sentinel-Project-Bible-v6.md:1368-1420` — Section 11 (all page subsections) and Section 12 (API table)
- `Sentinel-Build-Map.md:22-37` — Stage 1 ticket table (SENT-1-01 through SENT-1-09) + dependency note
- `BRANCHING.md:31-59` — Stage 1 file-ownership table, merge rules, Critical-ticket list
- `docker-compose.yml` — confirms actual running OPA image (`openpolicyagent/opa:1.19.1-debug`) vs Bible's example config (`openpolicyagent/opa:0.63.0`)
- `infra/README.md:65-99` — certified environment digests, confirming OPA 1.19.1-debug is genuinely what's running
- `backend/README.md`, `frontend/README.md`, `policies/README.md` — Phase 1's own scaffolding notes on tier ownership
- `.planning/REQUIREMENTS.md:10-15,17-20,24` — ENV-02/03/04, POL-01/02, ORC-01 requirement text
- `.planning/ROADMAP.md:43-56` — Phase 2 goal, ticket context, success criteria

### Secondary (MEDIUM confidence — official docs / registries, verified live this session)
- `pip index versions <pkg>` (fastapi, pydantic, langgraph, langchain-core, httpx, uvicorn) — PyPI, 2026-08-20
- `npm view <pkg> version` (vite, react, tailwindcss, reactflow, @xyflow/react) — npm registry, 2026-08-20
- `npm view reactflow deprecated` / `npm view react-flow-renderer deprecated` — npm registry deprecation notices, 2026-08-20
- openpolicyagent.org/docs/v0-upgrade — official OPA v1.0 upgrade guide (Rego v1 `contains`/`if` requirement)
- reactflow.dev/learn/troubleshooting/migrate-to-v12, xyflow.com/blog — official React Flow → @xyflow/react rename
- tailwindcss.com/docs — official Tailwind v4 + Vite installation guide
- docs.langchain.com/oss/python/migrate/langgraph-v1 — official LangGraph 1.0 migration guide (core primitives unchanged)

### Tertiary (LOW confidence — flagged in Assumptions Log)
- `pytest`/`vitest` as the intended test frameworks (not named by any project source, standard-ecosystem inference only)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — every pinned version verified live against PyPI/npm this session; every package name cross-checked against the project's own CLAUDE.md/Bible or official rename docs
- Architecture (schema/StateGraph/API): HIGH — transcribed directly from Bible sections read in full this session, with line-range citations
- Rego syntax compatibility: HIGH — the single most consequential finding, independently verified against OPA's own official upgrade documentation, not training-data recall
- Pitfalls: HIGH — each pitfall traces to a specific verified fact (registry deprecation notice, official migration doc, or a direct read of the DDL/seed data)
- Wave/plan decomposition: MEDIUM — explicit dependencies (SENT-1-04→03, SENT-1-06→05) are directly cited; the remaining two inferred dependencies (SENT-1-02, SENT-1-08) are reasonable engineering inference, flagged in the Assumptions Log

**Research date:** 2026-08-20
**Valid until:** ~30 days for the Bible-derived content (stable, versioned source-of-truth document); ~7-14 days for the pinned package versions and the OPA/Tailwind/React-Flow ecosystem findings (fast-moving npm/PyPI landscape) — re-verify version numbers if planning is delayed past early September 2026.
