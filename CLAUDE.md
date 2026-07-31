# GraphVisAgent — developer guide for AI assistants

Chat-driven network visual analytics. The user uploads a GraphML file and drives
all analysis and visual encoding through conversation; an LLM agent translates
intent into MCP tool calls against a NetworkX service, and the result is pushed
to a D3 canvas over SSE. Master's thesis project; the authoritative spec is the
Japanese `specification/` tree.

## Services

| Service | Port | Role |
|---|---|---|
| `backend/` | 8000 | Auth, chat, **the agent loop** (LLM client + MCP client) |
| `networkx-api/` | 8001 | All graph algorithms, exposed as an **MCP server** at `/mcp/sse` |
| `frontend/` | 5173 | React + D3. Draws what the backend sends; computes nothing |
| `db` | 5432 | Postgres. Models are shared via `common/models.py` |

`common/models.py` is used by both Python services — a change there affects both.

## Where behaviour lives

Agent behaviour is split across four places. Know which one you are changing.

| Concern | Location |
|---|---|
| Always-true policy (role, minimalism, user agency, tool-execution rule) | `backend/app/services/llm/prompts.py` |
| Procedural know-how, loaded on demand | `backend/app/services/llm/skills/definitions/*.md` |
| Enforced rules and side effects | `backend/app/services/llm/hooks/builtin/` |
| What a tool does and what its parameters mean | the tool's docstring and `Field(description=...)` in `networkx-api/app/mcp/tools/` |

Tool docstrings and `Field` descriptions are **prompt surface** — they are sent
to the model verbatim. Write them for a reader who has no other context, and do
not describe a parameter as effective when it is not (see `scale`/`center`).

### Skills

Markdown files with a small frontmatter block (`name`, `description`,
`triggers`, `related_tools`). The system prompt carries only a one-line index;
the model pulls a full procedure with the `skill_load` tool. This keeps the
always-on prompt small — it was ~16k characters before the split and is ~7.5k
now, with ~23k characters of procedure loaded only when relevant.

Adding a skill: drop a `.md` file in `skills/definitions/`. It is discovered
automatically. Give it **both English and Japanese triggers** — the app's users
write Japanese, and an English-only trigger list makes the skill invisible to
them. `tests/test_skills_loader.py` enforces this.

The frontmatter parser (`skills/loader.py`) is deliberately minimal (scalars and
string lists only, flow or block form) so the project needs no YAML dependency.
Anything richer belongs in the body.

### Hooks

Registered by decorator against tool-name patterns, dispatched from the ReAct
loop in `engine.py`:

| Event | Fires | Can |
|---|---|---|
| `TURN_START` | once, before the first generate() | append blocks to the system prompt |
| `PRE_TOOL` | before every tool call | **allow / modify args / deny** |
| `POST_TOOL` | after a successful call | render, switch the active network |
| `TOOL_ERROR` | after a failure or a denial | abort the turn |
| `NO_TOOL_CALLS` | an iteration called nothing | request one more round |
| `TURN_END` | once, after the loop | log the turn summary |

Priority bands (ascending, so lower runs first):

```
10-39  normalize     rewrite arguments
40-69  guards        validate and refuse (sees corrected arguments)
90-100 audit         tallies and logging
```

**Ordering is load-bearing**: guards must see normalized arguments, so a new
guard belongs in the 40–69 band and a new normalizer in 10–39.

A `deny` is not an exception. The engine records
`{"error": reason, "blocked_by": hook_name}` as the tool result and appends it to
history like any other result, so the model reads the reason and self-corrects.
That is the whole point — a prompt instruction can be skipped, a denial cannot.

Hooks fail **open**: one that raises is logged, counted in `turn_state`, and
treated as "no opinion", so a bug in a guard cannot take down every tool call.

Adding a hook: write it in `hooks/builtin/`, decorate with `@hook(...)`, and add
the module to the import list in `registry.load_builtin_hooks()`.

Note: `app.services.llm.hooks.registry` resolves to the `HookRegistry` *instance*
exported by the package `__init__`, which shadows the same-named submodule.
Import `load_builtin_hooks` from the package, not the module.

## MCP tools

52 tools, auto-discovered from `@mcp.tool()`-decorated functions in
`networkx-api/app/mcp/tools/{domain}/`. Naming is `domain_verb`:
`network_*` (7), `node_*` (6), `subgraph_*` (8), `analysis_*` (8), `layout_*` (13),
`visualization_*` (10). Plus three in-process tools in `backend/.../local_tools.py`
(`switch_to_main_network`, `switch_to_parent_network`, `skill_load`).

**To add a tool**: write the function in the right `tools/` module with
`@mcp.tool()` + `@handle_tool_errors`, and export it from that package's
`__init__.py`. There is no schema to register by hand anywhere — anything that
tells you to edit `backend/app/services/llm_service.py` is stale (that file does
not exist).

The backend caches discovered tool definitions for `MCP_TOOLS_CACHE_TTL` seconds
(default 300). Call `mcp_client.invalidate_tools_cache()` or wait it out after
adding a tool.

### Conventions that are easy to get wrong

