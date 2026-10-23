import functools

import anyio
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP Server
mcp = FastMCP("NetworkX Agent", host="0.0.0.0")

# Tools are plain `def`s doing CPU-bound graph work, and FastMCP calls a sync
# tool directly on the event loop: one 60-second layout froze every other
# request, health checks and SSE keep-alives included (chat 277). A few
# threads keep the server answering without letting parallel chats run an
# unbounded number of layouts at once.
TOOL_THREADS = anyio.CapacityLimiter(4)


def offload_sync_tools(server: FastMCP) -> int:
    """Run every registered sync tool in a worker thread. Returns the count.

    The module-level functions stay synchronous, so tests and internal callers
    are unaffected; only the registered MCP entry point becomes async.
    """
    count = 0
    for tool in server._tool_manager.list_tools():
        if tool.is_async:
            continue
        fn = tool.fn

        @functools.wraps(fn)
        async def run_in_thread(*args, _fn=fn, **kwargs):
            return await anyio.to_thread.run_sync(
                functools.partial(_fn, *args, **kwargs), limiter=TOOL_THREADS
            )

        tool.fn = run_in_thread
        tool.is_async = True
        count += 1
    return count
