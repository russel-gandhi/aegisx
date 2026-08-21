#!/usr/bin/env bash
set -uo pipefail

# infra/apply-seed.sh
#
# SENT-1-02 / ENV-03, extended by Phase 3 plan 03-04. Streams every
# `*.sql` file in infra/postgres/seed/ into the running postgres container
# over stdin, one at a time in sorted filename order (001_seed.sql, then
# 002_urs_fixture.sql, then any later NNN_*.sql this directory gains).
# infra/postgres/seed/ is deliberately NOT bind-mounted into the container
# (unlike infra/postgres/initdb/), so seeding only happens when this
# script is explicitly invoked — a cold `docker compose up` never silently
# re-materialises demo data.
#
# Safe to run repeatedly: every INSERT in every seed script carries
# ON CONFLICT (id) DO NOTHING, so a second run is a no-op, not an error.
# Application stops at the first script that errors (set -uo pipefail plus
# an explicit per-file status check below) rather than continuing past a
# partial failure.
#
# Usage:
#   bash infra/apply-seed.sh

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
  echo "to load the schema before seeding." >&2
  exit 1
fi

# Apply every seed script in sorted filename order, failing fast on the
# first one that errors rather than continuing past a partial failure.
for seed_file in infra/postgres/seed/*.sql; do
  echo "Applying ${seed_file}..."
  dc exec -T -e PGPASSWORD="${POSTGRES_PASSWORD:-}" postgres \
    psql -U "$PGUSER" -d "$PGDB" -v ON_ERROR_STOP=1 < "$seed_file"

  status=$?
  if [ "$status" -ne 0 ]; then
    echo "SEED FAILED" >&2
    exit "$status"
  fi
done

echo "SEED APPLIED"
