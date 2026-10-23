"""Sync tools run off the event loop (chat 277: one layout froze the server)."""

import threading

import anyio
from mcp.server.fastmcp import FastMCP

from app.core.mcp import offload_sync_tools


def test_sync_tool_runs_in_a_worker_thread_and_keeps_its_schema():
    server = FastMCP("test")
    seen = {}

    @server.tool()
    def busy(n: int) -> int:
        """Doubles n."""
        seen["thread"] = threading.current_thread()
        return n * 2

    schema_before = server._tool_manager.get_tool("busy").parameters
    assert offload_sync_tools(server) == 1
    tool = server._tool_manager.get_tool("busy")
    assert tool.is_async
    assert tool.parameters == schema_before

    async def main():
        result = await server.call_tool("busy", {"n": 21})
        return result

    anyio.run(main)
    assert seen["thread"] is not threading.main_thread()


def test_every_registered_tool_is_offloaded():
    from app.mcp_server import mcp

    assert all(tool.is_async for tool in mcp._tool_manager.list_tools())
