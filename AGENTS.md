# AGENTS.md — GraphVisAgent

Chat-driven network visual analytics. The user uploads a GraphML file and drives
all analysis and visual encoding through conversation; an LLM agent translates
intent into MCP tool calls against a NetworkX service, and the result is pushed
to a D3 canvas over SSE. Master's thesis project.

This file is the single source of agent instructions; `CLAUDE.md` and
`.agent/rules/` point here. Do not duplicate content into them.

## Services

| Service | Port | Role |
|---|---|---|
| `backend/` | 8000 | Auth, chat, **the agent loop** (LLM client + MCP client) |
| `networkx-api/` | 8001 | All graph algorithms, exposed as an **MCP server** at `/mcp/sse` |
| `frontend/` | 5173 | React + D3. Draws what the backend sends; computes nothing |
| `db` | 5433 → 5432 | Postgres. Models are shared via `common/models.py` |

`common/models.py` is shared by both Python services. Setup: `QUICKSTART.md`.

## Documentation policy

Three places hold knowledge, each with one job. Putting a fact in the wrong one
is how documentation rots.

| Place | Holds |
|---|---|
| **Code** — docstrings, `Field(description=...)`, types | The facts: what a tool does, what a parameter means, the schema |
| **AGENTS.md** (this file) | How to work here: where things live, how to add one, how to run and test, the invariants |
| **`specification/`** (Japanese) | **Why** it is this way: design decisions and rationale, contracts, diagrams of intent |

The test: **can this fact be derived mechanically from the code?** If yes it
belongs in the code, not in `specification/`. Endpoint tables, tool listings,
DDL, component inventories and point-in-time counts are exactly what went stale
before; do not reintroduce them.

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

Agent behaviour is split across four places. Know which one you are changing.

| Concern | Location |
|---|---|
| Always-true policy (role, minimalism, user agency, tool-execution rule) | `backend/app/services/llm/prompts.py` |
| Procedural know-how, loaded on demand | `backend/app/services/llm/skills/definitions/*.md` |
| Enforced rules and side effects | `backend/app/services/llm/hooks/builtin/` |
| What a tool does and what its parameters mean | the tool's docstring and `Field(description=...)` in `networkx-api/app/mcp/tools/` |

Tool docstrings and `Field` descriptions are **prompt surface**, sent to the
model verbatim. Write them for a reader with no other context, and never describe
a parameter as effective when it is not (see `scale`/`center`).

### Skills

Markdown files with a frontmatter block (`name`, `description`, `triggers`,
`related_tools`). The system prompt carries only a one-line index; the model
pulls a full procedure with `skill_load`.

Adding one: drop a `.md` file in `skills/definitions/`; it is discovered
automatically. Give it **both English and Japanese triggers** — the app's users
write Japanese, so an English-only trigger list makes the skill invisible to
them (`tests/test_skills_loader.py` enforces this). The frontmatter parser
accepts scalars and string lists only; anything richer belongs in the body.

### Hooks

Registered by decorator against tool-name patterns, dispatched from the ReAct
loop in `engine.py`:

| Event | Can |
|---|---|
| `TURN_START` | append blocks to the system prompt |
| `PRE_TOOL` | **allow / modify args / deny** |
| `POST_TOOL` | render, switch the active network |
| `TOOL_ERROR` | abort the turn (fires on a failure *or* a denial) |
| `NO_TOOL_CALLS` | request one more round |
| `TURN_END` | log the turn summary |

Priority bands, ascending, so lower runs first:

```
10-39  normalize     rewrite arguments
40-69  guards        validate and refuse (sees corrected arguments)
90-100 audit         tallies and logging
```

**Ordering is load-bearing**: a new guard belongs in 40–69, a new normalizer in
10–39. A `deny` is not an exception — the engine records it as the tool result,
so the model reads the reason and self-corrects. Hooks fail **open**. Rationale:
`specification/2_Technical_Details/1_Backend.md`.

Adding a hook: write it in `hooks/builtin/`, decorate with `@hook(...)`, and add
the module to the import list in `registry.load_builtin_hooks()`. Note that
`app.services.llm.hooks.registry` resolves to the `HookRegistry` *instance*
exported by the package `__init__`, which shadows the same-named submodule —
import `load_builtin_hooks` from the package, not the module.

### What the chat panel is told

Two one-sided contracts run backend → frontend, so they change together; both
are specified in `specification/2_Technical_Details/2_Frontend.md`.

**SSE events** are emitted from `llm/emitters.py` and consumed in
`frontend/src/hooks/useChatConnection.js`. `thinking_stream` means *model
reasoning* and nothing else — a pipeline step or status line goes through
`emit_progress`. Only a terminal event (`message`, `message_complete`, `error`)
ends a turn and calls `chatStore.endTurn()`; `render_update` must not.

**In-band markup** survives into the stored message: `llm/markup.py` lists the
tags, `frontend/src/utils/parseMessageContent.js` parses them. `<thought>` is
written by `engine.py` around model reasoning and by nothing else.

## MCP tools

