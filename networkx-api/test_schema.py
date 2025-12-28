
from mcp.server.fastmcp import FastMCP
from pydantic import Field
from typing import Annotated

# Create a temporary server
mcp = FastMCP("TestServer")

@mcp.tool()
def test_tool(
    arg1: Annotated[int, Field(description="Description for arg1")],
    arg2: str
) -> str:
    """
    Test tool docstring.
    """
    return "ok"

# Extract tools and print schema
# We need to access the underlying tool registration to see the schema
# FastMCP usually registers tools in an internal registry.
# Let's try to access it via listing tools.

import asyncio

async def run_test():
    tools = await mcp.list_tools()
    for tool in tools:
        print(f"Tool: {tool.name}")
        print(f"Prop arg1: {tool.inputSchema['properties'].get('arg1')}")
        print(f"Prop arg2: {tool.inputSchema['properties'].get('arg2')}")

if __name__ == "__main__":
    asyncio.run(run_test())
