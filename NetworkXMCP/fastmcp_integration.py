"""
NetworkX FastMCP Integration
============================

This module provides integration utilities for FastMCP and OpenAPI.
"""

import os
import logging
import httpx
from fastapi import FastAPI
from fastmcp import FastMCP

logger = logging.getLogger(__name__)


class NetworkXFastMCP:
    """FastMCP integration wrapper for NetworkX server"""

    def __init__(self, fastapi_app: FastAPI, base_url: str = None):
        self.app = fastapi_app
        self.base_url = base_url or os.environ.get(
            "BASE_URL", "http://localhost:8001")
        self.mcp_server = None
        self.http_client = None

    async def create_mcp_server(self):
        """Create FastMCP server from the FastAPI application's OpenAPI spec"""
        try:
            # Create HTTP client
            self.http_client = httpx.AsyncClient(
                base_url=self.base_url, timeout=30.0)

            # Get OpenAPI spec from the app
            try:
                # Try to fetch from running server first
                response = await self.http_client.get("/openapi.json")
                openapi_spec = response.json()
                logger.info("Fetched OpenAPI spec from running server")
            except Exception as e:
                logger.warning(
                    f"Could not fetch from server: {e}, using app.openapi()")
                # Fall back to generating from app
                openapi_spec = self.app.openapi()

            # Create FastMCP server
            self.mcp_server = FastMCP.from_openapi(
                openapi_spec=openapi_spec,
                client=self.http_client,
                name="NetworkX MCP (FastMCP)",
                tags={"networkx", "graph-analysis", "visualization"}
            )

            logger.info("FastMCP server created successfully")
            return self.mcp_server

        except Exception as e:
            logger.error(f"Error creating FastMCP server: {e}")
            raise

    async def run_mcp_server(self):
        """Run the MCP server"""
        if not self.mcp_server:
            await self.create_mcp_server()

        logger.info("Starting FastMCP server...")
        await self.mcp_server.run()

    async def close(self):
        """Clean up resources"""
        if self.http_client:
            await self.http_client.aclose()


def create_fastmcp_integration(app: FastAPI, base_url: str = None) -> NetworkXFastMCP:
    """Factory function to create FastMCP integration"""
    return NetworkXFastMCP(app, base_url)
