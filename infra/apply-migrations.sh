#!/usr/bin/env bash
set -uo pipefail

# infra/apply-migrations.sh
#
# Phase 4, plan 04-02. `infra/postgres/initdb/001_schema.sql` is applied by
# the postgres:16.15 image's own init mechanism, and only on a fresh (empty)
# data directory — see infra/README.md "Data tier (Stage 1)". Any file added
# to infra/postgres/initdb/ *after* a stack has already been brought up once
# (like this plan's 002_change_affects.sql) is therefore never picked up by
# a plain `docker compose up -d` or `restart` against an existing volume.
# This script exists to apply exactly those later-added files to an
# already-running stack, without the `down -v` that would destroy the
# seeded demo data infra/apply-seed.sh has already loaded.
#
# Streams every infra/postgres/initdb/0[2-9]*.sql file (001_schema.sql is
# deliberately excluded — it is the container's own responsibility) into
# the running postgres container over stdin, one at a time in sorted
# filename order, with ON_ERROR_STOP=1 so a mid-file error stops the whole
# run rather than continuing past a partial failure.
#
# Safe to run repeatedly: every statement in every 00N_*.sql file under
# infra/postgres/initdb/ uses `CREATE TABLE IF NOT EXISTS`, so a second run
# is a no-op, not an error.
#
# Usage:
#   bash infra/apply-migrations.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
cd "$SCRIPT_DIR/.." || exit 1

if [ -f ./.env ]; then
  set -a
  # shellcheck disable=SC1091
  . ./.env
  set +a
fi

PGUSER="${POSTGRES_USER:-sentinel}"
PGDB="${POSTGRES_DB:-sentinel}"

dc() {
  if docker compose version >/dev/null 2>&1; then
    docker compose "$@"
  else
    docker-compose "$@"
  fi
}

# Refuse to run against a schema-less database, with a message pointing at
# the schema gate, rather than emitting a wall of raw psql relation errors.
schema_present="$(dc exec -T -e PGPASSWORD="${POSTGRES_PASSWORD:-}" postgres \
  psql -U "$PGUSER" -d "$PGDB" -tA -c "SELECT to_regclass('public.gxp_systems')" 2>/dev/null | tr -d '[:space:]')"

if [ "$schema_present" != "gxp_systems" ]; then
  echo "ERROR: schema not found (public.gxp_systems does not resolve)." >&2
  echo "Run 'bash infra/verify-schema.sh' to diagnose, and if it fails," >&2
  echo "run 'docker compose down -v --remove-orphans && docker compose up -d --wait'" >&2
  echo "to load the base schema before applying migrations." >&2
  exit 1
fi

# Apply every migration file except 001_schema.sql, in sorted filename
# order, failing fast on the first one that errors rather than continuing
# past a partial failure. Filtered by basename (not a numeric glob range)
# so this script never re-applies 001_schema.sql — the container's own
# init-mechanism job — regardless of how many digits later filenames use,
# while still picking up every later-added file automatically.
shopt -s nullglob
all_initdb_files=(infra/postgres/initdb/*.sql)
shopt -u nullglob

migration_files=()
for f in "${all_initdb_files[@]}"; do
  if [ "$(basename "$f")" != "001_schema.sql" ]; then
    migration_files+=("$f")
  fi
done

if [ "${#migration_files[@]}" -eq 0 ]; then
  echo "No migration files found beyond 001_schema.sql — nothing to apply."
  echo "MIGRATIONS APPLIED"
  exit 0
fi

for migration_file in "${migration_files[@]}"; do
  echo "Applying ${migration_file}..."
  dc exec -T -e PGPASSWORD="${POSTGRES_PASSWORD:-}" postgres \
    psql -U "$PGUSER" -d "$PGDB" -v ON_ERROR_STOP=1 < "$migration_file"

  status=$?
  if [ "$status" -ne 0 ]; then
    echo "MIGRATIONS FAILED" >&2
    exit "$status"
  fi
done

echo "MIGRATIONS APPLIED"
