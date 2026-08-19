# Phase 1: Environment - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-08-19
**Phase:** 1-Environment
**Areas discussed:** Repo structure, Branching convention, Docker Compose specifics, Health check definition

---

## Repo Structure

| Option | Description | Selected |
|--------|-------------|----------|
| backend/ frontend/ policies/ infra/ | Matches the Bible's component split; clean ownership boundaries for Rule 10 | ✓ |
| Single flat app/ with subfolders | One app/ dir with api/, ui/, rego/ subfolders — blurs ownership boundaries | |
| You decide | Let Claude choose | |

**User's choice:** backend/ frontend/ policies/ infra/
**Notes:** None.

| Option | Description | Selected |
|--------|-------------|----------|
| docker-compose.yml at repo root | Root-level compose file is the single entry point, matches the Bible's one-liner | ✓ |
| docker-compose.yml inside infra/ | Keeps root clean but requires an extra -f flag | |

**User's choice:** docker-compose.yml at repo root
**Notes:** None.

---

## Branching Convention

| Option | Description | Selected |
|--------|-------------|----------|
| Trunk-based, short-lived branch per ticket | One branch per SENT-<stage>-<number> ticket, merged via PR | ✓ |
| Per-stage long-lived branches | One branch per Build-Map stage, higher collision risk | |
| Direct to main, no branches | Hackathon speed, only viable without parallel agent work | |

**User's choice:** Trunk-based, short-lived branch per ticket
**Notes:** None.

---

## Docker Compose Specifics

| Option | Description | Selected |
|--------|-------------|----------|
| Pin exact tags | Reproducible across the 20-day hackathon, avoids surprise breaking changes | ✓ |
| Track latest/major-only tags | Gets patches automatically but risks unexpected breakage | |

**User's choice:** Pin exact tags
**Notes:** None.

| Option | Description | Selected |
|--------|-------------|----------|
| Named Docker volumes | Survives `docker-compose down`, matches later demo-state-reset script target | ✓ |
| No persistence (ephemeral containers) | Simpler for Phase 1 alone, wrong fit for later phases' seed data | |

**User's choice:** Named Docker volumes
**Notes:** None.

---

## Health Check Definition

| Option | Description | Selected |
|--------|-------------|----------|
| Native healthcheck blocks per service | pg_isready / Qdrant health endpoint / OPA health endpoint, scriptable "all green" | ✓ |
| No healthcheck blocks, verify manually | Faster to write but no scriptable signal, weaker fit for Gate criterion | |

**User's choice:** Native healthcheck blocks per service
**Notes:** None.

---

## Claude's Discretion

- Exact image tag versions (specific Postgres 16.x patch, Qdrant version, OPA version)
- Exact healthcheck interval/timeout/retries values
- `.env` / secrets handling mechanics for the compose file (local dev only, no real secrets yet)

## Deferred Ideas

None — discussion stayed within Phase 1 scope.
