#!/usr/bin/env bash
# Stop the no-Docker local stack started by scripts/local/start.sh (macOS).
#
# Usage: stop.sh [--keep-db]
#   --keep-db   leave PostgreSQL running (only stop the app services)
#
# Database files in .local/pgdata are always preserved.
set -euo pipefail

. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

KEEP_DB=0
for arg in "$@"; do
  case "$arg" in
    --keep-db) KEEP_DB=1 ;;
    *) echo "Usage: $0 [--keep-db]" >&2; exit 1 ;;
  esac
done

stop_service() {
  # $1 = service name
  local name="$1" pidfile pid cmd i
  pidfile="$(pidfile_of "$name")"
  pid="$(service_pid "$name")"
  if [ -z "$pid" ]; then
    echo "  $name: not running"
    rm -f "$pidfile"
    return 0
  fi
  # Only kill processes that clearly belong to this project.
  cmd="$(ps -p "$pid" -o command= 2>/dev/null || true)"
  case "$cmd" in
    *"$ROOT_DIR"*) ;;
    *)
      echo "  $name: pid $pid no longer belongs to this project, removing stale pidfile"
      rm -f "$pidfile"
      return 0
      ;;
  esac
  kill "$pid" 2>/dev/null || true
  for i in $(seq 1 10); do
    kill -0 "$pid" 2>/dev/null || break
    sleep 1
  done
  if kill -0 "$pid" 2>/dev/null; then
    echo "  $name: did not exit after 10s, sending SIGKILL"
    kill -9 "$pid" 2>/dev/null || true
  fi
  rm -f "$pidfile"
  echo "  $name: stopped (pid $pid)"
}

echo "==> Stopping services"
stop_service frontend
stop_service backend
stop_service networkx-api

# Sweep leftovers (e.g. uvicorn --reload workers orphaned by a lost pidfile).
pkill -f "$VENV_DIR/bin/uvicorn" 2>/dev/null || true
pkill -f "$ROOT_DIR/frontend/node_modules/.bin/vite" 2>/dev/null || true

if [ "$KEEP_DB" -eq 1 ]; then
  echo "  postgres: left running (--keep-db)"
else
  if PG_BIN="$(find_pg_bin)" && pg_running; then
    "$PG_BIN/pg_ctl" -D "$PGDATA_DIR" stop -m fast >/dev/null
    echo "  postgres: stopped (data kept in .local/pgdata)"
  else
    echo "  postgres: not running"
  fi
fi

echo "Done."
