"""CPU tools preserve their schemas and do not block concurrent MCP requests."""

import threading

import anyio

from app.core.mcp import GraphMCPServer


def test_sync_tool_runs_in_a_worker_thread_and_keeps_its_schema():
    server = GraphMCPServer("test")
    seen = {}

    @server.tool()
    def busy(n: int) -> int:
        """Double n."""
        seen["thread"] = threading.current_thread()
        return n * 2

    async def check():
        tools = await server.list_tools()
        assert tools[0].input_schema["properties"]["n"]["type"] == "integer"
        result = await server.call_tool("busy", {"n": 21})
        assert not result.is_error
        assert "42" in result.content[0].text

    anyio.run(check)
    assert seen["thread"] is not threading.main_thread()
    assert busy(2) == 4  # Internal callers retain the synchronous entry point.


def test_slow_tool_keeps_the_event_loop_available():
    server = GraphMCPServer("test")
    entered, release = threading.Event(), threading.Event()

    @server.tool()
    def slow() -> str:
        entered.set()
        assert release.wait(5)
        return "done"

    async def check():
        async with anyio.create_task_group() as group:
            group.start_soon(server.call_tool, "slow", {})
            with anyio.fail_after(3):
                while not entered.is_set():
                    await anyio.sleep(0.01)
                assert await server.list_tools()
            release.set()

    anyio.run(check)
