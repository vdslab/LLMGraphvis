"""A dropped MCP connection is re-opened, not left dead for the turn.

In chat 277 networkx-api restarted mid-call; every later call in that turn
failed in a millisecond with an empty error message.
"""

from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import patch

import anyio
import pytest
from mcp.shared.exceptions import MCPError
from mcp.types import CONNECTION_CLOSED

from app.services.llm import mcp_client


def _ok(text='{"done": true}'):
    return SimpleNamespace(
        is_error=False, content=[SimpleNamespace(type="text", text=text)]
    )


class _Session:
    def __init__(self, failure=None):
        self.failure = failure
        self.calls = 0

    async def call_tool(self, name, arguments):
        self.calls += 1
        if self.failure:
            raise self.failure
        return _ok()


def _scopes(*sessions):
    opened = []
    queue = list(sessions)

    @asynccontextmanager
    async def scope():
        session = queue.pop(0)
        opened.append(session)
        yield session

    return scope, opened


@pytest.mark.asyncio
async def test_a_call_on_a_closed_stream_reconnects_and_retries_once():
    dead = _Session(anyio.ClosedResourceError())
    fresh = _Session()
    scope, opened = _scopes(dead, fresh)
    with patch.object(mcp_client, "session_scope", scope):
        async with mcp_client.ResilientSession() as session:
            result = await mcp_client.execute_tool(
                "layout_profile", {}, session=session
            )
    assert result == {"done": True}
    assert opened == [dead, fresh]
    assert fresh.calls == 1


@pytest.mark.asyncio
async def test_a_call_cut_off_mid_run_is_reported_not_rerun_and_the_next_call_works():
    cut = _Session(MCPError(CONNECTION_CLOSED, "Connection closed"))
    fresh = _Session()
    scope, _ = _scopes(cut, fresh)
    with patch.object(mcp_client, "session_scope", scope):
        async with mcp_client.ResilientSession() as session:
            with pytest.raises(mcp_client.ToolConnectionLost, match="safe"):
                await mcp_client.execute_tool(
                    "layout_suggest_parameters", {}, session=session
                )
            assert fresh.calls == 0
            assert await mcp_client.execute_tool("layout_profile", {}, session=session)
    assert fresh.calls == 1


@pytest.mark.asyncio
async def test_other_errors_pass_through_without_reconnecting():
    broken = _Session(ValueError("bad argument"))
    scope, opened = _scopes(broken)
    with patch.object(mcp_client, "session_scope", scope):
        async with mcp_client.ResilientSession() as session:
            with pytest.raises(ValueError):
                await mcp_client.execute_tool("layout_profile", {}, session=session)
    assert opened == [broken]
