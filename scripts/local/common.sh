# Shared configuration for the no-Docker local runner (macOS).
# Sourced by start.sh / stop.sh / status.sh — not meant to be executed directly.

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LOCAL_DIR="$ROOT_DIR/.local"
RUN_DIR="$LOCAL_DIR/run"
LOG_DIR="$LOCAL_DIR/logs"
PGDATA_DIR="$LOCAL_DIR/pgdata"
VENV_DIR="$LOCAL_DIR/venv"

BACKEND_PORT=8000
NX_PORT=8001
FRONTEND_PORT=5173

# ---------------------------------------------------------------------------
# Locate PostgreSQL binaries (Homebrew installs keg-only versions off PATH).
# ---------------------------------------------------------------------------
find_pg_bin() {
  if command -v pg_ctl >/dev/null 2>&1; then
    dirname "$(command -v pg_ctl)"
    return 0
  fi
  local prefix candidate
  for prefix in /opt/homebrew/opt /usr/local/opt; do
    for candidate in "$prefix"/postgresql@17 "$prefix"/postgresql@16 \
                     "$prefix"/postgresql@15 "$prefix"/postgresql@14 \
                     "$prefix"/postgresql; do
      if [ -x "$candidate/bin/pg_ctl" ]; then
        echo "$candidate/bin"
        return 0
      fi
    done
  done
  return 1
}

# ---------------------------------------------------------------------------
# Environment: load .env, then rewrite Docker-only values for host execution.
# ---------------------------------------------------------------------------
load_env() {
  if [ ! -f "$ROOT_DIR/.env" ]; then
    echo "ERROR: $ROOT_DIR/.env not found." >&2
    echo "       Create it first:  cp .env.sample .env  (then fill in the keys)" >&2
    exit 1
  fi
  set -a
  # shellcheck disable=SC1091
  . "$ROOT_DIR/.env"
  set +a

  export POSTGRES_USER="${POSTGRES_USER:-postgres}"
  export POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-postgres}"
  export POSTGRES_DB="${POSTGRES_DB:-graphvis}"
  export POSTGRES_PORT="${POSTGRES_PORT:-5433}"

  # "db", "backend", "networkx-api" only resolve inside the compose network.
  case "${POSTGRES_HOST:-}" in
    ""|db) export POSTGRES_HOST=localhost ;;
  esac
  case "${NETWORKX_API_URL:-}" in
    ""|*//networkx-api*) export NETWORKX_API_URL="http://localhost:$NX_PORT" ;;
  esac
  case "${VITE_API_URL:-}" in
    ""|*//backend*) export VITE_API_URL="http://localhost:$BACKEND_PORT" ;;
  esac
  case "${VITE_NX_API_URL:-}" in
    ""|*//networkx-api*) export VITE_NX_API_URL="http://localhost:$NX_PORT" ;;
  esac

  # Container path (or a stale path) for ADC breaks google-genai on the host.
  if [ -n "${GOOGLE_APPLICATION_CREDENTIALS:-}" ] && [ ! -r "$GOOGLE_APPLICATION_CREDENTIALS" ]; then
    local fallback="$ROOT_DIR/backend/application_default_credentials.json"
    if [ -r "$fallback" ]; then
      export GOOGLE_APPLICATION_CREDENTIALS="$fallback"
    else
      echo "WARN: GOOGLE_APPLICATION_CREDENTIALS points to an unreadable file; unsetting it for this run." >&2
      unset GOOGLE_APPLICATION_CREDENTIALS
    fi
  fi
}

# ---------------------------------------------------------------------------
# Process helpers
# ---------------------------------------------------------------------------
pidfile_of() { echo "$RUN_DIR/$1.pid"; }

# Returns the recorded PID if the service is alive, empty otherwise.
service_pid() {
  local pidfile pid
  pidfile="$(pidfile_of "$1")"
  [ -f "$pidfile" ] || return 0
  pid="$(cat "$pidfile" 2>/dev/null)"
  if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
    echo "$pid"
  fi
}

port_in_use() {
  lsof -nP -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1
}

pg_running() {
  [ -d "$PGDATA_DIR" ] && "$PG_BIN/pg_ctl" -D "$PGDATA_DIR" status >/dev/null 2>&1
}
