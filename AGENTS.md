# AGENTS.md — GraphVisAgent

Chat-driven network visual analytics. The user uploads a GraphML file and drives
all analysis and visual encoding through conversation; an LLM agent turns intent
into MCP tool calls against a NetworkX service, and the result is pushed to a D3
canvas over SSE. Master's thesis project.

This file is the single source of agent instructions; `CLAUDE.md` and
`.agent/rules/` point here. Do not duplicate content into them.

## Services

| Service | Port | Role |
|---|---|---|
| `backend/` | 8000 | Auth, chat, **the agent loop** (LLM client + MCP client) |
| `networkx-api/` | 8001 | All graph algorithms, exposed as an **MCP server** at `/mcp/sse` |
| `frontend/` | 5173 | React + D3. Draws what the backend sends; computes nothing |
| `db` | 5433 → 5432 | Postgres. Models are shared via `common/models.py` |

Setup: `QUICKSTART.md`.

## Documentation policy

| Place | Holds |
|---|---|
| **Code** — docstrings, `Field(description=...)`, types | The facts: what a tool does, what a parameter means, the schema |
| **AGENTS.md** (this file) | How to work here: where things live, how to add one, how to run and test, the invariants |
| **`specification/`** (Japanese) | **Why**: design decisions and rationale, contracts, diagrams of intent |

If a fact can be derived mechanically from the code, it belongs in the code.
Endpoint tables, tool listings, DDL and counts went stale before; do not
reintroduce them.

**New features are spec-driven**: write a short ADR in `specification/4_Decisions/`
(copy `0000-template.md`), implement, then fold the rationale into the relevant
`2_Technical_Details/` document. Existing behaviour is *not* retro-specified.

## House rules

- Run the application with Docker (`docker compose up -d`).
- Before writing code, produce a task list and wait for approval.
- Commit often. Always use `git mv` when moving or renaming a file.
- If a browser check fails or the console errors, stop and capture the log.
- After a UI/CSS change, verify visually in a browser before declaring it done.

## Where behaviour lives

| Concern | Location |
|---|---|
| Always-true policy (role, minimalism, user agency, tool-execution rule) | `backend/app/services/llm/prompts.py` |
| Procedural know-how, loaded on demand | `backend/app/services/llm/skills/definitions/*.md` |
| Enforced rules and side effects | `backend/app/services/llm/hooks/builtin/` |
| What a tool does and what its parameters mean | the tool's docstring and `Field(description=...)` in `networkx-api/app/mcp/tools/` |
| What the model sees of a tool result | `backend/app/services/llm/observations.py` |
| What a token count means, and its cost | `UsageData` in `llm/providers/types.py` (every adapter converts to it, ADR 0025), `llm/pricing.py` |

Tool docstrings and `Field` descriptions are **prompt surface**, sent to the
model verbatim. Write them for a reader with no other context, and never describe
a parameter as effective when it is not (see `scale`/`center`).

### Skills

Markdown files with a frontmatter block (`name`, `description`, `triggers`,
`related_tools`). The system prompt carries a one-line index; the model pulls a
full procedure with `skill_load`. Triggers are substring-matched against the
user's message, so avoid one-character or generic triggers.

Adding one: drop a `.md` file in `skills/definitions/`. Give it **both English
and Japanese triggers** — users write Japanese (`tests/test_skills_loader.py`
enforces this). The frontmatter takes scalars and string lists only.

Exposure lasts the whole turn and survives an `ask_user` answer or a confirmed
tuning panel (ADR 0014, 0016), never the response that activated it. Four places tell the model this; change them together.

### Hooks

Registered by decorator against tool-name patterns, dispatched from `engine.py`:

| Event | Can |
|---|---|
| `TURN_START` | append blocks to the system prompt |
| `PRE_TOOL` | **allow / modify args / defer / deny** |
| `POST_TOOL` | render, switch the active network |
| `TOOL_ERROR` | abort the turn (fires on a failure *or* a denial) |
| `NO_TOOL_CALLS` | request one more round |
| `TURN_END` | log the turn summary |

Priority bands, lower runs first: **10-39 normalize** (rewrite arguments),
**40-69 guards** (validate and refuse), **90-100 audit**. Ordering is
load-bearing. A `deny` is recorded as the tool result so the model can
self-correct; use `defer` for a recoverable unmet prerequisite (no
`TOOL_ERROR`). Hooks fail **open**. Rationale: `specification/2_Technical_Details/1_Backend.md`.

Adding a hook: write it in `hooks/builtin/`, decorate with `@hook(...)`, and add
the module to `registry.load_builtin_hooks()`. `app.services.llm.hooks.registry`
is the `HookRegistry` *instance*, shadowing the submodule — import
`load_builtin_hooks` from the package.

### What the chat panel is told

Two backend → frontend contracts, specified in `specification/2_Technical_Details/2_Frontend.md`.

**SSE events** are emitted from `llm/emitters.py` and consumed in
`frontend/src/hooks/useChatConnection.js`. `thinking_stream` means *model
reasoning* only — pipeline status goes through `emit_progress`. Only a terminal
event (`message`, `message_complete`, `error`) ends a turn and calls
`chatStore.endTurn()`; `render_update` must not.

**In-band markup** survives into the stored message: `llm/markup.py` lists the
tags, `frontend/src/utils/parseMessageContent.js` parses them. `<thought>` is
written by `engine.py` and by nothing else.

## MCP tools

