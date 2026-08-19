# Phase 1: Environment - Research

**Researched:** 2026-08-19
**Domain:** Docker Compose local environment bring-up (Postgres, Qdrant, OPA) + repo scaffold/branching convention
**Confidence:** MEDIUM-HIGH (image tags and base-image facts verified directly against source registries/repos; some healthcheck-tooling details are best-effort workarounds for a documented open upstream gap)

## Summary

Phase 1 has no application code — it is pure infrastructure bring-up. The two ticket contracts (SENT-0-01, SENT-0-02) reduce to: (1) a repo skeleton + branching doc that gives every later ticket an unambiguous file-ownership boundary, and (2) a root `docker-compose.yml` that brings up Postgres 16, Qdrant, and OPA with real Compose `healthcheck:` blocks so `docker-compose ps` shows all three `healthy`.

The Postgres and OPA halves are close to mechanical: `pg_isready` ships in every official Postgres image, and OPA's own docs recommend probing `/health`. The one real landmine, verified this session by reading the **actual source Dockerfiles/Makefiles** of both `qdrant/qdrant` and `openpolicyagent/opa`, is that **neither image ships curl, wget, or (in OPA's default tag) even a shell** — so the exact `curl`-based healthcheck the Bible's own Section 3.2 snippet shows for OPA will not execute inside OPA's default (`chainguard/static`-based, fully distroless) image, and the same problem applies to Qdrant's `debian:13-slim`-based image, which has a shell but no HTTP client at all. This is a genuine, source-verified pitfall the planner must design around, not a hypothetical one — see Common Pitfalls below for the two viable fixes.

**Primary recommendation:** Pin `postgres:16.15`, `qdrant/qdrant:v1.19.0`, and `openpolicyagent/opa:1.19.1-debug` (the busybox-based OPA variant, not the bare distroless default tag) in a root `docker-compose.yml`; give Qdrant a tiny locally-built derived image (via `build:` inline Dockerfile) that adds `curl` for its healthcheck, since no vendor-provided Qdrant variant includes an HTTP client; use `pg_isready` for Postgres and `wget`/`curl` HTTP probes for Qdrant `/readyz` and OPA `/health`. Pair this with a `backend/`, `frontend/`, `policies/`, `infra/` repo layout (already locked in CONTEXT.md D-01/D-02) and a documented trunk-based, one-branch/worktree-per-ticket convention (`SENT-<stage>-<number>`) recorded in a root `BRANCHING.md`.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Top-level layout is `backend/`, `frontend/`, `policies/`, `infra/` — matches the Bible's component split (FastAPI+LangGraph app, React/Vite app, Rego rules, docker-compose/configs) and gives clean ownership boundaries per ticket for Rule 10.
- **D-02:** `docker-compose.yml` lives at repo root so `docker-compose up -d postgres qdrant opa` works with zero path args, matching the Bible's documented one-liner. Service-specific config (Postgres init scripts, OPA policy bundle mount pointing at `policies/`) lives under `infra/`.
- **D-03:** Trunk-based development with a short-lived branch per ticket (`SENT-<stage>-<number>`), branched from `main`, merged via PR when the ticket's contract is met. Satisfies Rule 10 (no two agents editing the same critical file) by keeping ticket scope == branch scope, including for Critical-review tickets.
- **D-04:** Docker images pinned to exact tags (e.g. `postgres:16`, a specific `qdrant/qdrant` version tag, a specific OPA image tag) rather than `latest`/major-only tags — reproducibility across the 20-day build, no surprise breaking changes mid-hackathon. Reversibility: reversible — changing a pinned tag later is a one-line compose edit.
- **D-05:** Postgres and Qdrant data persist across `docker-compose down` via named Docker volumes (`postgres_data`, `qdrant_data`). Not wiped unless `down -v` is used explicitly. This is also the target the Stage 6 demo-state-reset script (SENT-6-06) will act on later.
- **D-06:** Each service defines a native `healthcheck:` block in `docker-compose.yml` — `pg_isready` for Postgres, an HTTP check against Qdrant's health endpoint, an HTTP check against OPA's health endpoint — with interval/retries, so `docker-compose ps` shows healthy/unhealthy directly. This gives a scriptable "all green" signal matching ENV-01's acceptance criterion verbatim, and sets up the later CI test runner (SENT-1-09).

