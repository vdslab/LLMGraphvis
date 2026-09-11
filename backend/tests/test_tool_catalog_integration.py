"""Integration checks against the live NetworkX MCP discovery endpoint."""

import pytest

from app.services.llm import local_tools, mcp_client
from app.services.llm.skills import registry


@pytest.mark.asyncio
async def test_shipped_skill_tool_names_resolve_against_live_catalog():
    try:
        tools = await mcp_client.get_tools()
    except Exception as exc:
        pytest.skip(f"live MCP server is unavailable: {exc}")

    discovered = {tool.name for tool in [*tools, *local_tools.get_local_tools()]}
    unresolved = {
        skill.name: sorted(set(skill.related_tools) - discovered)
        for skill in registry.all()
        if set(skill.related_tools) - discovered
    }
    assert unresolved == {}
