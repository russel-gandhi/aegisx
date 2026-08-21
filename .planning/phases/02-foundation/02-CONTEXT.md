# Phase 2: Foundation - Context

**Gathered:** 2026-08-20
**Status:** Ready for planning
**Mode:** Auto-generated (infrastructure phase — no user-facing behavior; smart discuss skipped per success-criteria analysis)

<domain>
## Phase Boundary

The full schema, seed data, policy layer, API skeleton, orchestration skeleton, frontend shell, and WebSocket pattern are all in place, giving Phase 3's real agents a real substrate to build on. (Build-Map Stage 1, Gate: "schema loads, seed data present, one Rego rule evaluates via raw OPA REST call, API skeleton returns 200 on `/api/health`.")

This phase implements Build-Map Stage 1 tickets SENT-1-01 through SENT-1-09 as described in `AegisX-Build-Map.md`. Ticket contracts there are authoritative for scope; when they disagree with `AegisX-AI-Project-Bible-v6.md`, the Bible wins (CLAUDE.md rule).

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion
All implementation choices are at Claude's discretion, guided by:
- The Bible's DDL, Pydantic models, and Rego rule specs (Section references in AegisX-Build-Map.md ticket contracts) are the source of truth for schema/API shape — do not invent alternative schemas.
- BRANCHING.md §4 Stage 1 file ownership table governs which paths belong to which ticket — respect it so parallel plan waves in this phase don't collide on files.
- Deterministic-first constraint (CLAUDE.md, Bible §1.3) applies from this phase forward: no LLM evaluates compliance/RBAC/injection decisions, even in skeleton form.
- SENT-1-03 (Rego rules) and SENT-1-06 (LangGraph StateGraph design) are Critical-review-level tickets per BRANCHING.md — plan and execute with correspondingly stronger test coverage (unit + negative + edge-case + integration), not a smoke test.

</decisions>

<code_context>
## Existing Code Insights

Repo currently has: `docker-compose.yml` (postgres/qdrant/opa services, all healthy), `infra/` (health-check, persistence verify, Dockerfiles), tier scaffolds `backend/`, `frontend/`, `policies/` with placeholder READMEs from phase 01-02, and `BRANCHING.md` allocating Stage 1 file ownership. No application source exists yet inside `backend/`, `frontend/`, or `policies/` beyond their README placeholders.

### Reusable Assets
- `docker-compose.yml` — Postgres/Qdrant/OPA already up; this phase adds application services (backend API) on top, not new infra services.
- `infra/health-check.sh` — extend or reuse pattern for `/api/health` once the API skeleton exists.

### Established Patterns
- Root Compose file + env interpolation + named volumes + native healthchecks + loopback-only publish, established in phase 1.
- Tier READMEs (`backend/README.md`, `frontend/README.md`, `policies/README.md`) as the self-explanatory entry point per tier — extend rather than replace.

### Integration Points
- `policies/` — Rego sources land here per BRANCHING.md.
- `backend/` — FastAPI app, Pydantic models, OPA client, LangGraph StateGraph module.
- `frontend/` — Vite/React/TS shell, Tailwind, React Flow canvas.

</code_context>

<specifics>
## Specific Ideas

No specific requirements beyond the Bible/Build-Map ticket contracts — this is a scaffolding phase and the ticket contracts in AegisX-Build-Map.md are the spec.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope. Real (non-stub) agent logic, C1 confidence scoring, and the evidence graph are explicitly Phase 3+ scope, not this phase.

</deferred>
