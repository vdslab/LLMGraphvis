#!/usr/bin/env bash
# Start the whole GraphVisAgent stack WITHOUT Docker (macOS).
#
#   PostgreSQL  -> .local/pgdata, port $POSTGRES_PORT (default 5433)
#   networkx-api-> uvicorn, port 8001
#   backend     -> alembic upgrade head + uvicorn, port 8000
#   frontend    -> vite dev server, port 5173
#
# Logs: .local/logs/*.log   PIDs: .local/run/*.pid
# Stop everything with scripts/local/stop.sh
set -euo pipefail

. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/common.sh"

mkdir -p "$RUN_DIR" "$LOG_DIR"

# ---------------------------------------------------------------------------
# Preflight
# ---------------------------------------------------------------------------
PYTHON_BIN="${PYTHON:-python3}"
command -v "$PYTHON_BIN" >/dev/null 2>&1 || { echo "ERROR: python3 not found." >&2; exit 1; }
command -v npm >/dev/null 2>&1 || { echo "ERROR: npm not found (brew install node)." >&2; exit 1; }
if ! PG_BIN="$(find_pg_bin)"; then
  echo "ERROR: PostgreSQL not found. Install it with:  brew install postgresql@15" >&2
  exit 1
fi

load_env

require_port_free() {
  # $1 = port, $2 = service name
  if port_in_use "$1"; then
    echo "ERROR: port $1 is already in use, cannot start $2." >&2
    echo "       If the Docker stack is running, stop it first:  docker compose down" >&2
    exit 1
  fi
}

wait_http() {
  # $1 = url, $2 = service name, $3 = timeout seconds
  local i=0
  until curl -fsS -o /dev/null "$1" 2>/dev/null; do
    i=$((i + 1))
    if [ "$i" -ge "$3" ]; then
      echo "ERROR: $2 did not become healthy within ${3}s. Last log lines:" >&2
      tail -n 30 "$LOG_DIR/$2.log" >&2 || true
      exit 1
    fi
    sleep 1
  done
}

start_bg() {
  # $1 = service name, $2 = working dir, rest = command.
  # `exec` replaces the subshell so the recorded PID is the server itself,
  # not a bash wrapper (stop.sh signals this PID directly).
  local name="$1" dir="$2"
  shift 2
  (cd "$dir" && exec "$@") >>"$LOG_DIR/$name.log" 2>&1 &
  echo $! >"$(pidfile_of "$name")"
  echo "  started $name (pid $(cat "$(pidfile_of "$name")"), log .local/logs/$name.log)"
}

# ---------------------------------------------------------------------------
# 1. PostgreSQL
# ---------------------------------------------------------------------------
echo "==> PostgreSQL (port $POSTGRES_PORT, data .local/pgdata)"
if [ ! -f "$PGDATA_DIR/PG_VERSION" ]; then
  echo "  initializing database cluster..."
  "$PG_BIN/initdb" -D "$PGDATA_DIR" -U "$POSTGRES_USER" --auth=trust --encoding=UTF8 \
    >>"$LOG_DIR/postgres.log" 2>&1
fi
if pg_running; then
  echo "  already running"
else
  require_port_free "$POSTGRES_PORT" postgres
  "$PG_BIN/pg_ctl" -D "$PGDATA_DIR" -l "$LOG_DIR/postgres.log" \
    -o "-p $POSTGRES_PORT -c listen_addresses=localhost" -w start >/dev/null
  echo "  started"
fi
until "$PG_BIN/pg_isready" -h 127.0.0.1 -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -q; do sleep 1; done
if ! "$PG_BIN/psql" -h 127.0.0.1 -p "$POSTGRES_PORT" -U "$POSTGRES_USER" -d postgres -tAc \
    "SELECT 1 FROM pg_database WHERE datname='$POSTGRES_DB'" | grep -q 1; then
  "$PG_BIN/createdb" -h 127.0.0.1 -p "$POSTGRES_PORT" -U "$POSTGRES_USER" "$POSTGRES_DB"
  echo "  created database $POSTGRES_DB"
fi

