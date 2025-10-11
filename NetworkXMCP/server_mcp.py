"""
FastMCP Server for NetworkX
============================

This file creates a standalone FastMCP server using the OpenAPI specification
from the FastAPI application to automatically generate MCP tools.
"""

import os
import logging
import asyncio
import httpx
from fastmcp import FastMCP

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("networkx_fastmcp")


async def create_mcp_server():
    """Create FastMCP server from OpenAPI specification"""
    try:
        # Base URL for the FastAPI server
        base_url = os.environ.get("FASTAPI_BASE_URL", "http://localhost:8001")

        # Create HTTP client
        client = httpx.AsyncClient(base_url=base_url, timeout=30.0)

        # Try to fetch OpenAPI specification
        try:
            logger.info(f"Fetching OpenAPI spec from {base_url}/openapi.json")
            response = await client.get("/openapi.json")
            response.raise_for_status()
            openapi_spec = response.json()
            logger.info(
                "Successfully fetched OpenAPI spec from running server")
        except Exception as e:
            logger.error(
                f"Could not fetch OpenAPI spec from running server: {e}")
            logger.info(
                "Make sure the FastAPI server is running on the specified base URL")
            raise RuntimeError(f"FastAPI server not available at {base_url}")

        # Create FastMCP server from OpenAPI spec
        mcp = FastMCP.from_openapi(
            openapi_spec=openapi_spec,
            client=client,
            name="NetworkX MCP (FastMCP)",
            tags={"networkx", "graph-analysis", "visualization", "mcp"}
        )

        logger.info(
            "FastMCP server created successfully with OpenAPI integration")
        logger.info(f"FastMCP server initialized with OpenAPI spec")

        return mcp

    except Exception as e:
        logger.error(f"Error creating FastMCP server: {e}")
        raise


async def run_mcp_server():
    """Run the FastMCP server"""
    try:
        # Create the MCP server
        mcp = await create_mcp_server()

        # Start the MCP server
        logger.info("Starting FastMCP server...")
        await mcp.run()

    except KeyboardInterrupt:
        logger.info("MCP server stopped by user")
    except Exception as e:
        logger.error(f"Error running MCP server: {e}")
        raise


if __name__ == "__main__":
    # Run the MCP server
    asyncio.run(run_mcp_server())
