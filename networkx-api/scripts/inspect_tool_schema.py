"""Inspect a standalone MCP parameter schema without connecting to a database."""

import asyncio
from typing import Annotated

from mcp.server import MCPServer
from pydantic import Field

mcp = MCPServer("Schema inspector")


@mcp.tool()
def sample_tool(
    count: Annotated[int, Field(description="Number of entries to return")],
    label: str,
) -> str:
    """Return a sample label."""
    return label


async def main():
    for tool in await mcp.list_tools():
        print(tool.name, tool.input_schema)


if __name__ == "__main__":
    asyncio.run(main())