Auto-discovered from `@mcp.tool()` functions in
`networkx-api/app/mcp/tools/{domain}/`. Naming is `domain_verb`: `network_*`,
`node_*`, `subgraph_*`, `analysis_*`, `layout_*`, `visualization_*`. Local tools
in `backend/.../local_tools.py`: `switch_to_main_network`,
`switch_to_parent_network`, `skill_load`, `tool_search`, `ask_user`,
`offer_parameter_tuning`, `apply_parameter_tuning`.

**To add a tool**: write the function with `@mcp.tool()` + `@handle_tool_errors`
and export it from its package's `__init__.py`. There is no schema to register
by hand — anything telling you to edit `backend/app/services/llm_service.py` is stale.
Add a skill *only* for procedural guidance, a hook *only* for enforcement.
The backend caches tool definitions for `MCP_TOOLS_CACHE_TTL` seconds (default 300).

### Invariants that are easy to get wrong

Rationale: `specification/2_Technical_Details/3_NetworkXAPI.md`.

- **`size` is an area, not a radius**: the frontend renders
  `r = sqrt(size * 10 / π)` (`NetworkGraph.jsx`). Tool descriptions and
  `visualization_builder` say so too; keep the three in sync.
- **Layout, then render.** `layout_*` only stores coordinates; nothing is drawn
  until `visualization_generate`.
- **Coordinates are renormalized to [-1000, 1000]**, making every layout's
  `scale`/`center` visually inert. Never offer them as a zoom; zoom is
  `visualization_set_viewport`.
- **Layouts are weighted by default, but only from the imported weight.**
  `WeightRole` in `logic/layouts/base.py`: `STRENGTH` applies automatically,
  `DISTANCE` never does, `NONE` has no weight parameter. Other numeric edge
  attributes are offered, never chosen. Weights live in `edges.weight`.
- **Styles persist and cannot be cleared by setting them.**
  `visualization_reset_style` is the only way back. The highlight is a style
  channel too; the viewport is a one-shot instruction and is never saved (ADR 0023).
- **Focus is a view, not an extraction.** Highlight to look; extract only to
  change the scope of analysis.
- **Results do not grow with the network** (ADR 0024). A tool returning one
  entry per node or edge takes a `limit`, returns the top entries plus a
  whole-graph summary and says what it omitted.
- **One layout, one declaration.** Each declares its nx call, parameter
  allowlist, tuning, `WeightRole` and `prepare` step in one `@register` in
  `logic/layouts/`; `logic/layout.py` never branches on a layout name.
- **Derived attribute names** come from the tool's return message:
  `{algorithm}_community`, `{layout}_x`/`{layout}_y`.
- **Layout quality is measured where it is drawn.** `layout_quality.normalize_like_renderer`
  is the only coordinate transform; the renderer calls it too.
- **Strength weights are median-normalized** before networkx sees them.
  Distance weights are not.

### Layout rules (ADR 0017)

- **Numbers live in code**: defaults, ranges and thresholds in a layout's
  `@register` (`tune`, `knobs`) and `layout_quality.py`, never in a skill.
  Tests reject digits in layout skills.
- **Meaning and direction of a parameter** go in its `Field(description=...)`;
  skills carry only strategy.
- **Two skill layers**: `layout` holds the shared procedure. An algorithm gets a
  `layout-<name>` skill only if it has `knobs` or a prerequisite procedure, and
  its `related_tools` must list its `layout_<name>` tool. The partitioned
  layouts share `layout-partitioned`. A skill may name only parameters its tool accepts.
- **`layout_suggest_parameters` is read-only.** Applying a candidate is a call
  to the real `layout_*` tool, so tuning replay (ADR 0016) stays correct.
- Adding a tunable layout: `knobs` on its `@register`, add it to
  `FORCE_LAYOUTS` in `hooks/builtin/tuning.py` (ADR 0018), then a
  `layout-<name>` skill if its knobs interact.

### MCP resources

`networkx-api/app/mcp/resources.py` serves the `network://…` resources the
backend reads directly to build context in `llm/context.py`.

- Every resource must pass **`mime_type="application/json"`** (enforced by
  `tests/test_mcp_integration.py`).
- Resources swallow exceptions into `{"error": ...}`, so a broken one looks like
  an empty network. Hence `test_resources_return_data_not_errors`.

### Deprecated but retained

`network_initialize` and `visualization_apply_layout` (same as
`visualization_generate`) are kept for old conversations. Do not use them in new code.

## Running and testing

```bash
docker compose up -d                 # db / backend:8000 / networkx-api:8001 / frontend:5173
scripts/local/start.sh               # non-Docker macOS runner (state under .local/)

cd backend       && pytest
cd networkx-api  && pytest tests     # run from this dir; there is no pytest.ini here
cd frontend      && npm test && npm run lint
```

Schema changes need an Alembic revision in `backend/alembic/versions/`.
Lint/typecheck config is the root `pyproject.toml` (ruff line-length 88, mypy).
Long `Field(description=...)` strings in `mcp/tools/` are the established
exception to E501; new non-tool modules should be clean. There is **no CI**.

## Known rough edges

- `mypy` reports pre-existing errors in `common/models.py` and the
  provider/history modules.
- Ad-hoc `verify_*.py` / `repro_*.py` / `debug_*.py` scripts under
  `networkx-api/`, `backend/` and `scripts/` are not tests.

## Secrets and local config

`.env` (repo root) holds every credential and is gitignored; keep it that way
and reference new secrets from it. Gemini CLI setup (`.gemini/settings.json`)
is in `QUICKSTART.md`; never create `.gemini/.env`, which shadows the root `.env`.
