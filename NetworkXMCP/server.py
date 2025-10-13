"""
NetworkX MCP Server - Best Practices Implementation
==================================================

Model Context Protocol server for NetworkX graph analysis and visualization
following MCP best practices as outlined in:
- https://modelcontextprotocol.io/tutorials/building-mcp-with-llms
- https://modelcontextprotocol.io/llms-full.txt

Key improvements:
- Proper stderr logging (CRITICAL for STDIO MCP servers)
- Structured tool responses with input/output schemas
- Resource management for cached data
- Error handling with meaningful messages
- Lifespan management for proper cleanup
"""

import logging
import sys
import json
import uuid
from contextlib import asynccontextmanager
from typing import AsyncIterator, Dict, Any, Optional
from datetime import datetime

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

        def prompt(self):
            def decorator(func):
                return func
            return decorator

        def run(self):
            print(f"Would run {self.name} v{self.version}", file=sys.stderr)

from core.context import ServerContext

# CRITICAL MCP Best Practice: Configure logging to stderr, never stdout
# stdout is reserved for JSON-RPC messages in STDIO transport
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    stream=sys.stderr  # CRITICAL: Use stderr for MCP servers
)
logger = logging.getLogger("networkx_mcp")

# Structured error response helper following MCP patterns


def create_error_response(error_msg: str, error_code: str = "EXECUTION_ERROR") -> Dict[str, Any]:
    """Create standardized error response following MCP best practices."""
    logger.error(f"Error [{error_code}]: {error_msg}")
    return {
        "success": False,
        "error": {
            "code": error_code,
            "message": error_msg,
            "timestamp": datetime.now().isoformat()
        }
    }


def create_success_response(data: Dict[str, Any], operation: str = "unknown") -> Dict[str, Any]:
    """Create standardized success response following MCP best practices."""
    logger.info(f"Success: {operation} completed")
    return {
        "success": True,
        "data": data,
        "timestamp": datetime.now().isoformat()
    }


@asynccontextmanager
async def server_lifespan(server: FastMCP) -> AsyncIterator[ServerContext]:
    """
    Manage server startup and shutdown lifecycle following MCP best practices.

    This lifespan manager:
    - Initializes shared resources and caches
    - Provides proper cleanup on shutdown
    - Logs all lifecycle events to stderr (MCP requirement)
    """
    # Use stderr for all MCP server logs
    logger.info("NetworkX MCP Server starting up with best practices...")

    # Initialize shared resources with enhanced context
    context = ServerContext()

    # Log initialization details
    logger.info(f"Server context initialized: {context.get_cache_stats()}")

    try:
        # Yield context for use during server lifetime
        yield context
    except Exception as e:
        # Log any lifecycle errors
        logger.error(f"Server lifecycle error: {str(e)}")
        raise
    finally:
        # Cleanup on shutdown with proper logging
        logger.info("NetworkX MCP Server shutting down...")
        stats_before_cleanup = context.get_cache_stats()
        context.clear_caches()
        logger.info(f"Cleanup completed. Cleared: {stats_before_cleanup}")


# Create FastMCP server with enhanced configuration following best practices
mcp = FastMCP(
    name="NetworkX Graph Analysis Server",
    version="2.0.0",
    description="Advanced NetworkX graph analysis and visualization server following MCP best practices",
    lifespan=server_lifespan
)

# Import and register tools and resources with enhanced error handling
try:
    from tools.network_operations import register_network_tools
    from tools.layout_algorithms import register_layout_tools
    from tools.centrality_metrics import register_centrality_tools
    from tools.graph_io import register_io_tools
    from tools.visualization import register_visualization_tools

    from resources.graph_resources import register_graph_resources
    from resources.cache_resources import register_cache_resources

    # Register all tools and resources with error handling
    tools_registered = []

    try:
        register_network_tools(mcp)
        tools_registered.append("network_operations")
    except Exception as e:
        logger.error(f"Failed to register network tools: {e}")

    try:
        register_layout_tools(mcp)
        tools_registered.append("layout_algorithms")
    except Exception as e:
        logger.error(f"Failed to register layout tools: {e}")

    try:
        register_centrality_tools(mcp)
        tools_registered.append("centrality_metrics")
    except Exception as e:
        logger.error(f"Failed to register centrality tools: {e}")

    try:
        register_io_tools(mcp)
        tools_registered.append("graph_io")
    except Exception as e:
        logger.error(f"Failed to register I/O tools: {e}")

    try:
        register_visualization_tools(mcp)
        tools_registered.append("visualization")
    except Exception as e:
        logger.error(f"Failed to register visualization tools: {e}")

    # Register resources with error handling
    resources_registered = []

    try:
        register_graph_resources(mcp)
        resources_registered.append("graph_resources")
    except Exception as e:
        logger.error(f"Failed to register graph resources: {e}")

    try:
        register_cache_resources(mcp)
        resources_registered.append("cache_resources")
    except Exception as e:
        logger.error(f"Failed to register cache resources: {e}")

    logger.info(f"Successfully registered tools: {tools_registered}")
    logger.info(f"Successfully registered resources: {resources_registered}")

