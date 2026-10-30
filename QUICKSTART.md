# Quick Start Guide

## Prerequisites

- Docker and Docker Compose
- An API key for at least one LLM provider — or LM Studio running locally if you
  want to use a local model instead

## Setup

1. **Create your `.env`** from the sample at the repository root:

```bash
cp .env.sample .env
```

`.env.sample` documents every variable. At minimum, set:

- `SECRET_KEY` — generate one with `openssl rand -hex 32`
- `LLM_PROVIDER` — `google`, `anthropic`, `openai`, or `lmstudio`
- the API key for the provider you chose (`GOOGLE_API_KEY`, `ANTHROPIC_API_KEY`,
  `OPENAI_API_KEY`), or `LM_STUDIO_BASE_URL` for a local model

The database defaults (`POSTGRES_*`) work as shipped.

2. **Start all services**:

```bash
docker compose up -d
```

| Service | URL |
|---|---|
| Frontend | http://localhost:5173 |
| Backend API + docs | http://localhost:8000 / http://localhost:8000/docs |
| NetworkX API | http://localhost:8001 |
| PostgreSQL | `localhost:5433` on the host (5432 inside the network) |

The Postgres port is **5433 on the host** by default, so it does not collide with
a local Postgres install. Change it with `POSTGRES_PORT` in `.env`.

3. **Wait for the services to come up** (about 30 seconds):

```bash
docker compose ps
docker compose logs -f backend
```

## Using the application

1. Open http://localhost:5173 and register an account.
2. Create a new chat.
3. Upload a GraphML file — `sample_data/karate_club.graphml` is a good first one.
4. Ask for what you want in English or Japanese:

```
Show people with many friends as larger
友達が多い人を大きく表示して
```

The agent interprets the request, computes degree centrality, maps it to node
size, and explains what it did. Other things to try:

```
Show bridge nodes as larger          橋渡しをしている人を大きく表示して
Show influential nodes as larger     影響力のある人を大きく表示して
Create a subgraph of the largest connected component
```

You can switch the LLM provider and model from the selector in the chat UI; the
choice is remembered per chat.

## Running without Docker

`scripts/local/start.sh` runs the whole stack on macOS without Docker, keeping
its state under `.local/`. See `scripts/local/README.md`.

To run a single service against an already-running stack:

```bash
cd backend       && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
cd networkx-api  && uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
cd frontend      && npm install && npm run dev
```

Python dependencies are declared in each service's `requirements.txt` and
resolved into hash-checked `requirements.lock` files. Docker installs the locks.
The root `pyproject.toml` configures lint and typing checks. Run
`scripts/update-python-locks` with uv installed to refresh Python locks, then run
the regression checks. Frontend dependencies are installed with `npm ci`.

## Tests

```bash
cd backend       && pytest
cd networkx-api  && python -m pytest
cd frontend      && npm run test:ci && npm run lint
```

## Browser and PostgreSQL regression checks

The test stack uses a separate, ephemeral database and a deterministic assistant.
HTTP, MCP, graph calculations, tuning, stored messages and SSE are real. No LLM
key or LM Studio is required.

```bash
docker compose -p graphvis-tests -f docker-compose.evaluation.yml -f docker-compose.test.yml up -d --build --wait
cd frontend
npm ci
npx playwright install chromium
npm run test:e2e
cd ..
docker compose -p graphvis-tests -f docker-compose.evaluation.yml exec -T evaluation-db psql -U evaluation -d graphvis_evaluation -c 'CREATE DATABASE graphvis_test'
docker compose -p graphvis-tests -f docker-compose.evaluation.yml exec -T -e TEST_POSTGRES_URL=postgresql+psycopg2://evaluation:evaluation@evaluation-db:5432/graphvis_test evaluation-backend python -m pytest -q
# Stop only the disposable test stack:
docker compose -p graphvis-tests -f docker-compose.evaluation.yml -f docker-compose.test.yml down -v
```

Browser failures retain a screenshot and trace under `frontend/test-results/`.
The lock regression rejects database names other than `*_test` or `test_*`.
GitHub Actions runs these checks on pushes and PRs, and reports dependency
updates weekly. Dependabot proposes npm, Docker and Actions updates.

To update running images, back up PostgreSQL first, then rebuild with
`docker compose build --pull` and recreate with `docker compose up -d`.
A `docker compose up` alone does not refresh an existing base image.
PostgreSQL major upgrades require a separate dump/restore or `pg_upgrade` plan;
do not point a newer major image at the existing data directory.

## Troubleshooting

**Services won't start**

```bash
docker compose logs
docker compose down && docker compose up -d
```

**Database connection errors** — reset the volume (this deletes all data):

```bash
docker compose down -v && docker compose up -d
```

**The frontend can't reach the backend** — confirm http://localhost:8000/docs
loads, then check the browser console for CORS errors and `CORS_ORIGINS` in
`.env`.

**The LLM doesn't respond** — check `LLM_PROVIDER` and the matching API key, then
`docker compose logs backend`. If calls hang rather than fail, you may be hitting
the container egress issue described in `.env.sample` (`PREFER_IPV6_GAI_CONF` /
`DISABLE_CONTAINER_IPV6`); pick at most one and recreate the stack.

**SSE connection issues** — confirm you are logged in, then reload the page.

## Gemini CLI (optional)

`.gemini/settings.json` holds the MCP server config. It refers to the GitHub
token as `${GITHUB_MCP_PAT}` (Gemini CLI expands `$VAR` and loads the root
`.env`) and must set `context.fileName` to `AGENTS.md`; without it Gemini CLI
looks for a `GEMINI.md` that does not exist. `.gemini/` is gitignored, so a
fresh clone has to recreate that setting. Do not create `.gemini/.env`: it
takes precedence over the root `.env` and hides the Google credentials.

## Stopping

```bash
docker compose down       # stop
docker compose down -v    # stop and reset the database
```

## Next steps

- [AGENTS.md](AGENTS.md) — how the repository is organised and how to change it
- [specification/](specification/README.md) — the design decisions behind the system (Japanese)
- More sample networks are in `sample_data/`
