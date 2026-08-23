# Phase 5: Safety & Remediation - Context

**Gathered:** 2026-08-23
**Status:** Ready for planning

<domain>
## Phase Boundary

Every request is deterministically gated by RBAC and injection detection before it reaches an agent (C2); a proposed GxP-relevant write sits `PENDING` until a human approves it, and the approval is audit-logged (C3 Action Gateway + A7 Remediation); and a tampered audit row is detected by `verify_chain()` (hash-chained audit trail). Zero LLM in any of the three decision paths (RBAC, injection detection, tamper detection). Maps to Build-Map Stage 4 (tickets SENT-4-01 through SENT-4-08).

</domain>

<decisions>
## Implementation Decisions

### Identity and RBAC source
- **D-01:** No real authentication exists in this codebase yet (confirmed absent as of Phase 4's T-04-05 threat disposition). For this hackathon build, identity arrives via a fixed demo-identity context: a role selector (not a login form) lets the operator pick one of the three Bible-defined roles — `IT System Manager`, `QA-Compliance`, `Auditor` — and every request carries `user_id` and `role` derived from that selection. — **Reversibility:** one-way — **rationale:** every C2/C3 handler, the audit event schema, and the frontend request layer will all read identity from this mechanism; swapping to real auth later (JWT/session) means touching every one of those call sites, not just adding a login page.

### Human approval flow
- **D-02:** All remediation actions require explicit human approval — no auto-execution path exists anywhere in this phase. Flow is fixed as: A7 produces an `ActionProposal` → C3 Action Gateway routes/validates it → status `PENDING_APPROVAL` in `action_proposals` → human approves via the Approval Centre UI → action executes → a hash-chained `AuditEvent` is recorded. This is the literal shape of Build-Map ticket SENT-4-04 and Bible Section 11.6 — not a new design, just confirmed as the only flow (no shortcut/auto-approve mode for the demo).

### A7 Remediation trigger point
- **D-03:** A7 Remediation only runs on an explicit user action — a "Generate CAPA" button — never automatically after a finding comes back with `INSUFFICIENT_EVIDENCE` or a failing deterministic check. The normal C1-verified query/finding flow (Phase 3's hero loop, Phase 4's Assurance Cards) stays exactly as built; A7 is an opt-in follow-up action a user takes on a finding they're already looking at, not a side effect of asking a question. — **Reversibility:** reversible — this is a UI/trigger-wiring choice, not a schema or contract change; switching to auto-trigger later only touches the call site that invokes A7.

### C2 gating scope
- **D-04:** C2 (RBAC + injection detection) applies to all write-capable endpoints — anything that can create, approve, execute, or mutate state (the future `/api/copilot/query`, action-approval, and action-execution routes). Read-only evidence/query endpoints — the existing Phase 4 routes (`GET .../evidence-graph`, `GET .../blast-radius`, `GET .../assurance-cards`) and the Phase 4 `POST .../evidence-graph/rebuild` — do **not** require C2 action gating; they stay as they are. This confirms C2 sits in front of the write/action surface this phase is building, not retroactively in front of already-shipped read endpoints. — **Reversibility:** costly — if this boundary turns out wrong (e.g. rebuild should also be RBAC-gated), moving it means adding middleware to already-shipped, tested routes and re-verifying them.

### Claude's Discretion
- Exact request-carrier mechanism for `user_id`/`role` (header vs. query param vs. request body field) — user specified the *shape* (fixed demo identity, role selector, every request carries both fields) but not the wire-level transport. Research/planning should pick the simplest mechanism consistent with the existing FastAPI/asyncpg conventions (`c1_verifier.py`'s allowlist-not-f-string discipline, `db.py`'s `acquire_pool_or_none()` degrade pattern) and the frontend's existing `frontend/src/lib/api.ts`/`ws.ts` conventions.
- Whether the role selector is a persistent app-chrome control (e.g. in `AppShell`) or scoped to the Approval Centre page — not specified; Claude's call at planning time based on where RBAC-gated actions actually originate in the UI.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Bible sections (source of truth, Rule 14)
- `AegisX-AI-Project-Bible-v6.md` §2 — C2 Policy & Safety Gateway: RBAC permission matrix (IT System Manager / QA-Compliance / Auditor), entropy + regex injection detection logic, exact jailbreak regex example
- `AegisX-AI-Project-Bible-v6.md` §2 — C3 Action Gateway: READ / DRAFT / MOCK_WRITE_LOW_RISK / GXP_RELEVANT_WRITE / PROHIBITED category routing
- `AegisX-AI-Project-Bible-v6.md` (DDL, ~line 752) — `CREATE TABLE action_proposals`
- `AegisX-AI-Project-Bible-v6.md` (DDL, ~line 761) — `CREATE TABLE audit_events`
- `AegisX-AI-Project-Bible-v6.md` (~line 868) — `class ActionProposal(BaseModel)` Pydantic contract
- `AegisX-AI-Project-Bible-v6.md` (~line 879) — `class AuditEvent(BaseModel)` Pydantic contract
- `AegisX-AI-Project-Bible-v6.md` (~line 1104) — A7 Remediation agent's ActionProposal JSON schema output contract
- `AegisX-AI-Project-Bible-v6.md` §7.1, (~lines 1142-1183) — hash-chain algorithm: `prev_hash`/`event_hash` via `hashlib.sha256`, `verify_chain()` implementation
- `AegisX-AI-Project-Bible-v6.md` §11.6 (~line 1390) — Action/Approval Centre UI: approval dialog built only from server-trusted `ActionProposal` metadata, never LLM-generated UI
- `AegisX-AI-Project-Bible-v6.md` §12 (~line 1418) — `POST /api/audit/demonstrate-tamper` endpoint contract
- `AegisX-AI-Project-Bible-v6.md` §1.3 — deterministic-first decision table (binding: zero LLM in RBAC, injection, or tamper-detection decision paths)
- `AegisX-AI-Project-Bible-v6.md` §14 — regulatory citation map (Annex 11 11.10(d)/11.10(e), ICH Q9) — cite from here only, never from model recall (Rule 13)

### Build-Map (ticket contracts)
- `AegisX-Build-Map.md` Stage 4 (lines 86-95) — SENT-4-01 through SENT-4-08 ticket contracts, owner models, priority, review level, and dependency notes (SENT-4-03/04/05 depend on SENT-2-12/C1 and SENT-1-06/graph topology; SENT-4-07 depends on SENT-4-06)

### Roadmap
- `.planning/ROADMAP.md` — Phase 5 section: goal, success criteria, `**Mode:** mvp`, dependency on Phase 3 (C1) and Phase 2 (graph/topology)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/app/schemas.py` already declares `ActionProposal`, `AuditEvent`, `CAPAProposal` (and `ConfidenceAssessment`, `AgentExecutionTrace`) as Pydantic models from earlier phase scaffolding — read these before redefining; this phase likely extends/uses them rather than creating from scratch.
- `backend/app/agents/c1_verifier.py` establishes the allowlist-not-f-string SQL discipline (`RULE_EVIDENCE_TABLES`, `_select_one_by_id_query`) that C2/C3/audit-trail code must mirror for any new table access.
- `backend/app/db.py`'s `acquire_pool_or_none()` degrade-don't-raise pattern is the established convention for every new route touching Postgres.
- `backend/app/routes/evidence_graph.py` and `backend/app/routes/findings.py` (Phase 4) are the two existing route-module examples to follow for a new `routes/` module (e.g. actions, audit).
- `frontend/src/lib/api.ts` / `frontend/src/lib/ws.ts` conventions (module docstring, `resolveApiBase`/`resolveWsBase`, `VITE_*` env fallback) are the established pattern for any new API client code this phase adds.
- The existing `/api/copilot/stream/{session_id}` WebSocket (`app/ws/copilot.py`, registered in `main.py`) is the literal channel Bible §11.6 and SENT-4-04 specify for pushing pending-proposal state live — reuse, don't build a second WS.

### Established Patterns
- `app/main.py`'s router-registration convention (`app.include_router(...)`, one line per phase, docstring updated to note the new attachment) — this phase adds at least one more router (actions/approval, possibly audit).
- Frozen module-level allowlists (`NODE_SPECS`, `RELATION_TYPES` in `evidence_graph.py`; `RULE_EVIDENCE_TABLES` in `c1_verifier.py`) are this codebase's established mechanism for "the only source of truth reaching SQL" — C2's RBAC permission matrix and injection regex list should very likely follow the same frozen-allowlist shape, not a database-driven config.

### Integration Points
- A7 Remediation consumes **already-verified (C1-passed) findings** — the Phase 3 hero loop's C1 output and Phase 4's Assurance Card data are A7's input surface; A7 must not re-verify or take an unverified LLM claim.
- The evidence graph (Phase 4, `blast_radius()`) and change-affects data (Phase 4, 04-02) are almost certainly what a CAPA narrative references when explaining what a proposed action would affect — check whether A7's `<action>` should call `blast_radius()` as part of proposal synthesis.

</code_context>

<specifics>
## Specific Ideas

No further specific UI/behavior references beyond the four decisions above — open to standard approaches for wire-level identity transport and role-selector placement (see Claude's Discretion).

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope. (Live auto-refresh for Phase 4's evidence-graph/findings pages remains logged separately in `.planning/STATE.md` Pending Todos as a Phase 6 candidate — not re-raised here.)

</deferred>

---

*Phase: 05-safety-remediation*
*Context gathered: 2026-08-23*