except ImportError as e:
    logger.warning(f"Could not import tool/resource modules: {e}")
    logger.info("Continuing with basic tool implementations...")


# Enhanced tools with proper MCP structure and error handling

@mcp.tool()
def get_server_info() -> Dict[str, Any]:
    """
    Get comprehensive information about the MCP server and its capabilities.

    Following MCP best practices, this tool provides:
    - Structured server metadata
    - Available tools and their parameters
    - Resource endpoints and their schemas
    - Capability matrix for client discovery

    Returns:
        Dict containing server information, capabilities, and available tools/resources
    """
    try:
        server_info = {
            "server": {
                "name": "NetworkX Graph Analysis Server",
                "version": "2.0.0",
                "description": "Advanced NetworkX graph analysis following MCP best practices",
                "mcp_version": "2025-01-14",
                "protocol_version": "2024-11-05"
            },
            "capabilities": {
                "network_creation": {
                    "types": ["random", "small_world", "scale_free", "custom"],
                    "parameters": ["num_nodes", "edge_probability", "seed"]
                },
                "layout_algorithms": {
                    "algorithms": ["spring", "circular", "spectral", "shell", "kamada_kawai", "fruchterman_reingold", "hierarchical"],
                    "parameters": ["iterations", "k", "pos", "scale"]
                },
                "centrality_measures": {
                    "measures": ["degree", "betweenness", "closeness", "eigenvector", "pagerank"],
                    "features": ["normalized", "weighted", "approximation", "caching"]
                },
                "io_formats": {
                    "input": ["graphml", "adjacency_list", "edge_list", "json"],
                    "output": ["graphml", "json", "positions", "metadata"]
                },
                "visualization": {
                    "features": ["color_mapping", "size_scaling", "edge_styling", "legends"],
                    "color_schemes": ["viridis", "plasma", "inferno", "magma", "coolwarm"]
                },
                "caching": {
                    "types": ["graphs", "calculations", "layouts", "visualizations"],
                    "persistence": "memory",
                    "cleanup": "lifespan_managed"
                }
            },
            "resources": {
                "cache://graphs": {
                    "description": "Cached graph data and metadata",
                    "mime_type": "application/json",
                    "schema": "graph_cache_entry"
                },
                "cache://centrality": {
                    "description": "Cached centrality calculations",
                    "mime_type": "application/json",
                    "schema": "centrality_calculation"
                },
                "cache://stats": {
                    "description": "Cache statistics and server metrics",
                    "mime_type": "application/json",
                    "schema": "cache_statistics"
                }
            },
            "tools": {
                "get_server_info": "Get server capabilities and information",
                "create_sample_graph": "Generate sample graphs for analysis",
                "calculate_centrality": "Compute centrality measures with caching",
                "apply_layout": "Calculate node positions using various algorithms",
                "get_visualization_data": "Generate visualization data from calculations",
                "list_calculations": "List cached calculations and their status",
                "clear_cache": "Clear server caches and reset state"
            }
        }

        return create_success_response(server_info, "get_server_info")

    except Exception as e:
        return create_error_response(
            f"Failed to get server info: {str(e)}",
            "SERVER_INFO_ERROR"
        )


# MCP Resource implementations following best practices

@mcp.resource("cache://status")
def get_cache_status() -> str:
    """
    Get current cache status and statistics.

    Returns cache information in a human-readable format following
    MCP resource best practices.
    """
    try:
        # Note: In a real implementation, this would access the server context
        # For now, providing mock data that matches the expected structure
        stats = {
            "graphs": 0,
            "centrality_calculations": 0,
            "active_calculations": 0,
            "memory_usage": "0 MB"
        }

        return json.dumps({
            "status": "active",
            "cache_stats": stats,
            "last_updated": datetime.now().isoformat(),
            "server_uptime": "running"
        }, indent=2)

    except Exception as e:
        logger.error(f"Error getting cache status: {e}")
        return json.dumps({"error": str(e)})


