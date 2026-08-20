#!/usr/bin/env bash
set -uo pipefail

# infra/health-check.sh
#
# Pure assertion script for ENV-01. It observes and reports; it never
# starts, stops, or modifies the environment. Waiting for readiness is
# Compose's own `--wait` bring-up flag's job (see RESEARCH.md
# "Don't Hand-Roll") — this script does not poll.
#
# Usage:
#   bash infra/health-check.sh [service ...]
#
# With no args, checks the full ENV-01 set: postgres qdrant opa.
# Exits 0 and prints "ALL HEALTHY" only when every requested service is
# both Compose-healthy AND reachable on its published loopback port.
# Exits non-zero and prints "NOT ALL HEALTHY" otherwise.

# cd to the repo root, derived from this script's own location, so it
# works when invoked from any directory.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
cd "$SCRIPT_DIR/.." || exit 1

# dc(): run `docker compose` if available, else fall back to the
# hyphenated `docker-compose` binary. Docker Desktop ships the former as
# a shim over v2; supporting both means the gate does not depend on
# which form the developer's machine provides.
dc() {
  if docker compose version >/dev/null 2>&1; then
    docker compose "$@"
  else
    docker-compose "$@"
  fi
}

# Services to check. Default to the exact set ENV-01 names.
if [ "$#" -gt 0 ]; then
  services=("$@")
else
  services=(postgres qdrant opa)
fi

overall_status=0

for svc in "${services[@]}"; do
  health_ok=0
  port_ok=0
  reason=""

  # 1. Container health.
  cid="$(dc ps -q "$svc" 2>/dev/null)"
  if [ -z "$cid" ]; then
    reason="not running"
  else
    health_status="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}no-healthcheck{{end}}' "$cid" 2>/dev/null)"
    if [ "$health_status" = "healthy" ]; then
      health_ok=1
    else
      reason="container: ${health_status:-unknown}"
    fi
  fi

  # 2. Host port reachability — what ENV-01's "on ports 5432/6333/8181"
  # actually claims, and which container health alone does not prove.
  # Uses `node` rather than `curl` — curl is unreliable under Windows
  # Git Bash (MSYS path and SSL mangling) and this is the dev platform.
  case "$svc" in
    postgres)
      if node -e "require('net').connect(5432,'127.0.0.1').on('connect',function(){process.exit(0)}).on('error',function(){process.exit(1)})" >/dev/null 2>&1; then
        port_ok=1
      else
        reason="${reason:+$reason; }port: 5432 unreachable"
      fi
      ;;
    qdrant)
      if node -e "fetch('http://127.0.0.1:6333/readyz').then(function(r){process.exit(r.ok?0:1)}).catch(function(){process.exit(1)})" >/dev/null 2>&1; then
        port_ok=1
      else
        reason="${reason:+$reason; }port: 6333 unreachable"
      fi
      ;;
    opa)
      if node -e "fetch('http://127.0.0.1:8181/health').then(function(r){process.exit(r.ok?0:1)}).catch(function(){process.exit(1)})" >/dev/null 2>&1; then
        port_ok=1
      else
        reason="${reason:+$reason; }port: 8181 unreachable"
      fi
      ;;
    *)
      reason="${reason:+$reason; }unknown service"
      ;;
  esac

  if [ "$health_ok" -eq 1 ] && [ "$port_ok" -eq 1 ]; then
    printf '%-12s GREEN\n' "$svc"
  else
    printf '%-12s RED    (%s)\n' "$svc" "$reason"
    overall_status=1
  fi
done

echo
if [ "$overall_status" -eq 0 ]; then
  echo "ALL HEALTHY"
else
  echo "NOT ALL HEALTHY"
fi

exit "$overall_status"
