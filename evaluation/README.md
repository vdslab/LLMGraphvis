# Real-LLM evaluation

## Repeatable visualization scenarios

Run the application in the disposable Docker stack, then run the scenario driver:

```bash
docker compose -f docker-compose.evaluation.yml -p graphvis-scenarios up -d --build --wait
.local/venv/bin/python -m evaluation.scenarios
docker compose -f docker-compose.evaluation.yml -p graphvis-scenarios down -v
```

Use `scripts/setup-evaluation` once if the Python environment or Playwright browser
is missing. LM Studio must serve `google/gemma-4-e4b`; load it with enough context
for the activated tool schemas and multi-turn history. The verified configuration
uses a context length of 32768 and one parallel prediction. An 8192-token context
failed after the first Skill activated more tools.

`--case degree` selects a case (repeat the flag for several), and `--run-id NAME`
names the artifact directory. The driver saves expectations and dataset hashes
before sending any messages. It checks the uploaded drawing and each requested
change against imported node/edge identities, channel configuration and actual
SVG colors, radii and opacity. It stops on the first browser failure and retains
the console evidence and PNG. A nonzero exit means a failed or incomplete run.
Results and raw states are under `.evaluation/runs/<run-id>/`.

After each scenario, the driver asks **the target chat assistant itself** about
unclear tool names, descriptions, arguments and return values. This is a separate
evaluation turn, saved as `target_feedback` in the session and scenario report.
It is an unverified suggestion, never a pass/fail oracle. Unexpected calls or
drawing changes during this turn are recorded. The next scenario uses a fresh
chat to avoid priming it with the feedback question. `--no-feedback` skips this
additional model call.

The same operation is available as `ask_target_feedback` in the evaluation MCP.
It refers only to the latest observed probe; reset that session before another
probe. Evaluation notes by the evaluator remain in `record_analysis_friction`.

## Cline exploratory prompt evaluation

The exploratory workflow bridges Cline and a real GraphVisAgent session. It is
for evaluating the current system prompt, Skills, and MCP descriptions—not for
reviewing a Git diff. No scenario files or fixed expected-tool lists are used.

## What runs

`scripts/evaluate` starts an isolated GraphVisAgent stack with an ephemeral
PostgreSQL database. It temporarily selects Cline's LM Studio provider and installs
one stdio MCP server containing only these evaluation operations:

- discover/read the current prompt surfaces;
- start, message, observe, or reset a GraphVisAgent test conversation;
- record what confused the evaluator AI during an observed analysis probe;
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

The evaluator calls `record_analysis_friction` when an analysis step or result is
hard to understand. The tool requires an observed session and probe, the exact
point of confusion, and evidence. It saves a note immediately under
`.evaluation/runs/<run-id>/friction.json` and includes it in the final report.
It does not display anything to GraphVisAgent users or alter their conversation.

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
