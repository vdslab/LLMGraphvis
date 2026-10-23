"""A stalled MCP call fails with a named timeout instead of hanging.

An upload once waited forever on a session that had initialised and then never
sent its tool call; nothing logged an error and the spinner never stopped.
"""

import asyncio
from unittest.mock import patch

import pytest

from app.services.llm import mcp_client


class _StalledSession:
    async def call_tool(self, name, arguments):
        await asyncio.sleep(3600)


@pytest.mark.asyncio
async def test_a_call_that_never_returns_raises_tool_timeout():
    with patch.object(mcp_client, "CALL_TIMEOUT_SECONDS", 0.05):
        with pytest.raises(mcp_client.ToolTimeoutError) as excinfo:
            await mcp_client.execute_tool(
                "network_import_graphml", {"network_id": 1}, session=_StalledSession()
            )

    assert excinfo.value.tool_name == "network_import_graphml"
    assert "did not respond within 0.05 seconds" in str(excinfo.value)


@pytest.mark.asyncio
async def test_the_timeout_also_covers_opening_the_session():
    """The observed stall happened inside a transient session, after setup."""

    class _StalledScope:
        async def __aenter__(self):
            await asyncio.sleep(3600)

        async def __aexit__(self, *exc):
            return False

    with (
        patch.object(mcp_client, "CALL_TIMEOUT_SECONDS", 0.05),
        patch.object(mcp_client, "session_scope", lambda: _StalledScope()),
    ):
        with pytest.raises(mcp_client.ToolTimeoutError):
            await mcp_client.execute_tool("layout_forceatlas2", {"network_id": 1})