Auto-discovered from `@mcp.tool()`-decorated functions in
`networkx-api/app/mcp/tools/{domain}/`. Naming is `domain_verb`: `network_*`,
`node_*`, `subgraph_*`, `analysis_*`, `layout_*`, `visualization_*`. Plus three
in-process tools in `backend/.../local_tools.py` (`switch_to_main_network`,
`switch_to_parent_network`, `skill_load`).

**To add a tool**: write the function in the right `tools/` module with
`@mcp.tool()` + `@handle_tool_errors` and export it from that package's
`__init__.py`. There is no schema to register by hand — anything telling you to
edit `backend/app/services/llm_service.py` is stale (that file does not exist).
Then add a skill *only* if it needs procedural guidance, a hook *only* if it
needs enforcement.

The backend caches discovered tool definitions for `MCP_TOOLS_CACHE_TTL` seconds
(default 300); call `mcp_client.invalidate_tools_cache()` or wait it out.

### Invariants that are easy to get wrong

The rationale for each is in `specification/2_Technical_Details/3_NetworkXAPI.md`.

- **`size` is an area, not a radius**: the frontend renders
  `r = sqrt(size * 10 / π)` (`NetworkGraph.jsx`). Also stated in the tool
  descriptions and `visualization_builder`; keep the three in sync.
- **Layout, then render.** `layout_*` only stores coordinates; nothing is drawn
  until `visualization_generate`.
- **Coordinates are renormalized to [-1000, 1000]**, making every layout's
  `scale`/`center` visually inert. Say so rather than offering them as a zoom.
- **Layouts are weighted by default, but only from the imported weight.** A
  layout declares what a weight *means* to it (`WeightRole` in
  `logic/layouts/base.py`): `STRENGTH` applies automatically, `DISTANCE` never
  does, `NONE` has no weight parameter. Any *other* numeric edge attribute is
  offered, never chosen. `weight='<name>'` picks one, `weight='none'` opts out.
  Weights live in `edges.weight`, never as an EdgeAttribute.
- **Styles persist and cannot be cleared by setting them.**
  `visualization_reset_style` is the only way back to uniform.
- **One layout, one declaration.** Each declares its nx call, parameter
  allowlist, tuning, `WeightRole` and `prepare` step in one `@register` in
  `logic/layouts/`; `logic/layout.py` never branches on a layout name. Adding a
  layout = one `@register`ed function plus its MCP tool.
- **Derived attribute names** come from the tool's return message — communities
  save to `{algorithm}_community`, layouts to `{layout}_x`/`{layout}_y`.

### MCP resources

`networkx-api/app/mcp/resources.py` serves the `network://…` resources the
backend reads directly (not via the LLM) to build the system-prompt context and
post-upload overview in `backend/app/services/llm/context.py`.

- Every resource must pass **`mime_type="application/json"`** (enforced by
  `tests/test_mcp_integration.py`).
- Resources swallow exceptions into `{"error": ...}`, so one pointed at a renamed
  helper fails **silently** — it looks like an empty network. That is why
  `test_resources_return_data_not_errors` runs each against a real DB.

### Deprecated but retained

`network_initialize` (import + a hardcoded layout + render) and
`visualization_apply_layout` (identical to `visualization_generate`) are kept so
old conversations do not break. Do not use them in new code.

## Running and testing

```bash
docker compose up -d                 # db / backend:8000 / networkx-api:8001 / frontend:5173
scripts/local/start.sh               # non-Docker macOS runner (state under .local/)

cd backend       && pytest
cd networkx-api  && pytest tests     # run from this dir; there is no pytest.ini here
cd frontend      && npm test && npm run lint
```

Lint/typecheck config is the single root `pyproject.toml` (ruff line-length 88,
mypy). The codebase does not fully comply with E501 — long
`Field(description=...)` strings are the established style in `mcp/tools/`. New
non-tool modules should be clean. There is **no CI** and no pre-commit config.

## Known rough edges

- `mypy` reports pre-existing errors in `common/models.py` (SQLAlchemy
  `declarative_base` typing) and in the provider/history modules.
- Dozens of ad-hoc `verify_*.py` / `repro_*.py` / `debug_*.py` scripts sit under
  `networkx-api/`, `backend/` and `scripts/`. They are not tests.

## Secrets and local config

`.env` (repo root) holds every credential: Postgres, `SECRET_KEY`, the LLM
provider keys and `GITHUB_MCP_PAT`. It is gitignored (`.gitignore:276`) and has
never been committed. Keep it that way — put new secrets there and reference
them rather than inlining them.

`.gemini/settings.json` holds MCP server config, refers to the token as
`${GITHUB_MCP_PAT}` (Gemini CLI expands `$VAR` and loads the root `.env`), and
sets `context.fileName` to `AGENTS.md` — without it Gemini CLI looks for a
`GEMINI.md` that no longer exists. **`.gemini/` is gitignored**, so a fresh
clone must recreate that setting. **Do not create `.gemini/.env`** — it takes
precedence over the root `.env` in the same directory and would shadow the
Google credentials the CLI needs.
