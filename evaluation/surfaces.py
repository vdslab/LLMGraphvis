from __future__ import annotations

import ast
import sys
from pathlib import Path
from typing import Any

from mcp import ClientSession
from mcp.client.sse import sse_client

from .config import EvaluationConfig


def _ensure_backend_imports(config: EvaluationConfig) -> None:
    for path in (config.repo_root, config.repo_root / "backend"):
        value = str(path)
        if value not in sys.path:
            sys.path.insert(0, value)


def _backend_surfaces(
    config: EvaluationConfig,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    _ensure_backend_imports(config)
    from app.services.llm import local_tools, prompts
    from app.services.llm.skills import registry as skill_registry

    system_text = prompts.build_system_instruction(supports_native_thinking=False)
    system = {
        "kind": "system_prompt",
        "name": "graphvis-agent",
        "description": "Active LM Studio/textual-thinking system instruction.",
        "path": str(config.repo_root / "backend/app/services/llm/prompts.py"),
        "characters": len(system_text),
        "content": system_text,
        "per_turn_skill_index": skill_registry.index_block(),
        "assembly_note": (
            "The runtime appends the current-network context, matching Skill "
            "suggestions, and iteration budget on each user turn."
        ),
    }

    skills = []
    for skill in skill_registry.all():
        skills.append(
            {
                "kind": "skill",
                "name": skill.name,
                "description": skill.description,
                "triggers": skill.triggers,
                "related_tools": skill.related_tools,
                "path": str(skill.source_path) if skill.source_path else None,
                "content": skill.body,
            }
        )

    local = []
    for tool in local_tools.get_local_tools():
        local.append(
            {
                "kind": "mcp_tool",
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.parameters,
                "source": "backend-local",
                "path": str(
                    config.repo_root / "backend/app/services/llm/local_tools.py"
                ),
            }
        )
    return system, skills, local


async def _networkx_tools(config: EvaluationConfig) -> list[dict[str, Any]]:
    source_locations = _tool_source_locations(
        config.repo_root / "networkx-api" / "app" / "mcp" / "tools"
    )
    async with sse_client(config.networkx_mcp_url) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.list_tools()
            return [
                {
                    "kind": "mcp_tool",
                    "name": tool.name,
                    "description": tool.description or "",
                    "input_schema": tool.inputSchema,
                    "source": "networkx-mcp",
                    **source_locations.get(tool.name, {}),
                }
                for tool in result.tools
            ]


def _tool_source_locations(root: Path) -> dict[str, dict[str, Any]]:
    locations: dict[str, dict[str, Any]] = {}
    for path in root.rglob("*.py"):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if node.name.startswith("_"):
                continue
            decorated = any(
                isinstance(decorator, ast.Call)
                and isinstance(decorator.func, ast.Attribute)
                and decorator.func.attr == "tool"
                for decorator in node.decorator_list
            )
            if decorated:
                locations[node.name] = {
                    "path": str(path),
                    "line": node.lineno,
                }
    return locations


async def load_prompt_surfaces(config: EvaluationConfig) -> dict[str, Any]:
    system, skills, local_tools = _backend_surfaces(config)
    warnings: list[str] = []
    try:
        networkx_tools = await _networkx_tools(config)
    except Exception as exc:
        networkx_tools = []
        warnings.append(
            f"Could not list live NetworkX MCP tools: {type(exc).__name__}: {exc}"
        )

    return {
        "system_prompts": [system],
        "skills": skills,
        "mcp_tools": sorted(
            local_tools + networkx_tools, key=lambda item: item["name"]
        ),
        "warnings": warnings,
    }


def compact_inventory(surfaces: dict[str, Any]) -> dict[str, Any]:
    def short(value: Any, limit: int = 240) -> str:
        text = " ".join(str(value or "").split())
        return text if len(text) <= limit else text[: limit - 1] + "…"

    return {
        "system_prompts": [
            {
                key: item.get(key)
                for key in ("kind", "name", "description", "path", "characters")
            }
            for item in surfaces.get("system_prompts", [])
        ],
        "skills": [
            {
                key: item.get(key)
                for key in (
                    "kind",
                    "name",
                    "description",
                    "triggers",
                    "related_tools",
                    "path",
                )
            }
            for item in surfaces.get("skills", [])
        ],
        "mcp_tools": [
            {
                "kind": item.get("kind"),
                "name": item.get("name"),
                "description": short(item.get("description")),
                "source": item.get("source"),
                "path": item.get("path"),
                "line": item.get("line"),
            }
            for item in surfaces.get("mcp_tools", [])
        ],
        "warnings": surfaces.get("warnings", []),
    }


def find_surface(
    surfaces: dict[str, Any], kind: str, name: str
) -> dict[str, Any] | None:
    aliases = {
        "system": "system_prompts",
        "system_prompt": "system_prompts",
        "skill": "skills",
        "mcp": "mcp_tools",
        "mcp_tool": "mcp_tools",
        "tool": "mcp_tools",
    }
    collection = aliases.get(kind.strip().lower())
    if not collection:
        return None
    normalized = name.strip().lower().replace("_", "-")
    for item in surfaces.get(collection, []):
        candidate = str(item.get("name", "")).lower().replace("_", "-")
        if candidate == normalized:
            return item
    return None
