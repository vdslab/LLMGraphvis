from __future__ import annotations

import json
import os
from typing import Any

from mcp.server.fastmcp import FastMCP, Image

from .bridge import EvaluationBridge
from .config import EvaluationConfig
from .reports import save_report
from .surfaces import compact_inventory, find_surface, load_prompt_surfaces

config = EvaluationConfig.from_env()
bridge = EvaluationBridge(config)
mcp = FastMCP("GraphVisAgent Prompt Evaluator")


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, default=str)


def _with_image(payload: dict[str, Any], image_path: Any | None) -> list[Any]:
    content: list[Any] = [_json(payload)]
    if image_path:
        content.append(Image(path=image_path))
    return content


@mcp.tool()
async def list_prompt_surfaces() -> str:
    """List the current GraphVisAgent system prompt, Skills, and live MCP tools.

    Use this to decide which prompt surfaces are relevant to the evaluation target.
    It intentionally returns a compact inventory; call read_prompt_surface only for
    items you actually need to inspect.
    """
    surfaces = await load_prompt_surfaces(config)
    return _json(compact_inventory(surfaces))


@mcp.tool()
async def read_prompt_surface(kind: str, name: str) -> str:
    """Read one current prompt surface in full.

    kind is one of system_prompt, skill, or mcp_tool. name must come from
    list_prompt_surfaces. The result is current runtime information, not a Git diff.
    """
    surfaces = await load_prompt_surfaces(config)
    surface = find_surface(surfaces, kind, name)
    if surface is None:
        available = compact_inventory(surfaces)
        return _json(
            {
                "error": f"No {kind!r} prompt surface named {name!r}.",
                "available": available,
            }
        )
    return _json(surface)


@mcp.tool()
async def start_test(dataset: str) -> str:
    """Create an isolated evaluation user, chat, and uploaded GraphML network.

    dataset must be a GraphML/XML file inside the GraphVisAgent repository. The chat
    is pinned to LM Studio and google/gemma-4-e4b. This does not define a scenario;
    the evaluator must invent its own user prompts after inspecting prompt surfaces.
    """
    return _json(await bridge.start(dataset))


@mcp.tool()
async def send_message(
    session_id: str,
    message: str,
    capture: bool = True,
) -> list[Any]:
    """Send one freely chosen user message to GraphVisAgent and observe the result.

    Returns the assistant response, loaded Skills, MCP tool calls and arguments,
    visualization state changes, model identity, and optionally a real frontend PNG.
    Before calling, record your hypothesis, expected behavior, and failure condition.
    """
    observation, image_path = await bridge.send(session_id, message, capture)
    return _with_image(observation, image_path)


@mcp.tool()
async def observe_session(session_id: str) -> list[Any]:
    """Read the current multi-turn transcript and visualization, including a PNG."""
    observation, image_path = await bridge.observe(session_id)
    return _with_image(observation, image_path)


@mcp.tool()
async def reset_test(session_id: str) -> str:
    """Replace a test chat with a fresh upload of the same dataset.

    Use this when the next freely designed probe requires the original graph state.
    """
    return _json(await bridge.reset(session_id))


@mcp.tool()
async def finish_evaluation(
    summary: str,
    findings: list[dict[str, Any]],
    implementation_issues: list[str] | None = None,
) -> str:
    """Validate and save the final prompt-evaluation report.

    Findings must separate prompt-surface recommendations from implementation defects.
    This tool writes only evaluation artifacts and never edits GraphVisAgent sources.
    """
    target = os.getenv("GRAPHVIS_EVAL_TARGET", "GraphVisAgent prompt surfaces")
    graphvis_model = config.model_id
    trials = []
    for session in bridge.sessions.values():
        for observation in session.observations:
            trials.append({"session_id": session.session_id, **observation})
        for observation in reversed(session.observations):
            if observation.get("model"):
                graphvis_model = observation["model"]
                break
    recorded_probes = {int(trial["probe_number"]) for trial in trials}
    finding_probes = {
        int(finding["probe_number"])
        for finding in findings
        if "probe_number" in finding
    }
    missing = sorted(recorded_probes - finding_probes)
    if missing:
        raise ValueError(
            "Every probe must be represented by at least one finding. "
            f"Missing probe numbers: {missing}"
        )
    report, json_path, markdown_path = save_report(
        config.run_dir,
        config.run_id,
        {
            "target": target,
            "evaluator_model": config.model_id,
            "graphvis_model": graphvis_model,
            "summary": summary,
            "trials": trials,
            "findings": findings,
            "implementation_issues": implementation_issues or [],
        },
    )
    return _json(
        {
            "status": "saved",
            "finding_count": len(report.findings),
            "json_report": str(json_path),
            "markdown_report": str(markdown_path),
        }
    )


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
