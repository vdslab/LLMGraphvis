"""Repeatable real-LLM scenarios, judged by drawings rather than tool sequences."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .bridge import EvaluationBridge
from .capture import capture_graph
from .config import EvaluationConfig
from .surfaces import load_prompt_surfaces


@dataclass(frozen=True)
class Scenario:
    name: str
    dataset: str
    prompts: tuple[str, ...]
    expected: str


KARATE = "sample_data/karate_club.graphml"
SCENARIOS = (
    Scenario(
        "degree",
        KARATE,
        ("つながっている相手が多い人ほどノードを大きくしてください。",),
        "全ノードと辺を保持し、次数が増えるほど面積が増える。",
    ),
    Scenario(
        "broker-club",
        KARATE,
        (
            "元データのclubで色分けし、橋渡し役ほど大きくしてください。"
            "橋渡し役には重みなしの媒介中心性を使ってください。",
        ),
        "clubの各所属に一色を割り当て、媒介中心性をサイズに使う。"
        "このデータで媒介中心性最大のノード0が最大になる。",
    ),
    Scenario(
        "communities",
        KARATE,
        ("Louvain法でコミュニティを検出して、その結果で色分けしてください。",),
        "全ノードと辺を保持し、計算したLouvain属性で複数色に分ける。",
    ),
    Scenario(
        "bipartite",
        "sample_data/davis_southern_women.graphml",
        (
            "女性を左、イベントを右にして、二部グラフを左右2列に配置してください。"
            "bipartite属性の0が女性、1がイベントです。",
        ),
        "全ノードと辺を保持し、女性とイベントが左右それぞれ一列に並ぶ。",
    ),
    Scenario(
        "focus",
        KARATE,
        (
            "ノードID 0だけを強調し、それ以外を薄くしてください。"
            "分析対象は全体のままにしてください。",
        ),
        "分析対象と全ノード・辺と画角を保持し、0だけを強調して他を薄くする。",
    ),
    Scenario(
        "extract",
        KARATE,
        (
            "clubがMr. Hiのノードだけを部分ネットワークとして抽出し、"
            "分析対象をその部分ネットワークに切り替えて表示してください。",
        ),
        "Mr. Hiに属するノードとその間の辺だけを描き、分析対象を切り替える。",
    ),
    Scenario(
        "reset-color",
        KARATE,
        (
            "clubで色分けし、次数が大きいほどノードを大きくしてください。",
            "色だけを初期状態の単色に戻してください。サイズの対応付けは保持してください。",
        ),
        "最初の発話でclubと次数を対応付け、次の発話で色だけを解除する。",
    ),
    Scenario(
        "reset-highlight",
        KARATE,
        (
            "ノードID 0だけを強調し、残りは薄くしてください。",
            "強調を解除し、全ノードと辺の薄表示を元に戻してください。",
        ),
        "強調が実際に設定された後、全体のノード数を保って強調と薄表示を解除する。",
    ),
)


def fixture(path: Path) -> dict[str, Any]:
    """Read imported values and adjacency directly, independently of API state."""
    ns = {"g": "http://graphml.graphdrawing.org/xmlns"}
    root = ET.parse(path).getroot()
    keys = {
        key.attrib["id"]: key.attrib["attr.name"] for key in root.findall("g:key", ns)
    }
    nodes = {
        node.attrib["id"]: {
            keys[d.attrib["key"]]: d.text for d in node.findall("g:data", ns)
        }
        for node in root.findall("g:graph/g:node", ns)
    }
    edges = [
        (edge.attrib["source"], edge.attrib["target"])
        for edge in root.findall("g:graph/g:edge", ns)
    ]
    degree = Counter(endpoint for edge in edges for endpoint in edge)
    return {"nodes": nodes, "edges": edges, "degree": degree}


def check_drawing(
    name: str,
    original: dict[str, Any],
    state: dict[str, Any],
    initial_network_id: int,
) -> dict[str, bool]:
    """Check observable outcomes; alternative valid tool paths are accepted."""
    render = state["render"]
    nodes = render.get("nodes", [])
    metadata = state.get("metadata", {})
    by_id = {str(node["id"]): node for node in nodes}
    expected_ids = set(original["nodes"])
    if name == "extract":
        expected_ids = {
            key
            for key, attrs in original["nodes"].items()
            if attrs.get("club") == "Mr. Hi"
        }
    expected_edges = {
        tuple(sorted((a, b)))
        for a, b in original["edges"]
        if a in expected_ids and b in expected_ids
    }
    actual_edges = {
        tuple(sorted((str(e["source"]), str(e["target"]))))
        for e in render.get("links", [])
    }
    checks = {
        "node_ids": set(by_id) == expected_ids,
        "edges": actual_edges == expected_edges,
        "scope": (state["network_id"] != initial_network_id)
        if name == "extract"
        else state["network_id"] == initial_network_id,
        "finite_positions": bool(nodes)
        and all(
            isinstance(n.get(axis), (int, float)) and math.isfinite(n[axis])
            for n in nodes
            for axis in ("x", "y")
        ),
    }
    sizes = {key: float(n.get("size", 0)) for key, n in by_id.items()}
    size_attribute = (metadata.get("last_node_size_config") or {}).get("attribute", "")
    if name in {"degree", "reset-color"}:
        checks["degree_size_attribute"] = "degree" in size_attribute
        checks["degree_size_order"] = len(set(sizes.values())) > 1 and all(
            sizes[a] < sizes[b]
            for a in by_id
            for b in by_id
            if original["degree"][a] < original["degree"][b]
        )
    if name in {"broker-club", "club-setup"}:
        groups: dict[str, set[str]] = defaultdict(set)
        for key, node in by_id.items():
            groups[original["nodes"][key]["club"]].add(node["color"])
        checks["club_colors"] = (
            len(groups) == 2
            and all(len(colors) == 1 for colors in groups.values())
            and len(set.union(*groups.values())) == 2
        )
        checks["club_attribute"] = (metadata.get("last_node_color_config") or {}).get(
            "attribute"
        ) == "club"
    if name == "broker-club":
        checks["broker_size_attribute"] = "betweenness" in size_attribute
        checks["broker_largest"] = (
            bool(sizes)
            and sizes.get("0", 0) == max(sizes.values())
            and len(set(sizes.values())) > 1
        )
    if name == "communities":
        color_config = metadata.get("last_node_color_config") or {}
        checks["computed_community"] = "louvain" in color_config.get("attribute", "")
        checks["community_colors"] = len({n["color"] for n in nodes}) > 1
    if name == "bipartite":
        columns = [
            {
                round(n["x"], 6)
                for key, n in by_id.items()
                if original["nodes"][key].get("bipartite") == value
            }
            for value in ("0", "1")
        ]
        checks["two_columns"] = all(len(xs) == 1 for xs in columns)
        checks["women_left"] = bool(columns[0] and columns[1]) and (
            max(columns[0]) < min(columns[1])
        )
    if name == "focus":
        checks["viewport_unchanged"] = not render.get("viewport")
        checks["highlighted_ids"] = {
            key for key, n in by_id.items() if n.get("highlighted")
        } == {"0"}
        checks["others_dimmed"] = all(
            n.get("opacity", 1) < 1 for key, n in by_id.items() if key != "0"
        )
    if name == "reset-color":
        checks["uniform_color"] = len({n["color"] for n in nodes}) == 1
        checks["color_config_cleared"] = not metadata.get("last_node_color_config")
    if name == "reset-highlight":
        checks["no_highlight"] = not any(n.get("highlighted") for n in nodes)
        checks["no_dimming"] = all(
            n.get("opacity", 1) == 1 for n in nodes + render.get("links", [])
        )
    return checks


def browser_checks(capture: dict[str, Any], state: dict[str, Any]) -> dict[str, bool]:
    actual = {n["id"]: n for n in capture.get("rendered_nodes", [])}
    nodes = state["render"].get("nodes", [])
    return {
        "captured": bool(capture.get("captured")),
        "dom_consistent": bool(capture.get("dom_consistent")),
        "no_console_errors": not capture.get("errors"),
        "valid_svg": not any(capture.get("svg_validation", {}).values()),
        "drawn_channels_match": bool(actual)
        and len(actual) == len(nodes)
        and all(
            str(n["id"]) in actual
            and (
                actual[str(n["id"])]["color"] == n["color"]
                and math.isclose(
                    actual[str(n["id"])]["radius"],
                    math.sqrt(n["size"] * 10 / math.pi),
                    rel_tol=1e-6,
                )
                and actual[str(n["id"])]["opacity"] == n.get("opacity", 1)
            )
            for n in nodes
        ),
    }


def save(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n")


def audit_tool_arguments(
    executions: list[dict[str, Any]], schemas: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    """Flag undeclared arguments without prescribing a tool or a tool sequence."""
    notes = []
    for execution in executions:
        name = execution["tool_name"]
        if name not in schemas:
            continue
        extra = sorted(
            set(execution.get("arguments") or {})
            - set(schemas[name].get("properties", {}))
        )
        if extra:
            notes.append({"tool": name, "undeclared_arguments": extra})
    return notes


async def run(
    config: EvaluationConfig, selected: list[Scenario], feedback: bool
) -> int:
    bridge = EvaluationBridge(config)
    manifest = {
        "model": config.model_id,
        "scenarios": [
            {
                **asdict(s),
                "dataset_sha256": hashlib.sha256(
                    (config.repo_root / s.dataset).read_bytes()
                ).hexdigest(),
            }
            for s in selected
        ],
    }
    save(config.run_dir / "expectations.json", manifest)
    results = []
    stopped = False
    run_error = ""
    try:
        surfaces = await load_prompt_surfaces(config)
        save(config.run_dir / "prompt-surfaces.json", surfaces)
        schemas = {tool["name"]: tool["input_schema"] for tool in surfaces["mcp_tools"]}
        for scenario in selected:
            print(f"Starting {scenario.name}", flush=True)
            entry: dict[str, Any] = {
                "name": scenario.name,
                "steps": [],
                "passed": False,
            }
            results.append(entry)
            started = await bridge.start(scenario.dataset)
            entry["model_preflight"] = started["lm_studio_preflight"]
            session = bridge.sessions[started["session_id"]]
            original = fixture(config.repo_root / scenario.dataset)
            initial = session.network_id
            save(
                config.run_dir / f"{scenario.name}-initial-state.json",
                session.current_state,
            )
            initial_capture = await capture_graph(
                config,
                session.chat_id,
                bridge.api.token or "",
                len(original["nodes"]),
                len(original["edges"]),
                config.run_dir / "screenshots" / f"{scenario.name}-initial.png",
            )
            entry["initial_browser"] = browser_checks(
                initial_capture, session.current_state
            )
            entry["initial_capture"] = initial_capture
            if not all(entry["initial_browser"].values()):
                stopped = True
                break
            for index, prompt in enumerate(scenario.prompts):
                before_state = session.current_state
                observation, _ = await bridge.send(session.session_id, prompt, True)
                state = session.current_state
                save(config.run_dir / f"{scenario.name}-{index + 1}-state.json", state)
                check_name = scenario.name
                if len(scenario.prompts) > 1 and index == 0:
                    check_name = (
                        "club-setup" if scenario.name == "reset-color" else "focus"
                    )
                checks = check_drawing(check_name, original, state, initial)
                if check_name == "club-setup":
                    checks.update(check_drawing("degree", original, state, initial))
                if scenario.name == "reset-color" and index == 1:
                    checks["sizes_preserved"] = {
                        n["id"]: n["size"] for n in before_state["render"]["nodes"]
                    } == {n["id"]: n["size"] for n in state["render"]["nodes"]}
                browser = browser_checks(observation["capture"], state)
                step = {
                    "probe_number": observation["probe_number"],
                    "prompt": prompt,
                    "checks": checks,
                    "browser": browser,
                    "tools": observation["tools_called"],
                    "response": observation["assistant_message"],
                    "provider": observation["provider"],
                    "model": observation["model"],
                    "argument_audit": audit_tool_arguments(
                        observation["tool_executions"], schemas
                    ),
                    "tool_failures": [
                        {
                            "tool": e["tool_name"],
                            "arguments": e.get("arguments"),
                            "error": e.get("error"),
                        }
                        for e in observation["tool_executions"]
                        if e.get("status") == "failed"
                    ],
                    "capture": observation["capture"],
                }
                entry["steps"].append(step)
                save(config.run_dir / "scenario-results.json", results)
                print(f"{scenario.name}: {checks}; browser={browser}", flush=True)
                if not all(browser.values()):
                    stopped = True
                    break
            if feedback and not stopped:
                entry["target_feedback"] = await bridge.ask_target_feedback(
                    session.session_id, session.observations[-1]["probe_number"]
                )
                print(f"{scenario.name}: feedback saved", flush=True)
            entry["passed"] = (
                bool(entry["steps"])
                and all(
                    all(step["checks"].values()) and all(step["browser"].values())
                    for step in entry["steps"]
                )
                and len(entry["steps"]) == len(scenario.prompts)
            )
            save(config.run_dir / "scenario-results.json", results)
            if stopped:
                break
    except Exception as exc:
        stopped = True
        run_error = f"{type(exc).__name__}: {exc}"
        save(config.run_dir / "run-error.json", {"error": run_error})
        print(run_error, flush=True)
    finally:
        await bridge.api.close()
        save(config.run_dir / "scenario-results.json", results)
    lines = [
        "# Real-LLM visualization scenarios",
        "",
        f"Model: `{config.model_id}`",
        "",
        "| Scenario | Verdict | Failed checks |",
        "|---|---|---|",
    ]
    for result in results:
        failed = [
            key
            for step in result["steps"]
            for group in ("checks", "browser")
            for key, passed in step[group].items()
            if not passed
        ]
        failed += [
            key
            for key, passed in result.get("initial_browser", {}).items()
            if not passed
        ]
        lines.append(
            f"| {result['name']} | {'PASS' if result['passed'] else 'FAIL'} | "
            f"{', '.join(failed)} |"
        )
    for result in results:
        lines.extend(["", f"## {result['name']}", ""])
        for step in result["steps"]:
            lines.extend(
                [
                    f"Prompt: {step['prompt']}",
                    "",
                    f"Tools: {', '.join(step['tools'])}",
                    f"Undeclared arguments: {step.get('argument_audit', [])}",
                    f"Failed tool calls: {step.get('tool_failures', [])}",
                    "",
                    step["response"],
                    "",
                    f"PNG: {step['capture'].get('path')}",
                    "",
                ]
            )
        if note := result.get("target_feedback"):
            lines.extend(
                [
                    "### Target feedback (unverified)",
                    "",
                    note["response"],
                    "",
                    f"Tools during feedback: {note['tools_called']}",
                    "Drawing changed during feedback: "
                    f"{note['visualization_diff']['changed']}",
                    "",
                ]
            )
    if stopped and not run_error:
        lines.extend(
            ["", "Stopped at the first browser failure. Remaining cases were not run."]
        )
    if run_error:
        lines.extend(["", f"Run error: {run_error}"])
    (config.run_dir / "scenario-report.md").write_text("\n".join(lines) + "\n")
    print(f"Report: {config.run_dir / 'scenario-report.md'}", flush=True)
    return int(
        stopped
        or len(results) != len(selected)
        or any(not result["passed"] for result in results)
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", action="append", choices=[s.name for s in SCENARIOS])
    parser.add_argument(
        "--run-id",
        default="scenarios-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
    )
    parser.add_argument("--no-feedback", action="store_true")
    args = parser.parse_args()
    selected = [s for s in SCENARIOS if not args.case or s.name in args.case]
    config = replace(
        EvaluationConfig.from_env(),
        run_id=args.run_id,
        max_probes=sum(len(s.prompts) for s in selected),
    )
    if config.run_dir.exists():
        parser.error(
            f"Run directory already exists: {config.run_dir}; use a new run ID"
        )
    return asyncio.run(run(config, selected, not args.no_feedback))


if __name__ == "__main__":
    raise SystemExit(main())
