"""
NetworkX MCP Server
==================

Model Context Protocol server for NetworkX graph analysis and visualization.
Follows MCP best practices with proper separation of concerns.
"""

import logging
import sys
from contextlib import asynccontextmanager
from typing import AsyncIterator

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    # Fallback for development/testing
    print("Warning: MCP library not found. Running in development mode.",
          file=sys.stderr)

    class FastMCP:
        def __init__(self, **kwargs):
            self.name = kwargs.get("name", "Mock MCP")
            self.version = kwargs.get("version", "1.0.0")

        def tool(self):
            def decorator(func):
                return func
            return decorator

        def resource(self, uri):
            def decorator(func):
                return func
            return decorator

        def run(self):
            print(f"Would run {self.name} v{self.version}", file=sys.stderr)

from core.context import ServerContext

# Configure logging for MCP (use stderr, not stdout)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr  # Important: Use stderr for MCP servers
)
logger = logging.getLogger("networkx_mcp")


@asynccontextmanager
async def server_lifespan(server: FastMCP) -> AsyncIterator[ServerContext]:
    """Manage server startup and shutdown lifecycle."""
    logger.info("NetworkX MCP Server starting up...")

    # Initialize shared resources
    context = ServerContext()

    try:
        yield context
    finally:
        # Cleanup on shutdown
        logger.info("NetworkX MCP Server shutting down...")
        context.clear_caches()


# Create FastMCP server with proper configuration
mcp = FastMCP(
    name="NetworkX MCP Server",
    version="1.0.0",
    description="Graph analysis and visualization using NetworkX",
    lifespan=server_lifespan
)

# Import and register tools and resources
try:
    from tools.network_operations import register_network_tools
    from tools.layout_algorithms import register_layout_tools
    from tools.centrality_metrics import register_centrality_tools
    from tools.graph_io import register_io_tools
    from tools.visualization import register_visualization_tools

    from resources.graph_resources import register_graph_resources
    from resources.cache_resources import register_cache_resources

    # Register all tools and resources
    register_network_tools(mcp)
    register_layout_tools(mcp)
    register_centrality_tools(mcp)
    register_io_tools(mcp)
    register_visualization_tools(mcp)

    # Register resources
    register_graph_resources(mcp)
    register_cache_resources(mcp)

    logger.info("All tools and resources registered successfully")

except ImportError as e:
    logger.warning(f"Could not register all tools/resources: {e}")


@mcp.tool()
def get_server_info():
    """Get information about the MCP server and its capabilities."""
    return {
        "success": True,
        "server": {
            "name": "NetworkX MCP Server",
            "version": "1.0.0",
            "description": "Graph analysis and visualization using NetworkX"
        },
        "capabilities": {
            "network_creation": ["random", "small_world", "scale_free"],
            "layout_algorithms": ["spring", "circular", "hierarchical"],
            "centrality_measures": ["degree", "betweenness", "closeness", "eigenvector", "pagerank"],
            "io_formats": ["graphml", "adjacency_list", "edge_list"],
            "visualization": ["color_schemes", "metric_styling", "legends"]
        },
        "resources": {
            "cached_graphs": "graph://",
            "cache_statistics": "cache://",
            "centrality_calculations": "cache://centrality"
        }
    }


if __name__ == "__main__":
    # Run the MCP server
    logger.info("Starting NetworkX MCP Server...")
    mcp.run()
