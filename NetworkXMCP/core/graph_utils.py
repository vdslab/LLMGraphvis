"""
Core graph utilities and helpers.
"""

import io
import logging
from typing import Dict, Any, Optional, Union
import networkx as nx

logger = logging.getLogger("networkx_mcp.core.graph")


def parse_graphml_content(graphml_content: str) -> nx.Graph:
    """
    Parse GraphML content string into NetworkX graph.

    Args:
        graphml_content: GraphML content as string

    Returns:
        NetworkX graph object

    Raises:
        ValueError: If GraphML content is invalid
    """
    try:
        logger.debug(
            f"Parsing GraphML content (length: {len(graphml_content)})")
        content_io = io.BytesIO(graphml_content.encode('utf-8'))
        G = nx.read_graphml(content_io)
        logger.debug(
            f"Successfully parsed GraphML with {G.number_of_nodes()} nodes and {G.number_of_edges()} edges")
        return G
    except Exception as e:
        error_msg = f"Failed to parse GraphML content: {str(e)}"
        logger.error(error_msg)
        raise ValueError(error_msg)


def graph_to_graphml_string(G: nx.Graph) -> str:
    """
    Convert NetworkX graph to GraphML string.

    Args:
        G: NetworkX graph object

    Returns:
        GraphML content as string
    """
    try:
        output = io.BytesIO()
        nx.write_graphml(G, output)
        output.seek(0)
        return output.read().decode("utf-8")
    except Exception as e:
        error_msg = f"Failed to convert graph to GraphML: {str(e)}"
        logger.error(error_msg)
        raise ValueError(error_msg)


def validate_graph(G: nx.Graph) -> Dict[str, Any]:
    """
    Validate and analyze basic graph properties.

    Args:
        G: NetworkX graph object

    Returns:
        Dictionary with graph validation results
    """
    return {
        "valid": True,
        "nodes": G.number_of_nodes(),
        "edges": G.number_of_edges(),
        "is_connected": nx.is_connected(G) if G.number_of_nodes() > 0 else False,
        "is_directed": G.is_directed(),
        "density": nx.density(G)
    }


def create_cytoscape_data(G: nx.Graph, positions: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Convert NetworkX graph to Cytoscape.js format.

    Args:
        G: NetworkX graph object
        positions: Optional node positions dictionary

    Returns:
        Dictionary in Cytoscape.js format
    """
    nodes = []
    for node, attrs in G.nodes(data=True):
        node_data = {
            "data": {"id": str(node), "label": attrs.get("label", str(node)), **attrs}
        }
        if positions and str(node) in positions:
            node_data["position"] = positions[str(node)]
        nodes.append(node_data)

    edges = [
        {"data": {"source": str(u), "target": str(v),
                  "id": f"{u}-{v}", **attrs}}
        for u, v, attrs in G.edges(data=True)
    ]

    return {"nodes": nodes, "edges": edges}
