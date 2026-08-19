# Cline exploratory prompt evaluation

This directory is a bridge between Cline and a real GraphVisAgent session. It is
for evaluating the current system prompt, Skills, and MCP descriptions—not for
reviewing a Git diff. No scenario files or fixed expected-tool lists are used.

## What runs

`scripts/evaluate` starts an isolated GraphVisAgent stack with an ephemeral
PostgreSQL database. It temporarily selects Cline's LM Studio provider and installs
one stdio MCP server containing only these evaluation operations:

- discover/read the current prompt surfaces;
- start, message, observe, or reset a GraphVisAgent test conversation;
- save the final structured evaluation report.

Cline runs in Plan mode with an otherwise empty workspace. Other configured Cline
MCP servers are disabled for the duration and all Cline configuration bytes are
restored afterward, including on failure. Cline never receives the repository as a
workspace and is instructed to make recommendations only.
The isolated application source mounts are read-only, and the evaluation MCP
disables Python bytecode writes; its only write operation targets run artifacts.

GraphVisAgent itself calls the existing NetworkX MCP. The evaluation bridge records
the response, Skills, tool executions and arguments, visualization state/diff, model
identity, browser consistency checks, JavaScript errors, and a frontend PNG. Its
internal Playwright browser is not exposed to Cline.

## Setup

Start LM Studio's local server and load exactly `google/gemma-4-e4b`. Configure
Cline's `lmstudio` provider to use that exact model. Then run:

```bash
scripts/setup-evaluation
```

The setup installs the Python dependencies and Playwright Chromium in the existing
`.local/venv` (creating it when necessary).

## Run

```bash
scripts/evaluate \
  --target "visual-encoding Skillと関連するMCP説明を評価する" \
  --dataset sample_data/davis_southern_women.graphml
```

For a repository-wide evaluation, the dataset can be omitted:

```bash
scripts/evaluate \
  --target "GraphVisAgentのシステムプロンプトとSkillsの有効性を評価する"
```

The default probe ceiling is 10. `--max-probes` changes only the ceiling; it does
not prescribe prompts, order, or conversation length. Use `--existing-stack` to
target already-running local services on ports 8000, 8001, and 5173 instead of the
isolated Docker stack.

Reports, transcripts, screenshots, the evaluator instruction, Cline log, and model
preflight are written under `.evaluation/runs/<run-id>/`. This directory is ignored
by Git. The isolated Docker database is destroyed at the end unless `--keep-stack`
is explicitly supplied.

## Report boundary

Each probe is recorded as a finding, including successful and inconclusive probes.
Prompt recommendations and implementation defects are separate. The bridge writes
only evaluation artifacts; it never applies recommendations to application source.
Approved findings can subsequently be handed to Codex or Claude Code.
