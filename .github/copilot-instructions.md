# Copilot Instructions for LLMGraph-vis

## Project Overview

LLMGraph-vis is a web application for interactive graph (network) visualization and analysis, integrating Large Language Models (LLMs) for chat-driven insights. The system targets researchers and developers who want to explore graph features and gain insights without deep technical expertise.

## Architecture & Major Components

- **Frontend (React, Vite)**: SPA for UI, state managed via Zustand. Key screens: Home, Login/Register, NetworkChat (main graph/chat UI).
- **Backend API (FastAPI)**: Handles authentication, business logic, proxies requests to NetworkXMCP and LLM APIs. Key endpoints: `/auth`, `/chat`, `/network`.
- **NetworkXMCP (FastAPI, NetworkX)**: Stateful microservice for graph calculations (centrality, layout, normalization). Connects directly to PostgreSQL for caching results.
- **Database (PostgreSQL)**: Stores user info, chat history, graph data, and cached results.

## Data Flow & Integration

- Frontend communicates with Backend via REST API (axios client, JWT auth).
- Backend proxies heavy graph calculations to NetworkXMCP and interacts with external LLM APIs (e.g., OpenAI, Gemini).
- NetworkXMCP caches results in DB; only recalculates if cache is missing.
- JWT tokens are stored in browser `localStorage` for session persistence.

## Developer Workflows

- **Install dependencies:** `yarn`
- **Local dev server:** `yarn start` (hot reload)
- **Build static site:** `yarn build` (output in `build/`)
- **Deploy (GitHub Pages):** `yarn deploy` (use `USE_SSH=true` for SSH, or set `GIT_USER`)

## Project-Specific Patterns

- **State Management:** Use Zustand stores for `auth`, `network`, and `chat` state. See `src/stores/` (if present).
- **API Client:** All requests attach JWT; auto-redirect to login on token expiry.
- **Graph Operations:** Calculations (centrality/layout) and visualization updates are separated; see NetworkXMCP endpoints for details.
- **Versioned Docs:** Specs and design docs are versioned under `specification_versioned_docs/` and `versioned_docs/`.

## Key Files & Directories

- `src/pages/`, `src/components/`: Frontend UI and logic
- `specification/`, `specification_versioned_docs/`: Architecture, API, and design specs
- `design_docs/`, `versioned_docs/`: Design documentation
- `build/`: Static site output

## External Dependencies

- Docusaurus (site generator)
- React, Zustand, axios (frontend)
- FastAPI, SQLAlchemy, NetworkX (backend/services)
- PostgreSQL (database)
- LLM APIs (OpenAI, Gemini, etc.)

## Example: Graph Calculation Flow

1. User uploads GraphML via frontend
2. Backend API stores data, proxies calculation to NetworkXMCP
3. NetworkXMCP computes centrality/layout, caches results in DB
4. Frontend fetches processed graph for visualization

---

For unclear or missing conventions, consult `specification/README.md` and versioned docs. Please ask for feedback if any section is ambiguous or incomplete.
