#!/usr/bin/env bash
set -uo pipefail

# infra/verify-seed.sh
#
# SENT-1-02 / ENV-03 gate. Asserts, against a live Postgres container, that
# both demo systems and all 10 deliberately-injected gap records are
# present with their distinguishing fields, and that every seeded `_ns`
# column carries a genuinely nanosecond-magnitude value (Pitfall 2 —
# a second- or millisecond-epoch value would pass every other check here
# and then silently make the Rego date rules in plan 02-02 wrong).
#
# Usage:
#   bash infra/verify-seed.sh
#
# Prints one PASS/FAIL line per check, then "SEED OK" (exit 0) or
# "SEED FAILED" (exit non-zero).

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

psql_exec() {
  dc exec -T -e PGPASSWORD="${POSTGRES_PASSWORD:-}" postgres \
    psql -U "$PGUSER" -d "$PGDB" -v ON_ERROR_STOP=1 -tA -c "$1" 2>/dev/null
}

overall_status=0

check_eq() {
  # check_eq <label> <query> <expected>
  local label="$1" query="$2" expected="$3"
  local actual
  actual="$(psql_exec "$query" | tr -d '\r')"
  if [ "$actual" = "$expected" ]; then
    printf '%-70s PASS\n' "$label"
  else
    printf '%-70s FAIL (expected: %s, got: %s)\n' "$label" "$expected" "${actual:-<none>}"
    overall_status=1
  fi
}

# 1. Both demo systems present.
check_eq "gxp_systems row count == 2" "SELECT count(*) FROM gxp_systems" "2"
check_eq "GXP-MFG-DEMO-01 resolves" "SELECT count(*) FROM gxp_systems WHERE id='GXP-MFG-DEMO-01'" "1"
check_eq "BUS-IT-DEMO-02 resolves" "SELECT count(*) FROM gxp_systems WHERE id='BUS-IT-DEMO-02'" "1"

# 2. Each of the 10 gap records, distinguishing field.
check_eq "Gap 1: DOC-2026-OM-99 status == DRAFT" "SELECT status FROM documents WHERE id='DOC-2026-OM-99'" "DRAFT"
check_eq "Gap 1: DOC-2026-OM-99 doc_type == O&M" "SELECT doc_type FROM documents WHERE id='DOC-2026-OM-99'" "O&M"
check_eq "Gap 2: AR-2026-05 status == PENDING" "SELECT status FROM access_reviews WHERE id='AR-2026-05'" "PENDING"
check_eq "Gap 3: RSK-2024-11 exists" "SELECT count(*) FROM risks WHERE id='RSK-2024-11'" "1"
check_eq "Gap 4: INC-849201 severity == P1" "SELECT severity FROM incidents WHERE id='INC-849201'" "P1"
check_eq "Gap 4: INC-849201 rca_started == false" "SELECT rca_started FROM incidents WHERE id='INC-849201'" "f"
check_eq "Gap 5: URS-042 exists" "SELECT count(*) FROM requirements WHERE id='URS-042'" "1"
check_eq "Gap 5: TC-2026-042 status == DRAFT" "SELECT status FROM test_cases WHERE id='TC-2026-042'" "DRAFT"
check_eq "Gap 6: SUP-2026-01 name == DataSync Solutions" "SELECT name FROM suppliers WHERE id='SUP-2026-01'" "DataSync Solutions"
check_eq "Gap 7: PE-2024-01 exists" "SELECT count(*) FROM periodic_evaluations WHERE id='PE-2024-01'" "1"
check_eq "Gap 8: GXP-MFG-DEMO-01 last_backup_test_ns == 1709251200000000000" "SELECT last_backup_test_ns FROM gxp_systems WHERE id='GXP-MFG-DEMO-01'" "1709251200000000000"
check_eq "Gap 9: ACC-2026-99 is_privileged == true" "SELECT is_privileged FROM access_records WHERE id='ACC-2026-99'" "t"
check_eq "Gap 9: ACC-2026-99 user_status == DEPARTED" "SELECT user_status FROM access_records WHERE id='ACC-2026-99'" "DEPARTED"
check_eq "Gap 10: CR-2026-089 status == CLOSED" "SELECT status FROM changes WHERE id='CR-2026-089'" "CLOSED"
check_eq "Gap 10: CA-2026-089-1 status == OPEN" "SELECT status FROM change_actions WHERE id='CA-2026-089-1'" "OPEN"

