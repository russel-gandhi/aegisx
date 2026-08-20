#!/usr/bin/env bash
set -uo pipefail

# infra/apply-seed.sh
#
# SENT-1-02 / ENV-03. Streams infra/postgres/seed/001_seed.sql into the
# running postgres container over stdin. infra/postgres/seed/ is
# deliberately NOT bind-mounted into the container (unlike
# infra/postgres/initdb/), so seeding only happens when this script is
# explicitly invoked — a cold `docker compose up` never silently
# re-materialises demo data.
#
# Safe to run repeatedly: every INSERT in 001_seed.sql carries
# ON CONFLICT (id) DO NOTHING, so a second run is a no-op, not an error.
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

dc exec -T -e PGPASSWORD="${POSTGRES_PASSWORD:-}" postgres \
  psql -U "$PGUSER" -d "$PGDB" -v ON_ERROR_STOP=1 < infra/postgres/seed/001_seed.sql

status=$?
if [ "$status" -ne 0 ]; then
  echo "SEED FAILED" >&2
  exit "$status"
fi

echo "SEED APPLIED"
