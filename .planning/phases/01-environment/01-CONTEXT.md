# Phase 1: Environment - Context

**Gathered:** 2026-08-19
**Status:** Ready for planning

<domain>
## Phase Boundary

The environment stands up from one command — `docker-compose up -d postgres qdrant opa` brings Postgres, Qdrant, and OPA up healthy on ports 5432/6333/8181 — on a repo structure and branching convention ready for Stage 1 work (Build-Map Stage 0 / ROADMAP.md Phase 1, requirement ENV-01). No application code, schema, or agent logic is in scope — that's Phase 2 onward.

</domain>

<decisions>
## Implementation Decisions

### Repo Structure
- **D-01:** Top-level layout is `backend/`, `frontend/`, `policies/`, `infra/` — matches the Bible's component split (FastAPI+LangGraph app, React/Vite app, Rego rules, docker-compose/configs) and gives clean ownership boundaries per ticket for Rule 10.
- **D-02:** `docker-compose.yml` lives at repo root so `docker-compose up -d postgres qdrant opa` works with zero path args, matching the Bible's documented one-liner. Service-specific config (Postgres init scripts, OPA policy bundle mount pointing at `policies/`) lives under `infra/`.

### Branching Convention
- **D-03:** Trunk-based development with a short-lived branch per ticket (`SENT-<stage>-<number>`), branched from `main`, merged via PR when the ticket's contract is met. Satisfies Rule 10 (no two agents editing the same critical file) by keeping ticket scope == branch scope, including for Critical-review tickets.

### Docker Compose Specifics
- **D-04:** Docker images pinned to exact tags (e.g. `postgres:16`, a specific `qdrant/qdrant` version tag, a specific OPA image tag) rather than `latest`/major-only tags — reproducibility across the 20-day build, no surprise breaking changes mid-hackathon. — **Reversibility:** reversible — changing a pinned tag later is a one-line compose edit.
- **D-05:** Postgres and Qdrant data persist across `docker-compose down` via named Docker volumes (`postgres_data`, `qdrant_data`). Not wiped unless `down -v` is used explicitly. This is also the target the Stage 6 demo-state-reset script (SENT-6-06) will act on later.

### Health Checks
- **D-06:** Each service defines a native `healthcheck:` block in `docker-compose.yml` — `pg_isready` for Postgres, an HTTP check against Qdrant's health endpoint, an HTTP check against OPA's health endpoint — with interval/retries, so `docker-compose ps` shows healthy/unhealthy directly. This gives a scriptable "all green" signal matching ENV-01's acceptance criterion verbatim, and sets up the later CI test runner (SENT-1-09).

### Claude's Discretion
- Exact image tag versions (specific Postgres 16.x patch, Qdrant version, OPA version) — pick current stable versions at implementation time.
- Exact healthcheck interval/timeout/retries values.
- `.env` / secrets handling mechanics for the compose file (no GxP secrets exist yet at this phase — local dev only).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Architecture & ports
- `AegisX-AI-Project-Bible-v6.md` — source of truth; fixed local ports (Postgres 5432, Qdrant 6333, OPA 8181, FastAPI 8000, Vite 3000) and Section 1.3 deterministic-first decision table
- `AegisX-Build-Map.md` — Stage 0 ticket contracts: SENT-0-01 (repo scaffold + branching convention), SENT-0-02 (Docker Compose: postgres/qdrant/opa)

### Process rules
- `CLAUDE.md` §"Working rules that apply to Claude Code here" — Rule 10 (no two agents editing the same critical file), which the branching convention (D-03) exists to satisfy

### Roadmap / requirements
- `.planning/ROADMAP.md` — Phase 1 goal and success criteria
- `.planning/REQUIREMENTS.md` — ENV-01

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- None — repository is currently a specification vault (Obsidian vault) with no application source, build tooling, or tests. Phase 1 creates the scaffold from scratch.

### Established Patterns
- None yet established in code. Governing patterns come from the Bible and CLAUDE.md only.

### Integration Points
- `infra/` compose config mounts `policies/` for the OPA policy bundle (used starting Phase 2, SENT-1-04) — plan the mount path now even though no Rego files exist yet.

</code_context>

<specifics>
## Specific Ideas

No specific requirements beyond the decisions above — user deferred exact versions/tags and secrets mechanics to Claude's discretion.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within Phase 1 scope. (Demo-state-reset scripting, CI test runner, and schema/seed work are already correctly scoped to later phases per ROADMAP.md and were not raised as in-scope-now by the user.)

</deferred>

---

*Phase: 1-Environment*
*Context gathered: 2026-08-19*
