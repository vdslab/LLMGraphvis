"""Tests for progressive tool-definition exposure and local discovery."""

import pytest

from app.services.llm import local_tools
from app.services.llm.providers.types import ToolDefinition
from app.services.llm.tool_catalog import ToolCatalog


def tool(name: str, description: str = "") -> ToolDefinition:
    return ToolDefinition(name=name, description=description, parameters={})


def test_progressive_turn_starts_with_only_discovery_tools(monkeypatch):
    monkeypatch.delenv("TOOL_EXPOSURE_MODE", raising=False)
    catalog = ToolCatalog(
        [
            tool("analysis_pagerank"),
            tool("skill_load"),
            tool("tool_search"),
            tool("ask_user"),
        ]
    )
    state = {}
    catalog.initialize_turn(state)

    assert [item.name for item in catalog.active_tools(state)] == [
        "skill_load",
        "tool_search",
        "ask_user",
    ]


def test_all_mode_preserves_legacy_exposure(monkeypatch):
    monkeypatch.setenv("TOOL_EXPOSURE_MODE", "all")
    catalog = ToolCatalog([tool("analysis_pagerank"), tool("skill_load")])
    state = {}
    catalog.initialize_turn(state)
    assert [item.name for item in catalog.active_tools(state)] == [
        "analysis_pagerank",
        "skill_load",
    ]


def test_activation_is_additive_deduplicated_and_catalog_ordered(monkeypatch):
    monkeypatch.delenv("TOOL_EXPOSURE_MODE", raising=False)
    catalog = ToolCatalog(
        [
            tool("analysis_pagerank"),
            tool("skill_load"),
            tool("tool_search"),
            tool("ask_user"),
        ]
    )
    state = {}
    catalog.initialize_turn(state)
    activated, missing = catalog.activate(
        ["analysis_pagerank", "analysis_pagerank", "missing"], state
    )
    assert activated == ["analysis_pagerank"]
    assert missing == ["missing"]
    assert [item.name for item in catalog.active_tools(state)] == [
        "analysis_pagerank",
        "skill_load",
        "tool_search",
        "ask_user",
    ]


def test_separate_turn_states_do_not_share_activation(monkeypatch):
    monkeypatch.delenv("TOOL_EXPOSURE_MODE", raising=False)
    catalog = ToolCatalog([tool("analysis_pagerank"), tool("skill_load")])
    first, second = {}, {}
    catalog.initialize_turn(first)
    catalog.initialize_turn(second)
    catalog.activate(["analysis_pagerank"], first)
    assert "analysis_pagerank" in first["enabled_tool_names"]
    assert "analysis_pagerank" not in second["enabled_tool_names"]


def test_search_ranks_name_before_description_and_hides_deprecated():
    catalog = ToolCatalog(
        [
            tool("analysis_pagerank", "Calculate importance"),
            tool("node_find", "Find a pagerank value"),
            tool("network_initialize", "Import and render a graph"),
        ]
    )
    assert [item.name for item in catalog.search("pagerank")] == [
        "analysis_pagerank",
        "node_find",
    ]
    assert catalog.search("initialize") == []
    assert [item.name for item in catalog.search("network_initialize")] == [
        "network_initialize"
    ]


def test_multi_word_query_naming_a_real_tool_still_finds_it():
    """A tool name plus extra words must not return nothing.

    "visualization_set_node_size scaling factor" matches the name partially and
    the description partially, but no single field wholly. Returning [] there
    sent the model into a retry loop against a tool that exists.
    """
    catalog = ToolCatalog(
        [
            tool("visualization_set_node_size", "Updates ONLY the node sizes."),
            tool("analysis_pagerank", "Calculate importance"),
        ]
    )
    assert [
        item.name
        for item in catalog.search("visualization_set_node_size scaling factor")
    ][0] == "visualization_set_node_size"


def test_single_term_search_stays_strict():
    catalog = ToolCatalog([tool("analysis_pagerank", "Calculate importance")])
    assert catalog.search("layout") == []


def test_search_uses_japanese_skill_metadata():
    catalog = ToolCatalog([tool("visualization_set_node_color")])
    assert [item.name for item in catalog.search("色分け")] == [
        "visualization_set_node_color"
    ]


@pytest.mark.asyncio
async def test_tool_search_paginates_and_activates_results(monkeypatch):
    monkeypatch.delenv("TOOL_EXPOSURE_MODE", raising=False)
    catalog = ToolCatalog(
        [
            tool("analysis_alpha", "metric"),
            tool("analysis_beta", "metric"),
            tool("skill_load"),
            tool("tool_search"),
            tool("ask_user"),
        ]
    )
    state = {}
    catalog.initialize_turn(state)
    result = await local_tools.tool_search("analysis_", 1, 1, state)
    assert result["total"] == 2
    assert result["has_more"] is False
    assert result["activated_tools"] == ["analysis_beta"]
    assert "parameters" not in result["results"][0]


@pytest.mark.asyncio
async def test_skill_load_activates_related_tools(monkeypatch):
    from app.services.llm.skills import registry

    monkeypatch.delenv("TOOL_EXPOSURE_MODE", raising=False)
    skill = registry.get("visual-encoding")
    catalog = ToolCatalog(
        [tool(name) for name in skill.related_tools]
        + [tool("skill_load"), tool("tool_search"), tool("ask_user")]
    )
    state = {}
    catalog.initialize_turn(state)
    result = await local_tools.skill_load("visual-encoding", state)
    assert result["missing_tools"] == []
    assert set(result["activated_tools"]) == set(skill.related_tools)
    assert set(skill.related_tools) <= state["enabled_tool_names"]


@pytest.mark.asyncio
async def test_empty_search_is_rejected():
    result = await local_tools.tool_search("  ", 5, 0, {})
    assert result == {"error": "query must not be empty"}
