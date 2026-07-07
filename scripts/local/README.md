# Running without Docker (macOS)

Scripts to run the full GraphVisAgent stack directly on macOS, without Docker.

## Prerequisites

- Homebrew PostgreSQL (`brew install postgresql@15` — any version ≥ 14 works;
  the binaries do not need to be on `PATH`)
- Python 3.12+ (`python3`)
- Node.js / npm
- A configured `.env` at the repo root (`cp .env.sample .env`, then fill in
  the keys). The `.env.sample` defaults (`POSTGRES_HOST=localhost`,
  `POSTGRES_PORT=5433`, `NETWORKX_API_URL=http://localhost:8001`) already
  match this setup. Docker-internal hostnames (`db`, `backend`,
  `networkx-api`) are rewritten to `localhost` automatically, so the same
  `.env` works for both Docker and non-Docker runs.

## Usage

```bash
scripts/local/start.sh    # start everything (idempotent)
scripts/local/status.sh   # show what is running / healthy
scripts/local/stop.sh     # stop everything (DB data is kept)
scripts/local/stop.sh --keep-db   # stop app services, leave PostgreSQL up
```

`start.sh` brings up, in order:

| Service      | Port                        | Notes                                   |
| ------------ | --------------------------- | --------------------------------------- |
| PostgreSQL   | `$POSTGRES_PORT` (5433)     | cluster lives in `.local/pgdata`        |
| networkx-api | 8001                        | uvicorn `--reload`                      |
| backend      | 8000                        | runs `alembic upgrade head` first       |
| frontend     | 5173                        | vite dev server                         |

Everything the runner creates lives under `.local/` (git-ignored):
`pgdata/` (database), `venv/` (shared Python env for backend +
networkx-api), `logs/*.log`, and `run/*.pid`.

## Notes

- The Docker stack and the local stack use the same ports, so only one can
  run at a time. `start.sh` detects the conflict and tells you to
  `docker compose down` first.
- The local PostgreSQL cluster (`.local/pgdata`) is separate from the Docker
  volume (`pgdata`), so the two setups do **not** share data.
- Local connections use `trust` auth, so `POSTGRES_PASSWORD` is not enforced
  (development only; the DB listens on localhost only).
- Python dependencies are reinstalled automatically when either
  `requirements.txt` changes; force a reinstall by deleting
  `.local/requirements.sha` (or all of `.local/venv`).
- Use a specific Python for the venv with `PYTHON=/path/to/python3.12
  scripts/local/start.sh` (only affects venv creation on first run).
