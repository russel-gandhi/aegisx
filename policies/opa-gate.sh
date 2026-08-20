#!/usr/bin/env bash
set -uo pipefail

# policies/opa-gate.sh
#
# POL-01 assertion gate for the Rego policy bundle (SENT-1-03, Critical
# review). Pure assertion script in the style of infra/health-check.sh: it
# observes and reports, it never starts, stops, or restarts anything. Any
# rule edit requires `docker compose restart opa` first (the compose
# command runs `opa run --server` with no `--watch`, so the live server
# does not pick up file changes on its own) — this script assumes that has
# already happened if a live-server check is expected to reflect edits.
#
# Two checks:
#   1. Unit suite — `opa test policies/`, run via a host `opa` binary if
#      present, otherwise executed inside the running `opa` container.
#   2. Live-server probe — POST a synthetic DRAFT O&M document to the real
#      OPA REST endpoint and assert the expected violation comes back.
#
# Usage: bash policies/opa-gate.sh
# Prints OPA GATE OK / OPA GATE FAILED and exits 0 / non-zero accordingly.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
cd "$SCRIPT_DIR/.." || exit 1

# dc(): run `docker compose` if available, else fall back to the
# hyphenated `docker-compose` binary — same helper pattern as
# infra/health-check.sh, so this gate behaves identically across the two
# supported Compose CLI forms.
dc() {
  if docker compose version >/dev/null 2>&1; then
    docker compose "$@"
  else
    docker-compose "$@"
  fi
}

gate_failed=0

# --- Check 1: opa test ------------------------------------------------

echo "== opa test =="

if command -v opa >/dev/null 2>&1; then
  if opa test policies/ -v; then
    echo "opa test: PASS (host binary)"
  else
    echo "opa test: FAIL (host binary)"
    gate_failed=1
  fi
elif dc exec -T opa /opa test /policies -v; then
  echo "opa test: PASS (container)"
else
  status=$?
  if [ "$status" -eq 127 ] || dc ps -q opa >/dev/null 2>&1 && [ -z "$(dc ps -q opa 2>/dev/null)" ]; then
    echo "opa test: FAIL — no host 'opa' binary found and the 'opa' container is not reachable via docker compose exec."
    echo "  Install opa locally, or run 'docker compose up -d opa' so the container route can be used."
  else
    echo "opa test: FAIL (container)"
  fi
  gate_failed=1
fi

echo

# --- Check 2: live REST probe -----------------------------------------

echo "== live OPA REST probe =="

probe_result="$(node -e "
fetch('http://127.0.0.1:8181/v1/data/sentinel/gxp/violation', {
  method: 'POST',
  headers: { 'content-type': 'application/json' },
  body: JSON.stringify({
    input: {
      documents: [{
        id: 'DOC-2026-OM-99',
        system_id: 'GXP-MFG-DEMO-01',
        doc_type: 'O&M',
        status: 'DRAFT',
      }],
    },
  }),
})
  .then(function (r) { return r.json(); })
  .then(function (j) {
    var v = j.result || [];
    var hit = v.some(function (x) {
      return x.rule_id === 'ANNEX11-S4-DOC-001' && x.record_id === 'DOC-2026-OM-99';
    });
    console.log(JSON.stringify({ ok: hit, raw: j }));
    process.exit(hit ? 0 : 1);
  })
  .catch(function (e) {
    console.log(JSON.stringify({ ok: false, error: String(e) }));
    process.exit(1);
  });
" 2>&1)"
probe_status=$?

echo "$probe_result"

if [ "$probe_status" -eq 0 ]; then
  echo "live probe: PASS"
else
  echo "live probe: FAIL"
  echo "  Hint: 'opa run --server' loads its bundle once at startup (no --watch)."
  echo "  If you just edited policies/gxp_rules.rego, restart the server and re-check:"
  echo "    docker compose restart opa && bash infra/health-check.sh opa"
  gate_failed=1
fi

echo

if [ "$gate_failed" -eq 0 ]; then
  echo "OPA GATE OK"
  exit 0
else
  echo "OPA GATE FAILED"
  exit 1
fi
