#!/usr/bin/env bash
# Show the status of the no-Docker local stack (macOS).
set -euo pipefail

. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

# Read ports from .env when available, but don't require it just for status.
if [ -f "$ROOT_DIR/.env" ]; then
  load_env
else
  POSTGRES_PORT="${POSTGRES_PORT:-5433}"
fi

report() {
  # $1 = service name, $2 = health URL ("" = skip health check)
  local name="$1" url="$2" pid health=""
  pid="$(service_pid "$name")"
  if [ -z "$pid" ]; then
    printf "  %-13s stopped\n" "$name"
    return 0
  fi
  if [ -n "$url" ]; then
    if curl -fsS -o /dev/null --max-time 3 "$url" 2>/dev/null; then
      health="healthy"
    else
      health="NOT RESPONDING"
    fi
  fi
  printf "  %-13s running (pid %s) %s\n" "$name" "$pid" "$health"
}

echo "Local stack status:"
if PG_BIN="$(find_pg_bin)" && pg_running; then
  printf "  %-13s running (port %s, data .local/pgdata)\n" postgres "$POSTGRES_PORT"
else
  printf "  %-13s stopped\n" postgres
fi
report networkx-api "http://localhost:$NX_PORT/health"
report backend "http://localhost:$BACKEND_PORT/health"
report frontend "http://localhost:$FRONTEND_PORT"
