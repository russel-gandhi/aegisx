# infra/ — Environment Operations

This document covers day-to-day operation of the local Docker Compose environment: the
canonical commands, the difference between stopping and resetting the stack, the
certified state of the environment, and fixes for the two verified image healthcheck
pitfalls. For prerequisites, the quickstart, and the port table, see the root
[`README.md`](../README.md) — this file does not repeat them.

## What this directory holds

- **`infra/postgres/initdb/`** — bind-mount source for `/docker-entrypoint-initdb.d`. Empty
  in Phase 1 (`.gitkeep` only); this is the reserved mount point Phase 2's schema DDL
  (SENT-1-01) will populate.
- **`infra/qdrant/Dockerfile`** — a locally built, curl-capable derived image on top of
  `qdrant/qdrant:v1.19.0`. The vendor image ships no curl/wget/nc at all (a deliberate
  upstream size/security tradeoff), so a real HTTP healthcheck against `/readyz` cannot
  run inside the bare vendor image — this derived image exists solely to make that
  healthcheck executable.
- **`infra/opa/Dockerfile`** — a locally built, curl-capable derived image on top of
  `openpolicyagent/opa:1.19.1-debug`. This is the plan's own named fallback path, and it
  was needed: the `-debug` tag's busybox build ships no `wget` applet, no `curl`, and no
  package manager reachable at build time (`apk: not found`), so its shell alone was not
  enough for an exec-based `/health` healthcheck either. The fallback here is implemented
  as a cross-image `COPY --from=cgr.dev/chainguard/curl / /` rather than a package
  install, because the OPA base has no package manager to install into.
- **`infra/health-check.sh`** — pure, read-only ENV-01 gate. Asserts, per service, that
  Compose reports the container `healthy` AND that its published loopback port is
  reachable from the host. Never starts, stops, or mutates anything.
- **`infra/verify-persistence.sh`** — automated, mutating assertion for D-05. Writes a
  probe row/collection to Postgres and Qdrant, cycles the stack with a plain
  `down`/`up` (never the destructive volumes flag), re-reads both stores to prove the
  named volumes survived, re-asserts health, and removes its own probes on exit.

## Daily commands

| Command | Effect |
|---|---|
| `docker-compose up -d postgres qdrant opa` | Bring the stack up. This is the entire setup step — nothing else is required. |
| `bash infra/health-check.sh` | Assert ENV-01: prints `ALL HEALTHY` and exits 0 only if every service is both Compose-healthy and reachable on its published port; exits non-zero and names the failing service(s) otherwise. |
| `docker compose ps` | Compose's own view of container status, health, and published ports. |
| `docker compose logs -f <service>` | Tail a single service's logs for diagnosis (`postgres`, `qdrant`, or `opa`). |
| `bash infra/verify-persistence.sh` | Automated proof that data survives a plain stop/start cycle (D-05). Mutates the environment (restarts the stack) but cleans up its own probes. |

## Stop versus reset — read before typing

This is the one distinction in this directory that is genuinely dangerous to get wrong.

- **`docker compose down`** stops and removes the containers, but the named volumes
  (`postgres_data`, `qdrant_data`) are left untouched. Postgres tables and Qdrant
  collections survive a plain `down` followed by `up` — this is D-05, and it is what
  `bash infra/verify-persistence.sh` proves automatically rather than merely asserting.
- **`docker compose down -v`** additionally deletes the `postgres_data` and
  `qdrant_data` named volumes, destroying every row and every collection — including,
  from Phase 2 onward, the seeded demo dataset SENT-1-02 creates. There is no
  confirmation prompt and no undo once the volume is gone; the flag is one character
  away from the safe form.
- From Phase 2 onward, running `down -v` means re-running the seed work from scratch.
  The Stage 6 demo-state-reset ticket (SENT-6-06) is the supported, intentional way to
  restore a known-good demo dataset — reach for that ticket's tooling, not an ad hoc
  `down -v`, when you actually want a clean demo state later in the project.
- `bash infra/verify-persistence.sh` is the automated proof of the non-destructive case
  (`down` / `up`), and is safe to run at any time after Phase 2 seed data exists, since
  it never touches the volumes flag and cleans up its own probes.

## Verified environment

This environment was certified from a genuinely destroyed state, not a warm one:
`docker compose down -v --remove-orphans` was run, `docker volume ls` confirmed neither
`postgres_data` nor `qdrant_data` existed anywhere, and then the single canonical
command below was run with no other manual step before all three services reported
healthy.

