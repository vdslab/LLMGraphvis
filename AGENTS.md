# AGENTS.md — GraphVisAgent

Chat-driven network visual analytics (master's thesis). The user uploads GraphML
and drives analysis and encoding through conversation; an LLM agent turns intent
into MCP calls against a NetworkX service, and the result reaches a D3 canvas
over SSE.

This is the single source of agent instructions; `CLAUDE.md` and
`.agent/rules/` only point here.

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
| **Code** — docstrings, `Field(description=...)`, types | The facts: what a tool or parameter does, the schema |
| **AGENTS.md** (this file) | How to work here: where things live, how to add, run and test, invariants |
| **`specification/`** (Japanese) | **Why**: decisions and rationale, contracts, diagrams of intent |

A fact derivable from the code belongs in the code: endpoint tables, tool
listings, DDL and counts went stale before.

**New features are spec-driven**: a short ADR in `specification/4_Decisions/`
(copy `0000-template.md`), then code, then the rationale folded into
`2_Technical_Details/`. Existing behaviour is *not* retro-specified.

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
| What a token count means, and its cost | `UsageData` in `llm/providers/types.py` (ADR 0025), `llm/pricing.py` |
| What an attribute means (`role`, `measurement`) | `networkx-api/app/logic/attribute_semantics.py` (ADR 0030) |

Tool docstrings and `Field` descriptions are **prompt surface**, sent to the
model verbatim. Write them for a reader with no other context, and never describe
a parameter as effective when it is not (see `scale`/`center`).

### Skills

Markdown with frontmatter (`name`, `description`, `triggers`, `related_tools`).
The system prompt carries a one-line index; the model pulls a procedure with
`skill_load`. Triggers are substring-matched, so avoid short or generic ones.

Adding one: a `.md` file in `skills/definitions/` with **English and Japanese
triggers** (`tests/test_skills_loader.py`). Frontmatter: scalars and string lists.

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

Priority bands, lower first and load-bearing: **10-39 normalize**, **40-69
guards**, **90-100 audit**. A `deny` becomes the tool result so the model can
self-correct; `defer` is for a recoverable unmet prerequisite (no `TOOL_ERROR`).
Hooks fail **open**. Rationale: `specification/2_Technical_Details/1_Backend.md`.

Adding a hook: `@hook(...)` in `hooks/builtin/`, module added to
`registry.load_builtin_hooks()`. `app.services.llm.hooks.registry` is the
`HookRegistry` *instance* shadowing the submodule; import `load_builtin_hooks`
from the package.

### What the chat panel is told

Two backend → frontend contracts, specified in `specification/2_Technical_Details/2_Frontend.md`.

**SSE events**: emitted from `llm/emitters.py`, consumed in
`frontend/src/hooks/useChatConnection.js`. `thinking_stream` is *model reasoning*
only; pipeline status goes through `emit_progress`. Only a terminal event
(`message`, `message_complete`, `error`) calls `chatStore.endTurn()`.

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

**To add a tool**: `@mcp.tool()` + `@handle_tool_errors`, exported from its
package's `__init__.py`; no schema is registered by hand (anything saying to edit
`backend/app/services/llm_service.py` is stale). Run `python -m app.mcp.manifest`
in `networkx-api/` to refresh `common/mcp_tools.json`, and list the tool in a
skill's `related_tools` (or `SEARCH_ONLY` in
`backend/tests/test_skill_tool_references.py`, with a reason), or tests fail (ADR 0027).
Add a skill *only* for procedural guidance, a hook *only* for enforcement.
Procedures live only in skills; the MCP server serves no prompts.
The backend caches tool definitions for `MCP_TOOLS_CACHE_TTL` seconds (default 300).

### Invariants that are easy to get wrong

Rationale: `specification/2_Technical_Details/3_NetworkXAPI.md`.

- **`size` is an area, not a radius**: the frontend renders
  `r = sqrt(size * 10 / π)` (`NetworkGraph.jsx`). Tool descriptions and
  `visualization_builder` say so too; keep the three in sync.
- **Layout, then render.** `layout_*` only stores coordinates; nothing is drawn
  until `visualization_generate`.
- **Coordinates are renormalized to [-1000, 1000]**, so a layout's
  `scale`/`center` are visually inert; never offer them as a zoom
  (`visualization_set_viewport` is the zoom).
