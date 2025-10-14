"""
NetworkX MCP Server (Proper FastMCP Implementation)
==================================================

FastMCP Model Context Protocol (MCP) server for network analysis and visualization.
This server provides MCP tools for NetworkX-based graph analysis.
"""

from tools.network_tools import apply_layout_to_graphml
from tools.centrality_persistence import (
    calculate_and_store_centrality,
    get_centrality_visualization_data,
    list_stored_calculations,
    get_calculation_status
)
import os
import logging
import networkx as nx
import numpy as np
from typing import Dict, Any, List, Optional, Union
import random
import json
import io
from datetime import datetime

# Configure logging
log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("networkx_mcp")

# Import FastMCP
try:
    from mcp.server.fastmcp import FastMCP
    MCP_AVAILABLE = True
except ImportError:
    logger.error("FastMCP not available. Please install mcp package.")
    MCP_AVAILABLE = False
    exit(1)

# Import NetworkX tools

# Initialize FastMCP server
mcp = FastMCP("NetworkX MCP Server")

# --- MCP Tools ---


@mcp.tool()
def get_sample_network() -> str:
    """Generate a sample network in GraphML format for testing purposes."""
    try:
        num_nodes = random.randint(18, 25)
        edge_probability = random.uniform(0.15, 0.25)
        G = nx.gnp_random_graph(num_nodes, edge_probability)

        # Ensure connectivity
        if not nx.is_connected(G):
            components = list(nx.connected_components(G))
            largest_component = max(components, key=len)
            for component in components:
                if component != largest_component:
                    node_from = random.choice(list(component))
                    node_to = random.choice(list(largest_component))
                    G.add_edge(node_from, node_to)

        # Apply spring layout
        positions = nx.spring_layout(G, k=1.0, iterations=50, seed=42)

        # Set node attributes (position, size, color)
        for node in G.nodes():
            pos = positions.get(node, (0, 0))
            G.nodes[node]['x'] = str(float(pos[0]))
            G.nodes[node]['y'] = str(float(pos[1]))
            G.nodes[node]['name'] = f"Node {node}"
            G.nodes[node]['size'] = "5.0"
            G.nodes[node]['color'] = "#1d4ed8"
            G.nodes[node]['description'] = f"Sample node {node}"

        # Set edge attributes
        for u, v in G.edges():
            G.edges[u, v]['width'] = "1.0"
            G.edges[u, v]['color'] = "#94a3b8"

        # Export as GraphML
        output = io.BytesIO()
        nx.write_graphml(G, output)
        output.seek(0)
        graphml_content = output.read().decode("utf-8")

        logger.info(
            f"Generated sample network with {G.number_of_nodes()} nodes and {G.number_of_edges()} edges")
        return json.dumps({
            "success": True,
            "graphml_content": graphml_content,
            "metadata": {
                "num_nodes": G.number_of_nodes(),
                "num_edges": G.number_of_edges(),
                "layout_type": "spring"
            }
        })
    except Exception as e:
        logger.error(f"Error creating sample network: {e}")
        return json.dumps({
            "success": False,
            "error": f"Error creating sample network: {str(e)}"
        })


@mcp.tool()
def change_layout(
    graphml_content: str,
    layout_type: str = "spring",
    layout_params: Optional[Dict[str, Any]] = None
) -> str:
    """
    Change the layout algorithm for a given network.

    Args:
        graphml_content: GraphML content representing the network
        layout_type: The layout algorithm to apply (spring, circular, random, etc.)
        layout_params: Optional parameters for the layout algorithm

    Returns:
        JSON string with layout results including new positions
    """
    try:
        if layout_params is None:
            layout_params = {}

        result = apply_layout_to_graphml(
            graphml_content, layout_type, layout_params)
        logger.info(f"Applied {layout_type} layout successfully")
        return json.dumps(result)
    except Exception as e:
        logger.error(f"Error applying layout {layout_type}: {e}")
        return json.dumps({
            "success": False,
            "error": f"Error applying layout: {str(e)}"
        })


@mcp.tool()
def calculate_and_store_centrality_mcp(
    graphml_content: str,
    centrality_type: str = "degree",
    centrality_params: Optional[Dict[str, Any]] = None
) -> str:
    """
    Calculate centrality values and store them for later visualization (Stage 1).

    Args:
        graphml_content: GraphML content representing the network
        centrality_type: Type of centrality (degree, betweenness, closeness, eigenvector, pagerank, katz)
        centrality_params: Optional parameters for centrality calculation

    Returns:
        JSON string with calculation results including calculation_id
    """
    try:
        if centrality_params is None:
            centrality_params = {}

        result = calculate_and_store_centrality(
            graphml_content=graphml_content,
            centrality_type=centrality_type,
            centrality_params=centrality_params
        )

        logger.info(f"Calculated and stored {centrality_type} centrality")
        return json.dumps(result)
    except Exception as e:
        logger.error(f"Error calculating centrality: {e}")
        return json.dumps({
            "success": False,
            "error": f"Error calculating centrality: {str(e)}"
        })