- **Command form used:** both `docker-compose up -d postgres qdrant opa` (hyphenated
  v1-style binary) and `docker compose up -d postgres qdrant opa` (v2 plugin subcommand)
  are available and equivalent on this machine (Docker Compose v5.4.0). The literal
  ENV-01/Bible Section 13 form (`docker-compose up -d postgres qdrant opa`) was the one
  actually run for this certification, and it worked with zero other steps: no manual
  database creation, no manual collection creation, no manual policy load, no container
  shell commands.
- **Result:** `bash infra/health-check.sh` printed `ALL HEALTHY` and exited 0 on the
  very first run after the cold `up` — no retry was needed. `docker compose ps` showed
  all three services `(healthy)`.
- **Resolved image digests** (`docker image inspect --format '{{index .RepoDigests 0}}'`),
  captured at the moment of this certification so a later "it worked in Phase 1" claim
  can be checked against the exact bits, not a mutable tag:

  | Service | Vendor base image (pinned tag) | Resolved digest |
  |---|---|---|
  | postgres | `postgres:16.15` | `postgres@sha256:e17e86066e5ef83e0952a9347f5c792b7ece00972e2aa787a6986f471b3dd3d5` |
  | qdrant | `qdrant/qdrant:v1.19.0` | `qdrant/qdrant@sha256:057ee3a8da769fe7310dd3537b4dc7583bf87a95ce8ac43c0af5a46bc580d1fc` |
  | opa | `openpolicyagent/opa:1.19.1-debug` | `openpolicyagent/opa@sha256:41fb76df0a663a257dfaca80cbc13089f1c2f9ad876c59a4de654c830ce8a5ae` |

  The `qdrant` and `opa` services actually run a locally built derived image on top of
  these bases (see "What this directory holds" above), not the bare vendor image
  directly. The derived images built for this certification resolve to:

  - `gxp-sentinel-qdrant@sha256:8978c042c54cb416546aef2d9c088856b2a86dafca6043828a3f21b3b758e865`
  - `gxp-sentinel-opa@sha256:34fce9fc78d426e40e428a635e71f608237738c81038f1eaab2aa824eb082e6c`

## Data tier (Stage 1)

Stage 1 (SENT-1-01/SENT-1-02) added the Postgres data tier on top of the empty
container skeleton Phase 1 left behind: the full Bible Section 4.1 schema (27
tables, 21 foreign keys) and a re-runnable seed script for both demo systems.

**The single most likely point of confusion in this tier:** the postgres
image only executes `infra/postgres/initdb/001_schema.sql` **when its data
directory is empty**. Editing the DDL and simply restarting the container
(`docker compose restart postgres`, or even `docker compose up -d postgres`
again) does nothing — Postgres already has a populated data directory and
skips `/docker-entrypoint-initdb.d` entirely. Applying a schema change
always requires destroying the volume first:

```bash
docker compose down -v --remove-orphans
docker compose up -d --wait
```

`down -v` also destroys the `qdrant_data` volume alongside `postgres_data` —
this is harmless at this stage, since nothing has been ingested into Qdrant
yet, but it is worth knowing before reaching for `-v` out of habit.

### Full data-tier reset, in order

```bash
docker compose down -v --remove-orphans
docker compose up -d --wait
bash infra/apply-seed.sh
bash infra/verify-schema.sh
bash infra/verify-seed.sh
```

### Why the seed lives outside `initdb/`

`infra/postgres/seed/001_seed.sql` is **not** bind-mounted into the
container the way `infra/postgres/initdb/` is. Seeding is a deliberate
operator action (`bash infra/apply-seed.sh`), not part of environment
bring-up — a cold start yields a clean, correctly-shaped, empty database,
rather than silently re-materialising demo data every time the volume is
destroyed and recreated. `infra/apply-seed.sh` streams the seed file into
the container over stdin, and every `INSERT` in it carries
`ON CONFLICT (id) DO NOTHING`, so re-running it is always safe.

### The 10 injected gaps

The seed data purpose-builds `GXP-MFG-DEMO-01` to fail exactly ten Rego
checks, so the compliance agents (Phase 3+) always have something real to
find. `BUS-IT-DEMO-02` is the healthy comparator and triggers none of them.
Rule IDs below are cited from `GxP-Sentinel-Project-Bible-v6.md` Section
3.3 (CLAUDE.md Rule 13 — regulatory/rule citations never come from model
recall):

