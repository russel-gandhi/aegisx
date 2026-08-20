#!/usr/bin/env bash
set -uo pipefail

# infra/verify-persistence.sh
#
# Automated assertion for D-05: Postgres and Qdrant data survive a plain
# `docker compose down` / `up` cycle via named volumes (postgres_data,
# qdrant_data), and are destroyed only by the destructive volumes-removal
# flag (deliberately not spelled out here so this file itself never
# contains that invocation).
#
# WARNING: unlike infra/health-check.sh, this script DOES mutate the
# environment. It stops and restarts the full stack (`down` with no `-v`,
# then `up -d --wait`). It writes small probe rows/collections to both
# Postgres and Qdrant to prove the round trip, and removes them again via
# an EXIT trap so a passing (or failing) run leaves no residue behind that
# could pollute the Phase 2 seed data (SENT-1-02).
#
# Usage:
#   bash infra/verify-persistence.sh
#
# Exits 0 and prints "PERSISTENCE OK" only when every assertion below
# passed. Exits non-zero and prints "PERSISTENCE FAILED" naming the
# failing step otherwise.

# cd to the repo root, derived from this script's own location, so it
# works when invoked from any directory.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
cd "$SCRIPT_DIR/.." || exit 1

# dc(): run `docker compose` if available, else fall back to the
# hyphenated `docker-compose` binary — same wrapper as infra/health-check.sh.
dc() {
  if docker compose version >/dev/null 2>&1; then
    docker compose "$@"
  else
    docker-compose "$@"
  fi
}

# Same defaults the Compose file itself uses (docker-compose.yml:
# POSTGRES_USER:-sentinel, POSTGRES_DB:-sentinel).
PGUSER="${POSTGRES_USER:-sentinel}"
PGDB="${POSTGRES_DB:-sentinel}"

PROBE_TABLE="gsd_persistence_probe"
PROBE_COLLECTION="gsd_persistence_probe"

FAILED_STEP=""

# Cleanup trap: always try to remove both probes, whether we succeeded or
# failed, so a broken run never leaves residue behind. Errors from the
# cleanup calls themselves are ignored (best-effort) — the point is to not
# leave state, not to assert the removal itself succeeded.
cleanup() {
  dc exec -T postgres psql -v ON_ERROR_STOP=1 -U "$PGUSER" -d "$PGDB" \
    -c "DROP TABLE IF EXISTS ${PROBE_TABLE};" >/dev/null 2>&1 || true
  dc exec -T qdrant curl -fsS -X DELETE \
    "http://localhost:6333/collections/${PROBE_COLLECTION}" >/dev/null 2>&1 || true
}
trap cleanup EXIT

fail() {
  FAILED_STEP="$1"
  echo "PERSISTENCE FAILED: ${FAILED_STEP}"
  exit 1
}

echo "== Step 1: write probes to Postgres and Qdrant =="

dc exec -T postgres psql -v ON_ERROR_STOP=1 -U "$PGUSER" -d "$PGDB" \
  -c "CREATE TABLE IF NOT EXISTS ${PROBE_TABLE} (id int primary key); INSERT INTO ${PROBE_TABLE} VALUES (1) ON CONFLICT DO NOTHING;" \
  || fail "writing Postgres probe row"

dc exec -T qdrant curl -fsS -X PUT "http://localhost:6333/collections/${PROBE_COLLECTION}" \
  -H 'content-type: application/json' \
  -d '{"vectors":{"size":4,"distance":"Cosine"}}' \
  || fail "creating Qdrant probe collection"

echo "== Step 2: cycle the stack (down, then up) — no -v, no --volumes =="

dc down || fail "docker compose down"

dc up -d --wait --wait-timeout 180 postgres qdrant opa || fail "docker compose up --wait after cycle"

echo "== Step 3: re-read and assert both probes survived =="

PG_COUNT="$(dc exec -T postgres psql -v ON_ERROR_STOP=1 -U "$PGUSER" -d "$PGDB" \
  -tAc "SELECT count(*) FROM ${PROBE_TABLE};" 2>/dev/null | tr -d '[:space:]')"

if [ "$PG_COUNT" != "1" ]; then
  fail "Postgres probe row did not survive the down/up cycle (got '${PG_COUNT}', want '1')"
fi

if ! dc exec -T qdrant curl -fsS "http://localhost:6333/collections/${PROBE_COLLECTION}" >/dev/null 2>&1; then
  fail "Qdrant probe collection did not survive the down/up cycle"
fi

echo "== Step 4: re-assert full stack health =="

if ! bash infra/health-check.sh; then
  fail "infra/health-check.sh reported not-healthy after the persistence cycle"
fi

echo
echo "PERSISTENCE OK"
exit 0
