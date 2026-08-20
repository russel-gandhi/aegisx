---
phase: 02-foundation
plan: 01
subsystem: data-tier
tags: [postgres, ddl, seed-data, infra]
status: complete

dependency-graph:
  requires: []
  provides:
    - "infra/postgres/initdb/001_schema.sql (27-table, 21-FK Bible Section 4.1 schema)"
    - "infra/postgres/seed/001_seed.sql (both demo systems + 10 injected gaps)"
    - "infra/verify-schema.sh (ENV-02 gate)"
    - "infra/verify-seed.sh (ENV-03 gate)"
    - "infra/apply-seed.sh (seed runner)"
  affects:
    - "plan 02-05 (evaluate_opa_policy integration payloads mirror these row shapes)"
    - "plan 02-08 (CI invokes all three scripts)"
    - "Phase 3 SENT-2-02 (A2 Compliance agent queries these rows)"
    - "Phase 4 SENT-3-01 (evidence graph built from this state)"

tech-stack:
  added: []
  patterns:
    - "docker compose exec -T postgres psql for all schema/seed assertions, no host DB client required"
    - ".env loaded via `set -a; . ./.env; set +a`, guarded for missing-file, falling back to compose defaults"
    - "ON CONFLICT (id) DO NOTHING as the sole permitted deviation from Bible-literal seed SQL, for re-runnability"

key-files:
  created:
    - infra/postgres/initdb/001_schema.sql
    - infra/postgres/seed/001_seed.sql
    - infra/apply-seed.sh
    - infra/verify-schema.sh
    - infra/verify-seed.sh
  modified:
    - infra/README.md

decisions:
  - "Confirmed 02-RESEARCH.md's table-count correction: the Bible's Section 4.1 DDL block is 27 CREATE TABLE statements / 21 FOREIGN KEY constraints, not the 20 tables the research prose stated (list was correct, arithmetic was not) — built and verified against 27/21."
  - "Header comments in both SQL files were worded to avoid literally containing the grep-target phrases ('REFERENCES', 'ON CONFLICT (id) DO NOTHING') so the plan's own acceptance-criteria grep counts stay exact — this was a real collision hit during execution, not a hypothetical."

actuals:
  tokens: 6800
  tasks: 3
  commits: 4
---

# Phase 02 Plan 01: Postgres Data Tier (Schema + Seed) Summary

Delivered the full Bible Section 4.1 Postgres schema (27 tables, 21 FK constraints, 8 nanosecond-epoch BIGINT columns) auto-loaded via initdb bind mount, plus a re-runnable seed script populating both demo systems and all 10 deliberately-injected compliance gaps, each backed by an exit-code gate proven in both the pass and fail direction against a live container.

## What Was Built

**Task 1 — Schema (`infra/postgres/initdb/001_schema.sql`, `infra/verify-schema.sh`):**
- Proved the initdb bind-mount path live with a 2-table mount-proof step (`gxp_systems`, `documents`) before spending the full transcription — confirmed both tables existed after a genuinely destroyed-volume cold start.
- Extended to all 27 `CREATE TABLE` statements in the Bible's own declaration order (every `REFERENCES` target already declared above it). Preserved `VARCHAR(50)` string primary keys, the single `UUID` PK (`document_chunks.chunk_id`), all 8 `_ns BIGINT` nanosecond-epoch columns, all 4 `JSONB` columns, and the Bible's only two `NOT NULL` constraints beyond primary keys.
- `infra/verify-schema.sh` asserts table count == 27, FK count == 21, each of the 27 tables individually via `to_regclass`, and `_ns BIGINT` column count == 8 — printing per-check PASS/FAIL lines, then `SCHEMA OK`/`SCHEMA FAILED`.
- Failure path proven live: renamed the schema file, cold-started, confirmed `verify-schema.sh` exits non-zero and names every missing table (not just a count mismatch), then restored the file and re-verified green.

**Task 2 — Seed (`infra/postgres/seed/001_seed.sql`, `infra/apply-seed.sh`, `infra/verify-seed.sh`):**
- 13 `INSERT` statements: both demo systems (`GXP-MFG-DEMO-01` unhealthy, `BUS-IT-DEMO-02` healthy) plus all 10 injected gap records, every literal value byte-identical to Bible Section 5. Every INSERT carries `ON CONFLICT (id) DO NOTHING` — the plan's one sanctioned mechanical deviation, for safe re-runs.
- `infra/apply-seed.sh` streams the seed file into the container over stdin (the seed directory is deliberately not bind-mounted), and refuses to run against a schema-less database with a message pointing at `infra/verify-schema.sh` rather than a raw psql relation error — proven live against an actually-schema-less DB.
- `infra/verify-seed.sh` asserts both systems present, all 10 gaps present with their distinguishing fields, and a nanosecond-magnitude guard (zero seeded `_ns` values below `1e18`) that would catch a second/millisecond-epoch unit mistake the other checks would miss.
- Idempotency proven live: `apply-seed.sh` run twice consecutively, second run reports 0 rows inserted per statement (`INSERT 0 0`), exits 0.