# 2b. Phase-3 fixture assertions (infra/postgres/seed/002_urs_fixture.sql,
# D-05): the additive DOC-2026-URS-01 row exists to give A2's
# verify_urs_approved its positive-path test data. This is not one of the
# ten Bible-seeded gaps above, and adds no violation count.
check_eq "Fixture: DOC-2026-URS-01 doc_type == URS" "SELECT doc_type FROM documents WHERE id='DOC-2026-URS-01'" "URS"
check_eq "Fixture: DOC-2026-URS-01 status == APPROVED" "SELECT status FROM documents WHERE id='DOC-2026-URS-01'" "APPROVED"

# 2c. Phase-4 fixture assertions (infra/postgres/seed/003_change_affects_fixture.sql,
# D-03): the additive DE-2026-DB-01 design element and the three
# change_affects rows for CR-2026-089 exist, spanning exactly the three
# expected entity types. Not one of the ten Bible-seeded gaps above, and
# adds no violation count.
check_eq "Fixture: DE-2026-DB-01 exists" "SELECT count(*) FROM design_elements WHERE id='DE-2026-DB-01'" "1"
check_eq "Fixture: change_affects row count for CR-2026-089 == 3" "SELECT count(*) FROM change_affects WHERE change_id='CR-2026-089'" "3"
check_eq "Fixture: CR-2026-089 entity_type set == DESIGN_ELEMENT,DOCUMENT,REQUIREMENT" "SELECT string_agg(DISTINCT entity_type, ',' ORDER BY entity_type) FROM change_affects WHERE change_id='CR-2026-089'" "DESIGN_ELEMENT,DOCUMENT,REQUIREMENT"

# 3. Nanosecond-magnitude guard (Pitfall 2): union of every seeded _ns
# value across the six tables that carry one must contain zero values
# below 1e18 (a second- or millisecond-epoch value would be far smaller).
below_threshold_count="$(psql_exec "
  SELECT count(*) FROM (
    SELECT last_backup_test_ns AS ns FROM gxp_systems WHERE last_backup_test_ns IS NOT NULL
    UNION ALL
    SELECT last_review_date_ns FROM risks WHERE last_review_date_ns IS NOT NULL
    UNION ALL
    SELECT opened_date_ns FROM incidents WHERE opened_date_ns IS NOT NULL
    UNION ALL
    SELECT scheduled_date_ns FROM access_reviews WHERE scheduled_date_ns IS NOT NULL
    UNION ALL
    SELECT reassessment_due_date_ns FROM suppliers WHERE reassessment_due_date_ns IS NOT NULL
    UNION ALL
    SELECT due_date_ns FROM periodic_evaluations WHERE due_date_ns IS NOT NULL
  ) all_ns
  WHERE ns < 1000000000000000000
" | tr -d '[:space:]')"

if [ "$below_threshold_count" = "0" ]; then
  printf '%-70s PASS\n' "nanosecond-magnitude guard (zero sub-1e18 _ns values)"
else
  printf '%-70s FAIL (%s value(s) below 1e18)\n' "nanosecond-magnitude guard (zero sub-1e18 _ns values)" "${below_threshold_count:-<none>}"
  overall_status=1
fi

echo
if [ "$overall_status" -eq 0 ]; then
  echo "SEED OK"
else
  echo "SEED FAILED"
fi

exit "$overall_status"
