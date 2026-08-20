#!/usr/bin/env bash
set -uo pipefail

# infra/verify-schema.sh
#
# SENT-1-01 / ENV-02 gate. Asserts, against a live Postgres container, that
# the full Bible Section 4.1 schema is present: 27 tables, 21 foreign key
# constraints, 8 nanosecond-epoch BIGINT columns. Runs every assertion
# through `docker compose exec -T postgres psql`, so no host Postgres
# client or Python driver is required. Modelled on infra/health-check.sh's
# per-check PASS/FAIL line + exit-code contract.
#
# Usage:
#   bash infra/verify-schema.sh
#
# Prints one PASS/FAIL line per check, then "SCHEMA OK" (exit 0) or
# "SCHEMA FAILED" (exit non-zero).

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
cd "$SCRIPT_DIR/.." || exit 1

# Load .env if present; fall back to compose defaults otherwise. Guarded so
# a missing .env degrades gracefully rather than aborting under `set -u`.
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

psql_exec() {
  dc exec -T -e PGPASSWORD="${POSTGRES_PASSWORD:-}" postgres \
    psql -U "$PGUSER" -d "$PGDB" -v ON_ERROR_STOP=1 -tA -c "$1" 2>/dev/null
}

overall_status=0

# The 27 table names, in Bible Section 4.1 declaration order.
TABLES=(
  gxp_systems documents document_chunks requirements risks design_elements
  test_cases test_results incidents access_reviews access_records suppliers
  supplier_assessments periodic_evaluations changes change_actions findings
  evidence_refs action_proposals audit_events agent_messages graph_nodes
  graph_edges candidate_memory trusted_memory users sessions
)

# 1. Total base table count == 27.
table_count="$(psql_exec "SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE'" | tr -d '[:space:]')"
if [ "$table_count" = "27" ]; then
  printf '%-60s PASS\n' "table count == 27"
else
  printf '%-60s FAIL (got: %s)\n' "table count == 27" "${table_count:-<none>}"
  overall_status=1
fi

# 2. Total FOREIGN KEY constraint count == 21.
fk_count="$(psql_exec "SELECT count(*) FROM information_schema.table_constraints WHERE table_schema='public' AND constraint_type='FOREIGN KEY'" | tr -d '[:space:]')"
if [ "$fk_count" = "21" ]; then
  printf '%-60s PASS\n' "foreign key count == 21"
else
  printf '%-60s FAIL (got: %s)\n' "foreign key count == 21" "${fk_count:-<none>}"
  overall_status=1
fi

# 3. Each of the 27 tables resolves individually, so a failure names the
# missing table rather than only reporting a count mismatch.
for t in "${TABLES[@]}"; do
  regclass="$(psql_exec "SELECT to_regclass('public.${t}')" | tr -d '[:space:]')"
  if [ "$regclass" = "$t" ]; then
    printf '%-60s PASS\n' "table exists: ${t}"
  else
    printf '%-60s FAIL (missing)\n' "table exists: ${t}"
    overall_status=1
  fi
done

# 4. 8 nanosecond-epoch BIGINT columns (column name ending in _ns, type bigint).
ns_count="$(psql_exec "SELECT count(*) FROM information_schema.columns WHERE table_schema='public' AND column_name LIKE '%\\_ns' AND data_type='bigint'" | tr -d '[:space:]')"
if [ "$ns_count" = "8" ]; then
  printf '%-60s PASS\n' "nanosecond BIGINT column count == 8"
else
  printf '%-60s FAIL (got: %s)\n' "nanosecond BIGINT column count == 8" "${ns_count:-<none>}"
  overall_status=1
fi

echo
if [ "$overall_status" -eq 0 ]; then
  echo "SCHEMA OK"
else
  echo "SCHEMA FAILED"
fi

exit "$overall_status"
