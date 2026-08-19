# Walking Skeleton — GxP Sentinel

**Phase:** 1 (Environment / Build-Map Stage 0)
**Generated:** 2026-08-20

> Phase 1's goal per ROADMAP.md is environment stand-up, not application functionality. The Walking Skeleton is therefore adapted as the orchestrator directed: the thinnest end-to-end proof for an infrastructure phase is **one real reachability check per container**, not a UI-to-database round trip. The application-level skeleton (a real route, a real DB read/write, a real UI interaction) is Phase 2's Foundation work, and the "Subsequent Slice Plan" below records where each of those lands.

## Capability Proven End-to-End

A developer with a clean clone and nothing running executes one command — `docker-compose up -d postgres qdrant opa` — and all three services reach a healthy state, each independently reachable from the host on its fixed port (Postgres 127.0.0.1:5432, Qdrant 127.0.0.1:6333, OPA 127.0.0.1:8181), with data written to Postgres and Qdrant surviving a `docker-compose down` and `up` cycle.

The single assertion that answers this is `bash infra/health-check.sh`, which exits 0 only when every service is both Compose-healthy and answering on its published loopback port.

## Architectural Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Container orchestration | Docker Compose v2, single `docker-compose.yml` at the repo root | D-02 — the Bible's documented one-liner `docker-compose up -d postgres qdrant opa` must work with zero path arguments. The obsolete top-level schema-version key is omitted; Compose v2 warns on it. |
| Relational store | `postgres:16.15`, named volume `postgres_data`, init mount at `infra/postgres/initdb/` | Owns the full GxP schema from Phase 2 (Bible Section 4.1). Exact patch pin per D-04, verified live against the Docker Hub registry API. The Debian-based variant over Alpine so Phase 2 extension installs use familiar apt package names. |
| Vector store | Locally built from `infra/qdrant/Dockerfile` (`FROM qdrant/qdrant:v1.19.0` plus curl), named volume `qdrant_data` | Owns hybrid dense + BM25 retrieval from Phase 3 (A1). The derived image exists for exactly one reason: no vendor Qdrant tag ships curl, wget, or netcat, so a Compose exec healthcheck cannot run against the stock image (verified against the vendor's own Dockerfile; upstream issue qdrant/qdrant#4250 is open). |
| Policy engine | `openpolicyagent/opa:1.19.1-debug` as a sidecar, `./policies` bind-mounted read-only at `/policies` | Deterministic-first (Bible Section 1.3) requires policy evaluation to live outside any LLM-reachable process, so OPA is a peer service the backend calls over REST, never an embedded library. The `-debug` suffix is load-bearing: the default tag builds `FROM chainguard/static` — fully distroless, no shell and no HTTP client — and cannot execute any healthcheck. This supersedes the Bible Section 3.2 snippet, which pins `0.63.0` and probes with curl. |
| Health signal | Compose-native `healthcheck:` on every service plus `infra/health-check.sh` | D-06. Compose's own health state is what `docker compose ps` reports, which is the wording ENV-01's acceptance criterion uses. Waiting is delegated to `docker compose up --wait`; no hand-rolled sleep/retry loop exists anywhere. |
| Data persistence | Named Docker volumes; `down` preserves, `down -v` destroys | D-05. This is the exact seam the Stage 6 demo-state reset (SENT-6-06) will act on. Proven by `infra/verify-persistence.sh`, not assumed. |
| Secrets | `.env` (gitignored) supplies `POSTGRES_PASSWORD`; `.env.example` committed with placeholders; Compose interpolates with a fail-loud `:?` guard | No credential literal ever enters git. `up` fails with a readable message rather than silently starting on a blank password. No real GxP secrets exist at this stage — local dev only. |
| Network exposure | Every published port bound to `127.0.0.1` explicitly; Qdrant gRPC 6334 not published at all | Docker publishes to all interfaces by default. Qdrant ships with no authentication, so a bare mapping would expose the whole vector store to the LAN/VPN. |
| Directory layout | `backend/`, `frontend/`, `policies/`, `infra/` at top level | D-01 — matches the Bible's component split (FastAPI + LangGraph, React/Vite, Rego bundle, compose/config) and gives each Build-Map ticket a disjoint ownership boundary for Rule 10. |
| Branching | Trunk-based; one short-lived branch per ticket named `SENT-<stage>-<number>`, merged to `main` by PR; `git worktree` per parallel agent | D-03. Ticket scope equals branch scope, which is what makes the Rule 10 file-ownership allocation in `BRANCHING.md` enforceable. |
| Image pinning | Exact tags, never floating; resolved `sha256:` digests recorded in `infra/README.md` | D-04 — reproducibility across a 20-day build with no surprise breaking change mid-hackathon. |

## Stack Touched in Phase 1

Adapted from the standard checklist for an infrastructure-only phase.

- [ ] Project scaffold — four D-01 tiers created, root `README.md`, `.gitignore`, `.gitattributes`, `BRANCHING.md` (plans 01-01, 01-02)
- [ ] Orchestration — root `docker-compose.yml` brings all three services up on one command (plans 01-01, 01-03)
- [ ] Relational store — Postgres healthy, reachable on 127.0.0.1:5432, persisting to a named volume, with the Phase 2 DDL mount reserved (plans 01-01, 01-04)
- [ ] Vector store — Qdrant healthy via a real `/readyz` HTTP probe, reachable on 127.0.0.1:6333, persisting to a named volume (plan 01-03)
- [ ] Policy engine — OPA healthy via a real `/health` HTTP probe, reachable on 127.0.0.1:8181, serving the read-only `policies/` bundle root (plan 01-03)
- [ ] Verification — `infra/health-check.sh` asserts container health plus host port reachability per service; `infra/verify-persistence.sh` asserts D-05 (plans 01-01, 01-04)
- [ ] Cold start — the full stack re-earned from destroyed volumes with the single canonical command and nothing else (plan 01-04)

## Out of Scope (Deferred to Later Slices)

Explicit, so later phases do not re-litigate Phase 1's minimalism.

- Postgres schema, DDL, and FK constraints — `infra/postgres/initdb/` is an empty reserved mount (SENT-1-01, Phase 2)
- Seed data for `GXP-MFG-DEMO-01` and `BUS-IT-DEMO-02`, including the injected `DataSync Solutions` finding (SENT-1-02, Phase 2)
- Any Rego rule — `policies/` is an empty bundle root; OPA serves nothing yet (SENT-1-03, Phase 2)
- The `evaluate_opa_policy()` client and `python_fallback_rules()` stub (SENT-1-04, Phase 2)
- FastAPI application, Pydantic schemas, `/api/health` (SENT-1-05, Phase 2). Nothing binds port 8000 in Phase 1.
- LangGraph `StateGraph` and the `C2 → A0 → [A1…A6] → C1 → A7 → C3` topology (SENT-1-06, Phase 2)
- React/Vite/Tailwind app and the WebSocket pattern (SENT-1-07/08, Phase 2). Nothing binds port 3000 in Phase 1.
- Qdrant collection configuration and the ingestion pipeline (SENT-2-08, Phase 3)
- CI test runner — `infra/health-check.sh` is deliberately shaped as its seed, but no `.github/workflows/` is created here (SENT-1-09, Phase 2)
- Demo-state reset script — `down` versus `down -v` semantics are documented and tested now, but the one-command restore is SENT-6-06 (Phase 7)
- Any authentication in front of Qdrant or OPA — both are loopback-only sidecars; RBAC is C2's job (Phase 5)
- Production deployment of any kind. This is a local dev environment; no hosted target exists in the project scope.

## Subsequent Slice Plan

Each later phase adds capability on top of this skeleton without altering its architectural decisions above.

- **Phase 2 (Foundation)** — schema and seed data land in the reserved Postgres init mount; the 10 Rego rules land in the `policies/` bundle root this phase created and mounted; FastAPI boots on 8000 and the Vite shell on 3000, both talking to services already proven reachable. This is where the standard walking-skeleton items (a real route, a real DB read/write, a real UI interaction) actually land.
- **Phase 3 (Intelligence & Retrieval)** — A0 routing, the A2 Compliance agent, and C1's real confidence calculation, consuming the live Postgres and OPA endpoints stood up here.
- **Phase 4 (Evidence & Impact)** — NetworkX evidence graph built from live Postgres state, Blast Radius traversal, React Flow rendering, Assurance Cards.
- **Phase 5 (Safety & Remediation)** — C2 RBAC and injection detection, C3 action routing with pending writes, A7 remediation, and the hash-chained audit trail.
- **Phase 6 (Product Experience)** — Command Centre and Ask GxP Copilot; the full Monitor → Investigate → Trust → Remediate → Audit loop becomes walkable.
- **Phase 7 (Integration & Hardening)** — adversarial testing and the one-command demo-state reset acting on the `postgres_data` / `qdrant_data` volumes defined here.
- **Phase 8 (Freeze)** — bug-fix pass, rehearsal, submission packaging.