- **Two-step layout.** `layout_*` computes and stores coordinates; nothing is
  drawn until `visualization_generate`.
- **`size` is an area, not a radius.** The frontend renders
  `r = sqrt(size * 10 / π)` (`NetworkGraph.jsx`). This convention is duplicated
  in the tool descriptions and `visualization_builder`; keep the three in sync.
- **Coordinates are renormalized to [-1000, 1000]** before drawing, which makes
  every layout's `scale`/`center` parameter visually inert. Say so rather than
  offering them as a way to zoom.
- **Layouts are weighted by default, but only from the imported weight.** A
  layout declares what a weight *means* to it (`WeightRole` in
  `logic/layouts/base.py`): `STRENGTH` (spring, forceatlas2, spectral) is applied
  automatically when `edges.weight` varies and is positive; `DISTANCE`
  (kamada_kawai) never is, because heavier would mean *further apart*; `NONE` has
  no weight parameter at all. Any *other* numeric edge attribute is only ever
  offered, never chosen — it could be a cost, a year or an id. `logic/layouts/weights.py`
  makes that call and returns the note that every layout tool appends to its
  result. `weight='<name>'` picks a different attribute, `weight='none'` opts out.
  Weights live in `edges.weight`, never as an EdgeAttribute (the importer skips
  the key), so `network://{id}/structure`'s `edge_weights` is the only place their
  existence is visible — which is why the agent never asked for them before.
- **Styles persist and cannot be cleared by setting them.** Each
  `visualization_set_*` preserves the channels it was not given, and
  `_save_state` only writes non-`None`. `visualization_reset_style` is the only
  way back to uniform.
- **One layout, one declaration.** `logic/layouts/` holds a module per family
  (mirroring `mcp/tools/layout/`), and each layout declares in one `@register`
  its nx call, its parameter allowlist, its size-based tuning, its `WeightRole`
  and any `prepare` step. `logic/layout.py` orchestrates (graph build, weight,
  cache, persistence) and never branches on a layout name; `LAYOUT_PARAM_KEYS` is
  derived from the registry. **Adding a layout** = one `@register`ed function
  plus its MCP tool. `tests/test_layout_parameters.py` cross-checks the allowlist
  against the installed networkx signatures, and the tool signatures against each
  layout's `WeightRole`.
- **Derived attribute names.** `analysis_detect_communities` saves to
  `{algorithm}_community`, layouts to `{layout}_x`/`{layout}_y`. Read the tool's
  return message for the exact name rather than assuming one.

### MCP resources

`networkx-api/app/mcp/resources.py` serves the `network://…` resources that the
backend reads directly (not via the LLM) to build the system-prompt context and
the post-upload overview in `backend/app/services/llm/context.py`.

- Every resource must pass **`mime_type="application/json"`**. FastMCP labels a
  resource template `text/plain` otherwise, and a client that trusts the label
  discards the body. `tests/test_mcp_integration.py` enforces this.
- Resources swallow exceptions into `{"error": ...}`, so a resource pointed at a
  renamed logic helper fails **silently** — it looks like an empty network.
  `test_resources_return_data_not_errors` executes each one against a real DB
  for that reason; mocking the logic layer would not catch it.

### Deprecated but retained

`network_initialize` (bundles import + a hardcoded layout + render) and
`visualization_apply_layout` (identical to `visualization_generate`). Both are
kept so existing conversations do not break; do not use them in new code.

## Running and testing

```bash
docker compose up -d                 # db / backend:8000 / networkx-api:8001 / frontend:5173
scripts/local/start.sh               # non-Docker macOS runner (state under .local/)

cd backend       && pytest           # 197 tests
cd networkx-api  && pytest tests     # 109 tests — run from this dir; there is no pytest.ini here
cd frontend      && npm test && npm run lint
```

Lint/typecheck config is the single root `pyproject.toml` (ruff line-length 88,
mypy). Note that the existing codebase does not fully comply with E501 — long
`Field(description=...)` strings are the established style in `mcp/tools/`. New
non-tool modules should be clean.

There is **no CI** and no pre-commit config.

## Known rough edges

- `mypy` reports pre-existing errors in `common/models.py` (SQLAlchemy
  `declarative_base` typing) and in the provider/history modules.
- Dozens of ad-hoc `verify_*.py` / `repro_*.py` / `debug_*.py` scripts are
  committed under `networkx-api/`, `backend/`, and `scripts/`. They are not
  tests and are not run by pytest.
- `knowledge.md` still describes pre-refactor tool names.

## Secrets

`.env` (repo root) holds every credential: Postgres, `SECRET_KEY`, the Google /
Vertex credentials, and `GITHUB_MCP_PAT`. It is gitignored (`.gitignore:276`)
and has never been committed. Keep it that way — put new secrets there and
reference them, rather than inlining them in a config file.

`.gemini/settings.json` refers to the token as `${GITHUB_MCP_PAT}`; Gemini CLI
expands `$VAR` / `${VAR}` / `${VAR:-default}` in settings values and loads the
root `.env` automatically. **Do not create `.gemini/.env`** — it takes
precedence over the root `.env` in the same directory, so it would shadow the
Google credentials the CLI needs to authenticate.