**Task 3 — Documentation (`infra/README.md`):**
- Added a `## Data tier (Stage 1)` section: the initdb-only-runs-on-empty-volume gotcha (the single most likely point of confusion), the full reset sequence, why the seed directory is not bind-mounted, a 10-row gap-to-Rego-rule table (all 10 rule IDs cited from Bible Section 3.3, per CLAUDE.md Rule 13 — never from model recall), and the nanosecond-epoch multiplier warning.
- `git diff --stat` confirms additions only — the Phase 1 content was extended, not rewritten.

## Verification

Ran the plan's full verification sequence end-to-end against a genuinely destroyed environment:
```
docker compose down -v --remove-orphans
docker compose up -d --wait
bash infra/health-check.sh    → ALL HEALTHY, exit 0 (Phase 1's ENV-01 gate not regressed)
bash infra/verify-schema.sh   → SCHEMA OK, exit 0
bash infra/apply-seed.sh      → SEED APPLIED, exit 0
bash infra/apply-seed.sh      → SEED APPLIED, exit 0 (idempotent)
bash infra/verify-seed.sh     → SEED OK, exit 0
```
Both failure paths (missing schema table, apply-seed against schema-less DB) were separately proven live and the environment restored to green before committing.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `verify-seed.sh` check_eq stripped internal whitespace, breaking a multi-word string comparison**
- **Found during:** first `bash infra/verify-seed.sh` run after seeding
- **Issue:** `check_eq()` used `tr -d '[:space:]'` to normalize psql output, which also stripped the space inside `'DataSync Solutions'`, producing a false FAIL (`DataSyncSolutions` != `DataSync Solutions`)
- **Fix:** changed to `tr -d '\r'` (strip only the Windows/docker-exec carriage return, not internal spaces)
- **Files modified:** `infra/verify-seed.sh`
- **Commit:** `783ed43` (fixed before the file was ever committed with the bug — no separate fix commit needed)

**2. [Rule 1 - Bug] Grep-target phrases appearing in my own header comments broke acceptance-criteria counts**
- **Found during:** Task 1 count verification (`grep -c 'REFERENCES'` returned 22, not 21) and Task 2 (`grep -c 'ON CONFLICT (id) DO NOTHING'` returned 14, not 13)
- **Issue:** header comments describing the file's own content happened to contain the literal grep-target phrases, double-counting against the real SQL usages
- **Fix:** reworded both header comments to describe the same fact without the literal phrase (e.g. "every foreign key target declared above it" instead of "every REFERENCES target...")
- **Files modified:** `infra/postgres/initdb/001_schema.sql`, `infra/postgres/seed/001_seed.sql`
- **Commit:** fixed before first commit of each file — no separate fix commit needed

**3. [Rule 1 - Bug] File mode did not register as executable on first commit**
- **Found during:** post-commit check of Task 1
- **Issue:** `core.filemode` is `false` on this Windows checkout, so `chmod 755` on the working-tree file did not translate into git's index mode — `infra/verify-schema.sh` landed as `100644` in the first commit
- **Fix:** `git update-index --chmod=+x` followed by a small dedicated commit; applied `git update-index --chmod=+x` *before* staging for Task 2's scripts so they landed correctly as `100755` in their first commit
- **Files modified:** `infra/verify-schema.sh`
- **Commit:** `864a591`

## Known Stubs

None. All five artifacts are fully functional against the live environment — no placeholder logic, no empty stub bodies.

## Self-Check: PASSED

- `infra/postgres/initdb/001_schema.sql` — FOUND
- `infra/postgres/seed/001_seed.sql` — FOUND
- `infra/apply-seed.sh` — FOUND, mode 100755
- `infra/verify-schema.sh` — FOUND, mode 100755
- `infra/verify-seed.sh` — FOUND, mode 100755
- `infra/README.md` — FOUND, Data tier section present
- Commit `ed95350` — FOUND in `git log --oneline`
- Commit `864a591` — FOUND in `git log --oneline`
- Commit `783ed43` — FOUND in `git log --oneline`
- Commit `4ae987f` — FOUND in `git log --oneline`
