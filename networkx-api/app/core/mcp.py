"""MCP registration with bounded CPU work and synchronous internal entry points."""

import functools
import inspect

import anyio
from mcp.server import MCPServer

TOOL_THREADS = anyio.CapacityLimiter(4)


class GraphMCPServer(MCPServer):
    """Register sync tools through the public API with a shared worker limit.

    Keep the decorated Python function synchronous for internal callers. Only
    the MCP entry point is async; long layouts cannot block the server or start
    an unbounded number of simultaneous graph calculations.
    """

    def tool(self, *args, **kwargs):
        register = super().tool(*args, **kwargs)

        def decorate(fn):
            if inspect.iscoroutinefunction(fn):
                return register(fn)

            @functools.wraps(fn)
            async def run_in_thread(*call_args, **call_kwargs):
                return await anyio.to_thread.run_sync(
                    functools.partial(fn, *call_args, **call_kwargs),
                    limiter=TOOL_THREADS,
                )

            register(run_in_thread)
            return fn

        return decorate


mcp = GraphMCPServer("NetworkX Agent")