### Claude's Discretion

- Exact image tag versions (specific Postgres 16.x patch, Qdrant version, OPA version) — pick current stable versions at implementation time.
- Exact healthcheck interval/timeout/retries values.
- `.env` / secrets handling mechanics for the compose file (no GxP secrets exist yet at this phase — local dev only).

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within Phase 1 scope. (Demo-state-reset scripting, CI test runner, and schema/seed work are already correctly scoped to later phases per ROADMAP.md and were not raised as in-scope-now by the user.)
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| ENV-01 | `docker-compose up -d postgres qdrant opa` brings up all three services healthy on ports 5432/6333/8181 | Verified current image tags (Standard Stack), verified healthcheck-tooling gaps in Qdrant/OPA images and their fixes (Common Pitfalls, Code Examples), verified `/health`/`/readyz` endpoint semantics (Code Examples) |
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Relational persistence (Postgres) | Database / Storage | — | Owns `gxp_systems`, `documents`, `action_proposals`, etc. from Phase 2 onward; Phase 1 only stands up the empty, healthy container + volume |
| Vector persistence (Qdrant) | Database / Storage | — | Owns hybrid dense/BM25 retrieval index (A1, Phase 3+); Phase 1 only stands up the empty, healthy container + volume |
| Policy evaluation sidecar (OPA) | API / Backend (sidecar) | — | Deterministic-first constraint (Bible Section 1.3) requires policy evaluation to live outside any LLM-reachable process; it is a peer service the FastAPI backend calls over REST, not embedded in it |
| Container orchestration (Compose bring-up, healthchecks, volumes) | Infra / Ops | — | `docker-compose.yml` at repo root; not owned by backend or frontend code |
| Repo scaffold + branching convention | Tooling / Process (cross-cutting) | — | Governs how every later tier's code gets written in parallel without collision (Rule 10); not itself part of the runtime request path |

## Standard Stack

### Core

| Image | Tag (verified current) | Purpose | Why this tag |
|-------|-------------------------|---------|---------------|
| `postgres` | `16.15` `[VERIFIED: Docker Hub registry API, library/postgres, last_updated 2026-08-16T07:07:43Z]` | Relational store for all GxP schema (Phase 2+) | Latest 16.x patch as of research date; Docker Official Image namespace (`library/postgres`), not a third-party fork |
| `qdrant/qdrant` | `v1.19.0` `[VERIFIED: Docker Hub registry API, qdrant/qdrant, last_updated 2026-08-04T12:32:39Z]` | Vector store for hybrid RAG (Phase 3+, A1) | Latest stable tag as of research date; published under the vendor's own `qdrant/qdrant` namespace, matches `github.com/qdrant/qdrant` source |
| `openpolicyagent/opa` | `1.19.1-debug` `[VERIFIED: Docker Hub registry API, openpolicyagent/opa, last_updated 2026-08-17T12:59:15Z for the base 1.19.1 tag; `-debug` suffix confirmed to exist as a published tag]` | Deterministic Rego policy sidecar (Section 3) | `-debug` variant recommended over the bare `1.19.1` tag — see Common Pitfalls: the default tag is fully distroless (no shell, no HTTP client) and cannot run an exec-based Compose healthcheck at all |

### Supporting

