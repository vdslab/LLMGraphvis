"""Skills against the real tool registry (ADR 0027).

Tools are exposed only through `skill_load` (a skill's `related_tools`) or
`tool_search`. So a skill naming a tool that does not exist, or a parameter the
tool does not take, sends the model into an error; a tool no skill exposes is
found only if the model thinks to search; and a tool a skill tells the model to
call, but does not expose, is refused by `guard_tool_is_exposed`.

The MCP side is read from `common/mcp_tools.json`, which networkx-api generates
and keeps current (its `tests/test_tool_manifest.py`).
"""

import json
import re
from pathlib import Path

import pytest

from app.services.llm.local_tools import get_local_tools
from app.services.llm.skills.loader import load_skills
from app.services.llm.tool_catalog import DEPRECATED_TOOL_NAMES


def _manifest_path() -> Path:
    here = Path(__file__).resolve()
    for root in (here.parents[1], here.parents[2]):
        candidate = root / "common" / "mcp_tools.json"
        if candidate.exists():
            return candidate
    pytest.skip("common/mcp_tools.json not found")


MCP_TOOLS = json.loads(_manifest_path().read_text(encoding="utf-8"))
LOCAL_TOOLS = {tool.name: sorted(tool.parameters.get("properties", {})) for tool in get_local_tools()}
# Added by mcp_client next to the discovered tools.
PROTOCOL_TOOLS = {"read_resource": ["uri"], "list_resources": []}
ALL_TOOLS = {**MCP_TOOLS, **LOCAL_TOOLS, **PROTOCOL_TOOLS}

# Reachable only through tool_search, on purpose. Each needs a reason.
SEARCH_ONLY = {
    "network_import_graphml": "the upload pipeline imports; the agent never does",
    "network_list_all": "the chat is bound to one network tree",
    "network_get_info": "the same facts are in [Current Network Context]",
    "network_update_metadata": "rare editing request",
    "node_update_label": "rare editing request",
    "subgraph_create_by_filter": "legacy compound; subgraph_extract_filter replaces it",
    "list_resources": "context is injected; resources are read by the backend",
    "read_resource": "context is injected; resources are read by the backend",
}

_TOOL_PREFIXES = ("network_", "node_", "subgraph_", "analysis_", "layout_", "visualization_")
_BACKTICKED = re.compile(r"`([a-z][a-z0-9_]*)")
_CALL_ARGS = re.compile(r"`([a-z][a-z0-9_]*)\(([^`)]*)")
_DOTTED = re.compile(r"`([a-z][a-z0-9_]*)\.([a-z][a-z0-9_]*)`")

SKILLS = load_skills()
SKILL_NAMES = {s.name for s in SKILLS}


# Tool-prefixed words that are parameters or result fields, not tools.
PARAMETER_NAMES = {p for params in ALL_TOOLS.values() for p in params}
RESULT_FIELDS = {"layout_quality", "node_overlap"}


def _tool_mentions(body: str) -> set:
    return {
        word
        for word in _BACKTICKED.findall(body)
        if word.startswith(_TOOL_PREFIXES)
        and not word.endswith("_")
        and word not in PARAMETER_NAMES
        and word not in RESULT_FIELDS
    }


@pytest.mark.parametrize("skill", SKILLS, ids=lambda s: s.name)
def test_related_tools_exist(skill):
    unknown = [t for t in skill.related_tools if t not in ALL_TOOLS]
    assert not unknown, f"{skill.name} exposes unknown tools {unknown}"


@pytest.mark.parametrize("skill", SKILLS, ids=lambda s: s.name)
def test_named_tools_exist(skill):
    unknown = sorted(_tool_mentions(skill.body) - set(ALL_TOOLS))
    assert not unknown, f"{skill.name} names unknown tools {unknown}"


@pytest.mark.parametrize("skill", SKILLS, ids=lambda s: s.name)
def test_named_tools_are_exposed_by_this_skill_or_one_it_points_to(skill):
    """Telling the model to call a tool it cannot see wastes a refused round."""
    pointed = {name for name in _BACKTICKED.findall(skill.body) if name in SKILL_NAMES}
    pointed |= {
        name for name in re.findall(r"`([a-z]+(?:-[a-z0-9]+)+)`", skill.body)
        if name in SKILL_NAMES
    }
    reachable = set(skill.related_tools)
    for other in SKILLS:
        if other.name in pointed:
            reachable |= set(other.related_tools)
    missing = sorted(
        _tool_mentions(skill.body) & set(ALL_TOOLS) - reachable - DEPRECATED_TOOL_NAMES
    )
    assert not missing, (
        f"{skill.name} tells the model to use {missing} but neither it nor a skill "
        "it points to exposes them; add them to related_tools"
    )


@pytest.mark.parametrize("skill", SKILLS, ids=lambda s: s.name)
def test_named_parameters_exist(skill):
    """`tool(param=...)` and `tool.param` must name a parameter the tool takes."""
    for tool, args in _CALL_ARGS.findall(skill.body):
        if tool not in ALL_TOOLS:
            continue
        for param in re.findall(r"([a-z_][a-z0-9_]*)\s*=", args):
            assert param in ALL_TOOLS[tool], f"{skill.name}: `{tool}` has no `{param}`"
    for tool, param in _DOTTED.findall(skill.body):
        if tool in ALL_TOOLS:
            assert param in ALL_TOOLS[tool], f"{skill.name}: `{tool}` has no `{param}`"


def test_every_tool_is_reachable_from_a_skill():
    exposed = {t for s in SKILLS for t in s.related_tools}
    always = {"skill_load", "tool_search", "ask_user"}
    unreachable = sorted(
        set(ALL_TOOLS) - exposed - always - DEPRECATED_TOOL_NAMES - set(SEARCH_ONLY)
    )
    assert not unreachable, (
        f"No skill exposes {unreachable}. Add each to the related_tools of the skill "
        "whose procedure uses it, or to SEARCH_ONLY with a reason."
    )


def test_search_only_entries_are_real_and_not_exposed():
    exposed = {t for s in SKILLS for t in s.related_tools}
    assert set(SEARCH_ONLY) <= set(ALL_TOOLS)
    assert not set(SEARCH_ONLY) & exposed