- **Layouts are weighted by default, only from the imported `edges.weight`.**
  `WeightRole` (`logic/layouts/base.py`): `STRENGTH` applies automatically,
  `DISTANCE` never, `NONE` has no weight. Other numeric edge attributes are
  offered, never chosen.
- **Styles persist; setting cannot clear them.** `visualization_reset_style` is
  the only way back. The highlight is a style channel; the viewport is one-shot
  and never saved (ADR 0023).
- **Focus is a view, not an extraction.** Highlight to look; extract only to
  change the scope of analysis.
- **Results do not grow with the network** (ADR 0024): per-node/edge tools take
  a `limit`, return the top entries plus a summary, and say what they omitted.
- **One layout, one declaration.** Each declares its nx call, parameter
  allowlist, tuning, `WeightRole` and `prepare` step in one `@register` in
  `logic/layouts/`; `logic/layout.py` never branches on a layout name.
- **Derived attributes**: read the name from the tool's return message
  (`{algorithm}_community`, `{layout}_x`). Every writer calls
  `update_attribute_cache_metadata`, which stamps provenance, `role` and
  `measurement`; without it a computed value lists as imported data.
- **Layout quality is measured where it is drawn.** `layout_quality.normalize_like_renderer`
  is the only coordinate transform; the renderer calls it too.
- **Strength weights are median-normalized** before networkx sees them.
  Distance weights are not.

### Layout rules (ADR 0017)

- **Numbers live in code** (`@register` `tune`/`knobs`, `layout_quality.py`),
  never in a skill; tests reject digits in layout skills.
- **Meaning and direction of a parameter** go in its `Field(description=...)`;
  skills carry only strategy.
- **Two skill layers**: `layout` is the shared procedure; a `layout-<name>`
  skill exists only for `knobs` or a prerequisite, lists its `layout_<name>`
  tool, and names only parameters it accepts. Partitioned layouts share
  `layout-partitioned`.
- **`layout_suggest_parameters` is read-only.** Applying a candidate is a call
  to the real `layout_*` tool, so tuning replay (ADR 0016) stays correct.
- Adding a tunable layout: `knobs` on its `@register`, `FORCE_LAYOUTS` in
  `hooks/builtin/tuning.py` (ADR 0018), a `layout-<name>` skill if knobs interact.

### MCP resources

`networkx-api/app/mcp/resources.py` serves the `network://…` resources that
`llm/context.py` reads directly. Each must pass **`mime_type="application/json"`**
(`tests/test_mcp_integration.py`). They swallow exceptions into `{"error": ...}`,
so a broken one looks like an empty network (`test_resources_return_data_not_errors`).

### Deprecated but retained

`network_initialize`, `visualization_apply_layout` (= `visualization_generate`)
and `analysis_detect_communities` (= per-algorithm tools) stay for old
conversations; never use them in new code. `DEPRECATED_TOOL_NAMES` in
`llm/tool_catalog.py` hides them from `tool_search`.

## Running and testing

```bash
docker compose up -d                 # db / backend:8000 / networkx-api:8001 / frontend:5173
scripts/local/start.sh               # non-Docker macOS runner (state under .local/)

cd backend       && pytest
cd networkx-api  && pytest tests     # run from this dir; there is no pytest.ini here
cd frontend      && npm test && npm run lint
```

Schema changes need an Alembic revision in `backend/alembic/versions/` and
`python -m common.schema_doc` (from `backend/`) to regenerate the ER diagram
`common/schema.md`; a test fails otherwise (ADR 0031). Lint: root
`pyproject.toml` (ruff, line-length 88; long `Field` descriptions in
`mcp/tools/` are the E501 exception). There is **no CI**.

## Known rough edges

- `mypy` reports pre-existing errors in `common/models.py` and the
  provider/history modules.
- Ad-hoc `verify_*.py` / `repro_*.py` / `debug_*.py` scripts are not tests.
- `test_agents_md_facts.py` skips in Docker (it needs the repo root); run it on
  the host after editing this file.

## Secrets and local config

`.env` (repo root, gitignored) holds every credential; add new secrets there.
Gemini CLI setup is in `QUICKSTART.md`; never create `.gemini/.env`, which
shadows the root `.env`.