| Item | Purpose | When to Use |
|------|---------|-------------|
| Named Docker volumes (`postgres_data`, `qdrant_data`) | Persist data across `docker-compose down` (D-05) | Declared under top-level `volumes:` in `docker-compose.yml`, mounted at each service's data directory |
| `.env` (gitignored) + `.env.example` (committed) | Local dev secrets (Postgres password, etc.) — no real GxP secrets exist yet | Compose reads `.env` automatically from the file's own directory; keep `docker-compose.yml` free of hardcoded credentials even in dev |
| Small inline/derived Dockerfile for Qdrant only | Adds `curl` so a real HTTP healthcheck can execute inside the Qdrant container | See Code Examples — required because no vendor-published Qdrant tag includes an HTTP client |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `openpolicyagent/opa:1.19.1-debug` (busybox-based) for the healthcheck-capable image | `openpolicyagent/opa:1.19.1` (default, distroless) + no Compose-native healthcheck (rely on `start_period` + host-side manual curl) | Simpler compose file, but fails D-06's explicit requirement that `docker-compose ps` show OPA healthy — not recommended unless the `-debug` tag turns out to lack `wget` at implementation time (unverified — flag for a quick manual check, see Assumptions Log) |
| Derived Qdrant image with `curl` added | Bash `/dev/tcp` TCP-only check (`bash -c 'echo > /dev/tcp/localhost/6333'`) | Works with zero extra build step (Qdrant's `debian:13-slim` base does ship `bash`), but only proves the port is listening, not that Qdrant has finished loading collections — does not satisfy D-06's "HTTP check against Qdrant's health endpoint" wording |
| Postgres `16.15` (default/bookworm variant) | `postgres:16.15-alpine` | Alpine is smaller, but complicates any future extension installs (Phase 2 DDL) since apk package names differ from apt; not worth the tradeoff for a 20-day hackathon where image pull time is not the bottleneck |

**Installation:**
```bash
# No package manager install — these are Docker images pulled by Compose itself.
docker-compose up -d postgres qdrant opa
```

**Version verification:** All three tags above were confirmed live against the Docker Hub Registry HTTP API (`https://hub.docker.com/v2/repositories/<namespace>/tags`) during this research session, not from training-data recall. Re-run the same query at implementation time if more than a few days have passed, since these projects ship frequently.

## Package Legitimacy Audit

> Adapted for this phase: Phase 1 installs no npm/pip/cargo packages — it only pulls three Docker images. The equivalent supply-chain check is registry-namespace provenance, done below by reading each project's own source repo (Dockerfile/Makefile) to confirm the published image matches the vendor's own build process.

| Image | Registry namespace | Provenance check | Verdict |
|-------|---------------------|-------------------|---------|
| `postgres:16.15` | `library/postgres` (Docker Official Images) | Reserved Docker Hub namespace for official images; not attributable to an arbitrary publisher | OK |
| `qdrant/qdrant:v1.19.0` | `qdrant/qdrant` | `[VERIFIED: github.com/qdrant/qdrant Dockerfile — read this session]` Dockerfile's final stage builds `FROM debian:13-slim AS qdrant-cpu`, copies the compiled `qdrant` binary from the project's own multi-stage build; matches the vendor's published source | OK |
| `openpolicyagent/opa:1.19.1-debug` | `openpolicyagent/opa` | `[VERIFIED: github.com/open-policy-agent/opa Makefile — read this session]` Default and `-debug` tags are built by the project's own `image-quick-%` Make target from `chainguard/static:latest` and `chainguard/busybox:latest` respectively; matches vendor source | OK |

**Packages removed due to [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Architecture Patterns

### System Architecture Diagram

```
Developer runs one command
        |
        v
  docker-compose up -d postgres qdrant opa
        |
        v
  Compose reads ./docker-compose.yml (repo root)
        |
        +----------------+----------------+
        |                |                |
        v                v                v
  [postgres:16.15]  [qdrant/qdrant   [openpolicyagent/
   pulls image        :v1.19.0]       opa:1.19.1-debug]
        |             pulls image      pulls image
        v                |                |
  binds 5432:5432        v                v
  mounts postgres_data  binds 6333:6333  binds 8181:8181
        |               mounts qdrant_data mounts ./policies:/policies
        v                |                |
  container starts,      v                v
  runs native            container starts container starts
  pg_isready healthcheck (curl-augmented   (wget-capable
        |               healthcheck vs.   healthcheck vs.
        |               /readyz)          /health)
        +----------------+----------------+
                          |
                          v
              `docker-compose ps` reports
              all three services `healthy`
                          |
                          v
              Stage 1 tickets (SENT-1-xx) connect
              over the published ports — no code
              runs in this phase
```

### Recommended Project Structure
```
.
├── docker-compose.yml       # D-02: root, zero-arg `docker-compose up`
├── .env.example              # committed template; real .env gitignored
├── .gitignore
├── BRANCHING.md               # D-03: trunk-based, ticket-scoped branch/worktree doc
├── backend/                   # FastAPI + LangGraph app (Phase 2+, empty/placeholder now)
├── frontend/                  # Vite + React + Tailwind app (Phase 2+, empty/placeholder now)
├── policies/                  # Rego bundle root — mounted read-only into OPA at /policies
└── infra/
    ├── postgres/               # init scripts (none needed yet — Phase 2 owns DDL)
    └── qdrant/
        └── Dockerfile          # thin derived image: qdrant/qdrant:v1.19.0 + curl, for the healthcheck
```

### Pattern 1: Compose-native healthcheck + `docker-compose ps` as the acceptance gate
**What:** Every service declares its own `healthcheck:` block; the ticket's Definition of Done is verified by reading Compose's own health state, not a hand-rolled wait-loop script.
**When to use:** Any Compose service whose "ready" state is meaningfully different from "process started" (all three services here — Postgres/Qdrant/OPA all have a window where the process is running but not yet accepting correct traffic).
**Example:**
```yaml
# Source: pattern derived from official Postgres/OPA docs + Docker Compose healthcheck spec
services:
  postgres:
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-postgres}"]
      interval: 5s
      timeout: 5s
      retries: 10
      start_period: 10s
```

### Anti-Patterns to Avoid
- **Hand-rolled `sleep`/retry wait scripts before running app code:** Compose's native `healthcheck:` + `depends_on: condition: service_healthy` already solves this; a custom wait-for-it script duplicates functionality Compose provides for free and is exactly the kind of "don't hand-roll" trap this phase should avoid.
- **Copying the Bible's Section 3.2 OPA healthcheck snippet verbatim:** it targets the bare `openpolicyagent/opa:0.63.0` tag with a `curl`-based `CMD` test. The bare/default OPA tag is built from `chainguard/static` — a fully distroless base with no shell and no `curl` — so this exact snippet will not execute inside that container. Use the `-debug` tag (or add a healthcheck-shim image) instead.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Waiting for Postgres/Qdrant/OPA to be truly ready before dependent tickets run | Custom polling/retry script wrapping `docker-compose up` | Compose native `healthcheck:` + `depends_on: condition: service_healthy` | Built into Compose, shows up natively in `docker-compose ps`, and is exactly the mechanism ENV-01's acceptance criterion checks against |
| Giving Qdrant an HTTP client for its healthcheck | Installing curl/wget by hand inside the running container on every `up` (e.g. via `command:` override running `apt-get install` at start) | A tiny locally-built derived image (`infra/qdrant/Dockerfile`) referenced via Compose `build:`, built once as part of `docker-compose up` | Deterministic, cached, and doesn't add install-time network dependency/flakiness to every container start |
| Branch/worktree ownership tracking | A custom lockfile or bot to prevent two agents touching the same file | Trunk-based, one-branch-per-ticket convention (D-03) documented in `BRANCHING.md`, enforced by PR review | Git's own branch model already gives this for free when ticket scope == branch scope; Rule 10 asks for discipline/convention, not new tooling |

**Key insight:** Every problem in this phase already has a first-party solution (Compose healthchecks, Docker volumes, Git branches). The only genuine gap is that two of the three vendor images (Qdrant, OPA-default) don't ship an HTTP client to satisfy an *exec-based* Compose healthcheck — that's a real, source-verified constraint, not something to work around with more hand-rolled tooling than necessary (one thin derived Dockerfile for Qdrant; one tag swap for OPA).

## Common Pitfalls

### Pitfall 1: Qdrant's official image has no curl, wget, or netcat — an exec-based HTTP healthcheck will fail with "executable file not found"
**What goes wrong:** A Compose `healthcheck.test` entry like `["CMD", "curl", "-f", "http://localhost:6333/readyz"]` fails immediately, marking the container `unhealthy` forever, even though Qdrant itself is running fine.
**Why it happens:** `[VERIFIED: github.com/qdrant/qdrant/Dockerfile, final stage — read this session]` The runtime stage is `FROM debian:13-slim AS qdrant-cpu`, and the only packages installed on top of that base are `ca-certificates tzdata libunwind8` (plus an optional `$PACKAGES` build arg used only during Qdrant's own from-source build, not available against the already-published Docker Hub tag). There is no curl, wget, or netcat in the shipped image. This is a known, currently-open upstream gap: `[CITED: github.com/qdrant/qdrant/issues/4250]` — "Add a healthcheck command that can be used within docker compose" is open, and maintainers confirm curl/wget/nc were deliberately left out as a security/size tradeoff.
**How to avoid:** Build a thin derived image for the Qdrant service only (`infra/qdrant/Dockerfile`, `FROM qdrant/qdrant:v1.19.0` + `RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*`), referenced via Compose `build:` so it's still produced by a single `docker-compose up`. Healthcheck against `[CITED: api.qdrant.tech/api-reference/service/readyz]` `GET /readyz`, which returns 200 once "all shards are ready" — a stronger readiness signal than a bare TCP connect.
**Warning signs:** `docker-compose ps` shows Qdrant `unhealthy` indefinitely; `docker inspect <container> --format '{{json .State.Health}}'` shows `"Output": "OCI runtime exec failed: exec failed: unable to start container process: exec: \"curl\": executable file not found in $PATH"`.

### Pitfall 2: OPA's default (bare-tag) image is fully distroless — no shell at all, so even `CMD-SHELL` healthchecks can't run
**What goes wrong:** The Bible's own Section 3.2 docker-compose snippet (`image: openpolicyagent/opa:0.63.0`, healthcheck `["CMD", "curl", "-f", "http://localhost:8181/health"]`) will not execute — worse than the Qdrant case, because the default OPA image has no `/bin/sh` at all to fall back on.
**Why it happens:** `[VERIFIED: github.com/open-policy-agent/opa/Makefile, image-quick-% target — read this session]` The default (non-`-debug`, non-`-static`-suffixed-for-static) `openpolicyagent/opa:<version>` tag is built with `--build-arg BASE=chainguard/static:latest`. Chainguard's `static` image is intentionally distroless — no package manager, no shell, no coreutils, just certs and the `/opa` binary itself (`ENTRYPOINT ["/opa"]`). The `-debug` tag is built from `--build-arg BASE=chainguard/busybox:latest` instead, which does include a busybox shell and its bundled utilities.
**How to avoid:** Pin the OPA service to `openpolicyagent/opa:1.19.1-debug`, not the bare `1.19.1` tag, and heathcheck with `wget` (busybox's bundled HTTP client) against `[CITED: openpolicyagent.org/docs/deploy/docker]` `GET /health`. `[ASSUMED]` that the Chainguard busybox image's bundled `wget` applet is present and functional — this is standard busybox behavior but was not runtime-verified this session (no Docker runtime was available in the research environment). Flag a one-line manual check (`docker run --rm openpolicyagent/opa:1.19.1-debug wget --help`) as a fast pre-flight step before trusting this in the plan.
**Warning signs:** `docker-compose ps` shows OPA `unhealthy`; `docker inspect` health output shows `OCI runtime exec failed ... exec: "curl": executable file not found` or, for the bare tag, a failure to exec `/bin/sh` at all.

### Pitfall 3: Docker Compose `depends_on` alone does not wait for readiness
**What goes wrong:** Later Stage 1 tickets (e.g. SENT-1-01 loading the Postgres schema) assume Postgres is ready just because its container started, and fail with connection-refused errors during CI or a fast machine.
**Why it happens:** `depends_on` without a `condition:` only orders container *start*, not service *readiness* — well-documented, common Compose gotcha.
**How to avoid:** Always pair `depends_on` with `condition: service_healthy` once a service has a `healthcheck:` block, and give Postgres/Qdrant a `start_period` generous enough to cover cold-start (10–30s is typical for local dev).
**Warning signs:** Intermittent connection-refused errors in Stage 1 tickets that only reproduce on a cold `docker-compose up` (not on a warm restart where images/layers are cached).

### Pitfall 4: Publishing dev database/vector-store ports to `0.0.0.0` instead of loopback
**What goes wrong:** `ports: ["5432:5432"]` binds to all interfaces by default, meaning Postgres (with whatever dev password is set) is reachable from other devices on the same network/VPN, not just localhost.
**Why it happens:** Docker's default port-publish behavior binds `0.0.0.0` unless an explicit host IP is given. `[ASSUMED]` — general Docker networking behavior, not verified against Docker's own docs this session.
**How to avoid:** Bind explicitly to loopback in the compose file, e.g. `ports: ["127.0.0.1:5432:5432"]`, for all three services, since this is purely a local dev environment with no need for LAN exposure.
**Warning signs:** N/A for local single-machine dev — this is a preventive hardening step, not something that manifests as a visible bug during the hackathon.

## Code Examples

### Postgres service with healthcheck and named volume
```yaml
# Source: pattern synthesized from Postgres official image docs + Compose healthcheck spec
services:
  postgres:
    image: postgres:16.15
    ports:
      - "127.0.0.1:5432:5432"
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-sentinel}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?set in .env}
      POSTGRES_DB: ${POSTGRES_DB:-sentinel}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-sentinel}"]
      interval: 5s
      timeout: 5s
      retries: 10
      start_period: 10s

volumes:
  postgres_data:
```

### Qdrant service with a derived curl-capable image for the healthcheck
```yaml
# Source: derived pattern — see Pitfall 1 for why a plain `image:` + curl-based test does NOT work
services:
  qdrant:
    build:
      context: ./infra/qdrant
    ports:
      - "127.0.0.1:6333:6333"
    volumes:
      - qdrant_data:/qdrant/storage
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:6333/readyz"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 10s

volumes:
  qdrant_data:
```
```dockerfile
# infra/qdrant/Dockerfile
# Source: derived from github.com/qdrant/qdrant/Dockerfile (verified base image + package set this session)
FROM qdrant/qdrant:v1.19.0
USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*
USER 0:0
```

### OPA service on the `-debug` tag (shell + wget available)
```yaml
# Source: adapted from Bible Section 3.2, with the healthcheck-capable tag substituted — see Pitfall 2
services:
  opa:
    image: openpolicyagent/opa:1.19.1-debug
    ports:
      - "127.0.0.1:8181:8181"
    volumes:
      - ./policies:/policies:ro
    command:
      - "run"
      - "--server"
      - "--log-format=json"
      - "--set=decision_logs.console=true"
      - "/policies"
    healthcheck:
      test: ["CMD", "wget", "--no-verbose", "--tries=1", "--spider", "http://localhost:8181/health"]
      interval: 10s
      timeout: 5s
      retries: 3
      start_period: 5s
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| Bible Section 3.2's `openpolicyagent/opa:0.63.0` + curl healthcheck | `openpolicyagent/opa:1.19.1-debug` + wget healthcheck | OPA has moved through 0.63.0 → 1.19.1 since the Bible was written; separately, current default OPA images build on Chainguard's distroless `static` base, which post-dates and invalidates the curl-based snippet regardless of version | Planner must not copy the Bible's OPA compose snippet verbatim — pin the current version AND swap the tag suffix and healthcheck tool |
| Qdrant pre-1.5.0: no k8s-style health endpoints | Qdrant ≥1.5.0: dedicated `/livez` and `/readyz` endpoints | Introduced in Qdrant 1.5.0 (well before the current 1.19.0) | Use `/readyz` (collection-load-aware), not a bare `/` root check, for the Qdrant healthcheck |

**Deprecated/outdated:**
- Bible's pinned `openpolicyagent/opa:0.63.0` — over a year of releases behind current stable (1.19.1); D-04/discretion explicitly asks for "current stable versions at implementation time," which supersedes this specific tag.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|----------------|
| A1 | `openpolicyagent/opa:1.19.1-debug`'s bundled busybox includes a working `wget` applet | Common Pitfalls (Pitfall 2), Standard Stack, Code Examples | If wrong, OPA healthcheck fails identically to the default tag; fallback is the same derived-image-with-curl pattern already used for Qdrant, applied to OPA's `-debug` tag instead |
| A2 | Docker's default port-publish binds to `0.0.0.0` unless a host IP is given in the `ports:` mapping | Common Pitfalls (Pitfall 4) | If wrong (e.g. a Docker Desktop networking default differs), the `127.0.0.1:` prefix in the code examples is still harmless/correct either way — low risk |

**If this table is empty:** N/A — two assumptions logged above; both are low-blast-radius (verifiable with a single `docker run`/`docker-compose up` smoke test at implementation time, not requiring a design change if wrong).

## Open Questions

1. **Does `openpolicyagent/opa:1.19.1-debug` actually include a functional `wget`?**
   - What we know: it's built from `chainguard/busybox:latest`, which bundles the standard busybox multi-call binary; busybox distributions near-universally include the `wget` applet.
   - What's unclear: Chainguard's specific busybox build could in principle be trimmed differently; this was not runtime-verified (no Docker daemon available in the research environment).
   - Recommendation: planner should add a first executable task step that runs `docker run --rm openpolicyagent/opa:1.19.1-debug wget --help` (or equivalent) as a fast pre-flight check before committing the OPA healthcheck config; if it fails, fall back to the same derived-image-with-curl pattern used for Qdrant.

2. **Should the derived Qdrant Dockerfile pin an exact `apt-get install curl` version, or float?**
   - What we know: D-04 locks pinned image tags for reproducibility.
   - What's unclear: whether pinning the Debian package version of `curl` inside the derived image is worth the added maintenance for a 20-day hackathon.
   - Recommendation: leave `curl` unpinned inside the derived image (Debian's own base-image package pinning via the `debian:13-slim` tag already gives day-level reproducability); this is a supporting build tool, not an application dependency, so full pinning is not warranted here.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| Docker Engine / Docker Desktop | ENV-01, all of Phase 1 | ✗ (not found on PATH in this research shell) | — | None — Docker is a hard requirement for this entire phase; must be confirmed installed on the actual dev machine(s) before execution starts. This research session ran in a shell with no `docker` binary on PATH; that does not necessarily mean Docker Desktop is absent from the developer's machine (Windows dev machines commonly run Docker Desktop outside the Git-Bash PATH), but it must be confirmed at execution time, not assumed. |
| Docker Compose v2 (`docker compose` / `docker-compose`) | ENV-01 (the CLI invocation itself) | ✗ (same shell constraint as above) | — | Same as above — bundled with Docker Desktop on Windows/Mac; standalone installs on Linux need the `docker-compose-plugin` package |
| Git ≥ 2.20 (worktree support) | D-03 branching convention (`git worktree`) | ✓ | 2.37.3 | — |
| Network access to Docker Hub | Image pulls for all three services | ✓ (used this session for registry lookups) | — | — |

**Missing dependencies with no fallback:**
- Docker Engine/Compose itself — cannot be worked around; the planner should add an explicit first task step confirming `docker --version` and `docker compose version` succeed before attempting `docker-compose up`.

**Missing dependencies with fallback:**
- None beyond the Docker dependency above.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | None — this is a pure infrastructure phase; no application test runner exists yet (SENT-1-09 CI test runner is a later, Stage 1 ticket) |
| Config file | none — see Wave 0 |
| Quick run command | `docker-compose up -d postgres qdrant opa && docker-compose ps` |
| Full suite command | `docker-compose up -d postgres qdrant opa && docker-compose ps --format json` piped to a small health-status assertion script (see Wave 0) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|---------------------|--------------|
| ENV-01 | All three services report `healthy` in Compose's native health state | smoke | `docker-compose up -d postgres qdrant opa` then assert `docker-compose ps --format json` shows `Health: healthy` for all three | ❌ Wave 0 |
| ENV-01 | `docker-compose up -d postgres qdrant opa` is the *only* setup step (no manual pre-steps) | manual-only (justification: verifying "zero extra setup steps" is inherently a fresh-clone/fresh-machine check, not something a unit test asserts) | — | — |

### Sampling Rate
- **Per task commit:** `docker-compose up -d postgres qdrant opa && docker-compose ps`
- **Per wave merge:** same command plus explicit endpoint probes (`docker-compose exec postgres pg_isready`, `curl -f http://127.0.0.1:6333/readyz`, `curl -f http://127.0.0.1:8181/health`)
- **Phase gate:** full suite green (all three `healthy` in `docker-compose ps`) before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `infra/health-check.sh` (or `.ps1` for Windows dev machines) — polls `docker-compose ps --format json` and exits non-zero if any of the three services is not `healthy`; this becomes the mechanical implementation of ENV-01's acceptance criterion and the seed for SENT-1-09's later CI test runner
- [ ] `infra/qdrant/Dockerfile` — the curl-capable derived image described in Pitfall 1 / Code Examples
- [ ] No Python/Node test framework install needed this phase (none exists to test yet)

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|----------------|---------|--------------------|
| V2 Authentication | No | No user-facing auth exists yet — infra-only phase |
| V3 Session Management | No | N/A this phase |
| V4 Access Control | No | RBAC is C2's job (Phase 5) — not in scope |
| V5 Input Validation | No | No app code accepts input yet |
| V6 Cryptography | No | No secrets are stored beyond local dev `.env` values; no cryptographic design decisions in this phase |
| V14 Configuration | Yes | Pinned exact image tags (no `latest`) per D-04; no hardcoded credentials in `docker-compose.yml` — read from `.env` (gitignored) with `.env.example` committed as the template; loopback-only port binding for local dev services |

### Known Threat Patterns for this phase's stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|-----------------------|
| Hardcoded/default database credentials committed to `docker-compose.yml` | Information Disclosure | `.env` (gitignored) supplies `POSTGRES_PASSWORD`; `.env.example` documents required keys without real values; compose file references `${POSTGRES_PASSWORD:?set in .env}` so `up` fails loudly if unset rather than silently using a blank/default password |
| Dev-only services (Postgres/Qdrant/OPA) reachable from the local network, not just localhost | Information Disclosure / Tampering | `[ASSUMED]` Bind published ports to `127.0.0.1:` explicitly rather than the bare `host:container` form (see Pitfall 4) |
| Floating `:latest` tags silently pulling a breaking or compromised newer image mid-hackathon | Tampering | D-04 already locks exact tag pinning — this research verified all three tags exist and are current as of 2026-08-19 |
| OPA policy bundle directory (`./policies`) mounted read-write into the container | Tampering | Mount `./policies:/policies:ro` (read-only) — OPA only needs to read the bundle, never write to it |

## Sources

### Primary (HIGH confidence)
- `[VERIFIED: Docker Hub Registry API — hub.docker.com/v2/repositories/library/postgres/tags]` — current Postgres 16.x tag list and publish dates, read this session
- `[VERIFIED: Docker Hub Registry API — hub.docker.com/v2/repositories/qdrant/qdrant/tags]` — current Qdrant tag list and publish dates, read this session
- `[VERIFIED: Docker Hub Registry API — hub.docker.com/v2/repositories/openpolicyagent/opa/tags]` — current OPA tag list and publish dates, read this session
- `[VERIFIED: github.com/qdrant/qdrant/Dockerfile — raw file read this session]` — confirms runtime base image (`debian:13-slim`) and exact installed package set (no curl/wget/nc)
- `[VERIFIED: github.com/open-policy-agent/opa/Makefile — raw file read this session]` — confirms default tag builds from `chainguard/static:latest` (distroless) and `-debug` tag builds from `chainguard/busybox:latest`
- `GxP-Sentinel-Project-Bible-v6.md` Section 3.2 (OPA compose config, superseded per State of the Art), Section 12 (API table), Section 13 (Hour 0-2 environment setup verification), Section 16.11 Rule 10 (branching)
- `Sentinel-Build-Map.md` Stage 0 (SENT-0-01, SENT-0-02 contracts)

### Secondary (MEDIUM confidence)
- `[CITED: openpolicyagent.org/docs/deploy/docker]` — `/health` endpoint recommended for readiness/liveness probing
- `[CITED: api.qdrant.tech/api-reference/service/readyz]` — `/readyz` endpoint returns 200 with a JSON status string once all shards are ready
- `[CITED: github.com/qdrant/qdrant/issues/4250]` — open upstream issue confirming curl/wget/nc were deliberately excluded from the Qdrant image

### Tertiary (LOW confidence)
- General WebSearch results on Compose healthcheck syntax/`depends_on` semantics and Chainguard busybox applet contents — used for pattern shape only, cross-checked against the verified source files above where it mattered (image contents), flagged `[ASSUMED]` in Pitfall 2/A1 where it could not be

## Metadata

**Confidence breakdown:**
- Standard stack (image tags): HIGH — confirmed live against Docker Hub Registry API this session
- Healthcheck-tooling gaps (Qdrant/OPA): HIGH for the *fact* the tools are missing (read straight from source Dockerfiles/Makefiles); MEDIUM for the *fix* (OPA `-debug` wget presence unverified against a live container — no Docker runtime in this research shell)
- Architecture/repo structure: HIGH — directly specified by locked CONTEXT.md decisions, no invention needed
- Pitfalls: HIGH — grounded in source-code reads, not recall
- Security domain: MEDIUM — standard Docker Compose local-dev hardening practices, one claim (`0.0.0.0` default bind) flagged `[ASSUMED]`

**Research date:** 2026-08-19
**Valid until:** ~7 days for image tag pins (Qdrant/OPA ship frequently — re-verify tags immediately before implementation if this research is more than a few days old); ~30 days for the architectural/pitfall findings (source-code-level facts about base images change far less often)
