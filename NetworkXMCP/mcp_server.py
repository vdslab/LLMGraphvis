#!/usr/bin/env python3
"""
MCP Server Entry Point for NetworkX
===================================

This script provides a proper MCP server entry point using stdio transport
while keeping the existing HTTP API server for backwards compatibility.
"""

import sys
import json
import asyncio
from main_mcp import mcp


async def main():
    """Run the MCP server with stdio transport."""
    try:
        # Run the FastMCP server with stdio transport
        await mcp.run_async(transport="stdio")
    except Exception as e:
        print(f"Error running MCP server: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