| Record | Rego rule triggered |
|---|---|
| `DOC-2026-OM-99` (O&M doc, status DRAFT) | `ANNEX11-S4-DOC-001` |
| `AR-2026-05` (access review, 98 days overdue) | `ANNEX11-S12-ACC-001` |
| `RSK-2024-11` (risk review expired) | `ICH-Q9-RSK-001` |
| `INC-849201` (P1 incident, no RCA) | `ANNEX11-S13-INC-001` |
| `URS-042` / `TC-2026-042` (traceability gap) | `ANNEX11-S4-TRC-001` |
| `SUP-2026-01` (supplier reassessment overdue) | `ANNEX11-S3-SUP-001` |
| `PE-2024-01` (periodic evaluation overdue) | `ANNEX11-S11-PE-001` |
| `GXP-MFG-DEMO-01.last_backup_test_ns` (backup restore test stale) | `ANNEX11-S16-BCK-001` |
| `ACC-2026-99` (orphaned privileged account) | `ANNEX11-S12-ACC-002` |
| `CR-2026-089` / `CA-2026-089-1` (change closed with open action) | `ANNEX11-S10-CHG-001` |

### Nanosecond epoch columns

Every column ending `_ns` (e.g. `last_backup_test_ns`, `scheduled_date_ns`,
`due_date_ns`) is a **nanosecond**-epoch `BIGINT`, not seconds or
milliseconds — the Rego rules in `policies/` compute against them with
`time.now_ns()` / `time.diff(...)`. Any future code that generates one of
these values must multiply seconds by `1_000_000_000` (equivalently,
`1000000000`). `infra/verify-seed.sh` includes a guard that fails if any
seeded `_ns` value falls below nanosecond magnitude, but nothing enforces
this for values generated later by application code — get the multiplier
right at the source.

## Troubleshooting

Two failure modes were actually hit and fixed during this phase (not hypothetical) —
each entry below states the symptom, the cause, and the fix.

**(a) Qdrant stuck `unhealthy`, with an `executable file not found` healthcheck output.**
Symptom: `docker compose ps` shows `qdrant` unhealthy indefinitely, and
`docker inspect <container> --format '{{json .State.Health}}'` shows an error like
`exec: "curl": executable file not found in $PATH`. Cause: the container is running the
bare vendor image (`qdrant/qdrant:v1.19.0`) directly instead of the derived,
curl-capable image built from `infra/qdrant/Dockerfile` — the vendor image ships no
curl, wget, or nc at all. Fix: `docker compose build qdrant` to (re)build the derived
image, then `docker compose up -d qdrant`.

**(b) OPA stuck `unhealthy`, or `up` fails to find a shell/HTTP client at all.**
Symptom: the same class of `executable file not found` error, or (if the compose file
were ever pointed at the bare, non-`-debug` OPA tag) a failure to exec any shell
whatsoever. Cause: the bare `openpolicyagent/opa` tag is built on a fully distroless
Chainguard `static` base with no shell and no HTTP client, and — the pitfall actually
verified in this phase — even the `-debug` tag's busybox build has **no working `wget`
applet, no curl, and no package manager reachable at build time**, so a plain tag swap
to `-debug` is not sufficient on its own. Fix: use the derived image built from
`infra/opa/Dockerfile`, which copies a working `curl` binary and its shared libraries
in from a separate, ABI-compatible Chainguard `curl` image (`COPY --from=... / /`)
rather than attempting any in-container package install.

**(c) A service shows `(healthy)` in `docker compose ps` but is unreachable from the host.**
Symptom: `bash infra/health-check.sh` reports a service `RED` with `port: <n> unreachable`
even though Compose itself considers the container healthy. Cause: the port publish
mapping in `docker-compose.yml` is missing, wrong, or the service inside the container is
bound to a different address than the healthcheck probes (all three services here bind
loopback-only, `127.0.0.1:<port>:<port>`, by design — this stack is never meant to be
reachable from the LAN). Fix: check the `ports:` mapping for the affected service in
`docker-compose.yml`, and confirm the service's own listen address matches.

**(d) `docker compose up` fails immediately with an unset-password / required-variable error.**
Symptom: Compose refuses to start with an error naming `POSTGRES_PASSWORD` (or similar)
as unset. Cause: `.env` was never created from the committed `.env.example` template —
`docker-compose.yml` deliberately fails loud (`${POSTGRES_PASSWORD:?...}`) rather than
silently falling back to a blank or default password. Fix: `cp .env.example .env` at the
repo root, per the root README's Quickstart, before running `up` again.

## See also

- Root [`README.md`](../README.md) — prerequisites, quickstart, full port table, and
  repository layout.
- `.planning/phases/01-environment/01-CONTEXT.md` — D-05 (persistence) and D-06
  (healthcheck) decisions this document and `infra/verify-persistence.sh` implement.