# ---------------------------------------------------------------------------
# 2. Python virtualenv (shared by backend and networkx-api)
# ---------------------------------------------------------------------------
echo "==> Python dependencies (.local/venv)"
if [ ! -x "$VENV_DIR/bin/python" ]; then
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi
REQ_STAMP="$LOCAL_DIR/requirements.sha"
REQ_HASH="$(cat "$ROOT_DIR/backend/requirements.txt" "$ROOT_DIR/networkx-api/requirements.txt" | shasum | cut -d' ' -f1)"
if [ ! -f "$REQ_STAMP" ] || [ "$(cat "$REQ_STAMP")" != "$REQ_HASH" ]; then
  echo "  installing (this may take a few minutes on first run)..."
  "$VENV_DIR/bin/pip" install -q --upgrade pip
  "$VENV_DIR/bin/pip" install -q \
    -r "$ROOT_DIR/backend/requirements.txt" \
    -r "$ROOT_DIR/networkx-api/requirements.txt"
  echo "$REQ_HASH" >"$REQ_STAMP"
else
  echo "  up to date"
fi

# Make the repo-root `common` package importable from both services.
BASE_PYTHONPATH="${PYTHONPATH:-}"

# ---------------------------------------------------------------------------
# 3. networkx-api
# ---------------------------------------------------------------------------
echo "==> networkx-api (port $NX_PORT)"
if [ -n "$(service_pid networkx-api)" ]; then
  echo "  already running"
else
  require_port_free "$NX_PORT" networkx-api
  export PYTHONPATH="$ROOT_DIR:$ROOT_DIR/networkx-api${BASE_PYTHONPATH:+:$BASE_PYTHONPATH}"
  start_bg networkx-api "$ROOT_DIR/networkx-api" \
    "$VENV_DIR/bin/uvicorn" app.main:app --host 127.0.0.1 --port "$NX_PORT" \
    --reload --timeout-keep-alive 60
fi
wait_http "http://localhost:$NX_PORT/health" networkx-api 60

# ---------------------------------------------------------------------------
# 4. backend (migrations, then the API)
# ---------------------------------------------------------------------------
echo "==> backend (port $BACKEND_PORT)"
export PYTHONPATH="$ROOT_DIR:$ROOT_DIR/backend${BASE_PYTHONPATH:+:$BASE_PYTHONPATH}"
echo "  running alembic migrations..."
(cd "$ROOT_DIR/backend" && "$VENV_DIR/bin/alembic" upgrade head) >>"$LOG_DIR/backend.log" 2>&1
if [ -n "$(service_pid backend)" ]; then
  echo "  already running"
else
  require_port_free "$BACKEND_PORT" backend
  start_bg backend "$ROOT_DIR/backend" \
    "$VENV_DIR/bin/uvicorn" app.main:app --host 127.0.0.1 --port "$BACKEND_PORT" \
    --reload --timeout-keep-alive "${KEEP_ALIVE_TIMEOUT:-86400}"
fi
wait_http "http://localhost:$BACKEND_PORT/health" backend 60

# ---------------------------------------------------------------------------
# 5. frontend
# ---------------------------------------------------------------------------
echo "==> frontend (port $FRONTEND_PORT)"
if [ -n "$(service_pid frontend)" ]; then
  echo "  already running"
else
  require_port_free "$FRONTEND_PORT" frontend
  if [ ! -x "$ROOT_DIR/frontend/node_modules/.bin/vite" ] || \
     [ "$ROOT_DIR/frontend/package-lock.json" -nt "$ROOT_DIR/frontend/node_modules/.package-lock.json" ]; then
    echo "  installing npm dependencies..."
    (cd "$ROOT_DIR/frontend" && npm install) >>"$LOG_DIR/frontend.log" 2>&1
  fi
  start_bg frontend "$ROOT_DIR/frontend" \
    "$ROOT_DIR/frontend/node_modules/.bin/vite" --host
fi
wait_http "http://localhost:$FRONTEND_PORT" frontend 60

echo
echo "All services are up:"
echo "  frontend     http://localhost:$FRONTEND_PORT"
echo "  backend      http://localhost:$BACKEND_PORT  (docs: /docs)"
echo "  networkx-api http://localhost:$NX_PORT"
echo "  postgres     localhost:$POSTGRES_PORT (db: $POSTGRES_DB)"
echo
echo "Logs:   tail -f .local/logs/<service>.log"
echo "Status: scripts/local/status.sh    Stop: scripts/local/stop.sh"