@mcp.resource("mcp://server-info")
def get_mcp_server_metadata() -> str:
    """
    Get MCP server metadata in standardized format.

    This resource provides server information that clients can use
    for discovery and capability negotiation.
    """
    try:
        metadata = {
            "mcp": {
                "protocol_version": "2024-11-05",
                "server_name": "NetworkX Graph Analysis Server",
                "server_version": "2.0.0",
                "capabilities": ["tools", "resources", "prompts"],
                "transport": "stdio"
            },
            "implementation": {
                "name": "networkx-mcp",
                "version": "2.0.0",
                "language": "python",
                "framework": "fastmcp"
            }
        }

        return json.dumps(metadata, indent=2)

    except Exception as e:
        logger.error(f"Error getting MCP metadata: {e}")
        return json.dumps({"error": str(e)})


# MCP Prompt templates for common graph analysis tasks

@mcp.prompt()
def analyze_network_structure(
    graph_description: str = "a network",
    analysis_type: str = "general"
) -> str:
    """
    Generate analysis prompts for network structure exploration.

    Args:
        graph_description: Description of the network to analyze
        analysis_type: Type of analysis (general, centrality, community, etc.)

    Returns:
        Structured prompt for network analysis
    """
    return f"""Analyze the structure of {graph_description} with focus on {analysis_type} analysis.

Please follow these steps:
1. Load or create the network data
2. Calculate basic network statistics (nodes, edges, density, connectivity)
3. Apply appropriate centrality measures based on analysis type
4. Choose and apply a suitable layout algorithm for visualization
5. Identify key structural patterns and important nodes
6. Provide insights and recommendations

Analysis Type: {analysis_type}
Expected Output: Structured analysis with visualizations and key findings
"""


@mcp.prompt()
def compare_centrality_measures(
    measures: str = "degree, betweenness, closeness"
) -> str:
    """
    Generate prompts for comparing different centrality measures.

    Args:
        measures: Comma-separated list of centrality measures to compare

    Returns:
        Structured prompt for centrality comparison
    """
    measure_list = [m.strip() for m in measures.split(",")]

    return f"""Compare centrality measures for network analysis: {', '.join(measure_list)}

Analysis Steps:
1. Calculate each centrality measure: {', '.join(measure_list)}
2. Identify top-ranked nodes for each measure  
3. Create visualizations showing the differences
4. Explain what each measure reveals about node importance
5. Analyze correlations and differences between measures
6. Recommend the most appropriate measure(s) for your analysis goals

Focus: Understanding how different centrality concepts reveal different aspects of network structure.
"""


@mcp.prompt()
def optimize_graph_layout(
    network_size: str = "medium",
    purpose: str = "exploration"
) -> str:
    """
    Generate prompts for selecting optimal graph layout algorithms.

    Args:
        network_size: Size of network (small, medium, large)
        purpose: Purpose of visualization (exploration, presentation, analysis)

    Returns:
        Structured prompt for layout optimization
    """
    return f"""Optimize graph layout for {network_size} network visualization.

Visualization Purpose: {purpose}
Network Size: {network_size}

Optimization Process:
1. Analyze network characteristics (size, density, structure)
2. Consider the visualization purpose and target audience
3. Test multiple layout algorithms (spring, circular, hierarchical, spectral)
4. Evaluate each layout based on:
   - Node overlap and readability
   - Edge crossing minimization
   - Structural pattern visibility
   - Aesthetic appeal and clarity
5. Fine-tune parameters for the best-performing layout
6. Generate final visualization with optimal settings

Goal: Create the most effective and informative network visualization for {purpose}.
"""


if __name__ == "__main__":
    # Run the MCP server with enhanced logging
    logger.info(
        "Starting NetworkX MCP Server with best practices implementation...")
    logger.info("Server configured with:")
    logger.info("- Structured error handling and responses")
    logger.info("- Proper stderr logging for MCP compatibility")
    logger.info("- Resource endpoints for cached data")
    logger.info("- Prompt templates for common analysis tasks")
    logger.info("- Lifespan management for proper cleanup")

    try:
        mcp.run()
    except Exception as e:
        logger.error(f"Failed to start MCP server: {e}")
        sys.exit(1)