@mcp.tool()
def get_centrality_visualization(
    calculation_id: str,
    color_scheme: str = "viridis",
    size_range: Optional[List[float]] = None
) -> str:
    """
    Generate visualization data from stored centrality calculation (Stage 2).

    Args:
        calculation_id: ID of the stored centrality calculation
        color_scheme: Color scheme for visualization (viridis, plasma, etc.)
        size_range: Node size range [min, max] for better visibility

    Returns:
        JSON string with visualization data including colors and sizes
    """
    try:
        if size_range is None:
            # Enhanced default range for better visibility
            size_range = [30, 80]

        result = get_centrality_visualization_data(
            calculation_id=calculation_id,
            color_scheme=color_scheme,
            size_range=tuple(size_range)
        )

        logger.info(
            f"Generated visualization for calculation {calculation_id}")
        return json.dumps(result)
    except Exception as e:
        logger.error(f"Error generating visualization: {e}")
        return json.dumps({
            "success": False,
            "error": f"Error generating visualization: {str(e)}"
        })


@mcp.tool()
def list_centrality_calculations() -> str:
    """
    List all stored centrality calculations.

    Returns:
        JSON string with list of calculations
    """
    try:
        result = list_stored_calculations()
        logger.info("Listed centrality calculations")
        return json.dumps(result)
    except Exception as e:
        logger.error(f"Error listing calculations: {e}")
        return json.dumps({
            "success": False,
            "error": f"Error listing calculations: {str(e)}"
        })


@mcp.tool()
def get_centrality_status(calculation_id: str) -> str:
    """
    Get status and details of a specific centrality calculation.

    Args:
        calculation_id: ID of the centrality calculation

    Returns:
        JSON string with calculation status and metadata
    """
    try:
        result = get_calculation_status(calculation_id=calculation_id)
        logger.info(f"Retrieved status for calculation {calculation_id}")
        return json.dumps(result)
    except Exception as e:
        logger.error(f"Error getting calculation status: {e}")
        return json.dumps({
            "success": False,
            "error": f"Error getting calculation status: {str(e)}"
        })


@mcp.tool()
def get_network_info(graphml_content: str) -> str:
    """
    Get basic information about a network.

    Args:
        graphml_content: GraphML content representing the network

    Returns:
        JSON string with network statistics
    """
    try:
        # Parse GraphML
        content_io = io.BytesIO(graphml_content.encode('utf-8'))
        G = nx.read_graphml(content_io)

        # Calculate basic statistics
        info = {
            "success": True,
            "num_nodes": G.number_of_nodes(),
            "num_edges": G.number_of_edges(),
            "density": nx.density(G),
            "is_connected": nx.is_connected(G),
            "number_of_components": nx.number_connected_components(G),
            "average_clustering": nx.average_clustering(G) if G.number_of_nodes() > 0 else 0,
            "is_directed": G.is_directed(),
            "node_list": list(G.nodes()),
            "edge_list": list(G.edges())
        }

        # Add degree statistics if nodes exist
        if G.number_of_nodes() > 0:
            degrees = [G.degree(n) for n in G.nodes()]
            info.update({
                "average_degree": sum(degrees) / len(degrees),
                "max_degree": max(degrees),
                "min_degree": min(degrees)
            })

        logger.info(
            f"Retrieved network info: {info['num_nodes']} nodes, {info['num_edges']} edges")
        return json.dumps(info)
    except Exception as e:
        logger.error(f"Error getting network info: {e}")
        return json.dumps({
            "success": False,
            "error": f"Error getting network info: {str(e)}"
        })


# --- Main Entry Point ---

def main():
    """Main entry point for the MCP server."""
    if not MCP_AVAILABLE:
        logger.error("FastMCP is not available. Cannot start server.")
        exit(1)

    logger.info("Starting NetworkX MCP Server...")
    try:
        # Run with stdio transport (default for MCP)
        mcp.run(transport="stdio")
    except Exception as e:
        logger.error(f"Failed to start MCP server: {e}")
        exit(1)


if __name__ == "__main__":
    main()
