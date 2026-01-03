from typing import Annotated, Optional
from pydantic import Field
from app.core.mcp import mcp
from app.core.database import get_db_context
import logging
import traceback
import json

logger = logging.getLogger(__name__)

@mcp.tool()
def get_top_nodes(
    network_id: Annotated[int, Field(description="The ID of the network.")],
    metric: Annotated[str, Field(description="The node attribute/metric to sort by (e.g., 'degree', 'betweenness').")],
    n: Annotated[int, Field(description="Number of top nodes to retrieve.")] = 10,
    order: Annotated[str, Field(description="'desc' (highest first) or 'asc' (lowest first).")] = "desc"
) -> str:
    """
    Retrieves the top N nodes based on a specific metric.
    
    Returns:
        str: Formatted string list of nodes and their values.
    """
    with get_db_context() as db:
        try:
            from app.logic import centrality
            return json.dumps(centrality.get_top_nodes(network_id, metric, n, order, db), default=str)
        except Exception as e:
            logger.error(f"get_top_nodes failed: {e}")
            raise RuntimeError(f"Failed to get top nodes: {str(e)}") from e


@mcp.tool()
def search_nodes(
    network_id: Annotated[int, Field(description="The ID of the network.")],
    query: Annotated[str, Field(description="The search query (part of node ID or label).")]
) -> str:
    """
    Searches for nodes whose ID or label matches the query.
    
    Returns:
        str: Formatted list of matching nodes.
    """
    with get_db_context() as db:
        try:
            from app.logic import search
            return json.dumps(search.search_nodes(network_id, query, db=db), default=str)
        except Exception as e:
            logger.error(f"search_nodes failed: {e}")
            raise RuntimeError(f"Node search failed: {str(e)}") from e


@mcp.tool()
def get_network_structure(
    network_id: Annotated[int, Field(description="The ID of the network.")]
) -> str:
    """
    Returns a summary of the network structure (node count, edge count, density) AND metadata (name, description).
    Useful for understanding the dataset before performing heavy operations.

    Returns:
        str: Summary text.
    """
    with get_db_context() as db:
        try:
            from app.logic import network_metadata
            structure = network_metadata.get_network_structure(db, network_id)
            metadata = network_metadata.get_network_metadata(db, network_id)
            # Combine structure and metadata
            result = {**structure, **metadata}
            return json.dumps(result, default=str)
        except Exception as e:
            logger.error(f"get_network_structure failed: {e}")
            raise RuntimeError(f"Failed to get network structure: {str(e)}") from e


@mcp.tool()
def list_node_attributes(
    network_id: Annotated[int, Field(description="The ID of the network.")]
) -> str:
    """
    Lists all available node attributes (metadata) in the network.
    Use this to see what data is available for coloring, sizing, or filtering.

    Returns:
        str: List of attribute names and types.
    """
    with get_db_context() as db:
        try:
            from app.logic import network_metadata
            return json.dumps(network_metadata.list_node_attributes(db, network_id), default=str)
        except Exception as e:
            logger.error(f"list_node_attributes failed: {e}")
            raise RuntimeError(f"Failed to list node attributes: {str(e)}") from e


@mcp.tool()
def list_edge_attributes(
    network_id: Annotated[int, Field(description="The ID of the network.")]
) -> str:
    """
    Lists all available edge attributes (metadata) in the network.

    Returns:
        str: List of attribute names and types.
    """
    with get_db_context() as db:
        try:
            from app.logic import network_metadata
            return json.dumps(network_metadata.list_edge_attributes(db, network_id), default=str)
        except Exception as e:
            logger.error(f"list_edge_attributes failed: {e}")
            raise RuntimeError(f"Failed to list edge attributes: {str(e)}") from e


@mcp.tool()
def get_node_details(
    network_id: Annotated[int, Field(description="The ID of the network.")],
    node_id: Annotated[str, Field(description="The ID of the node to retrieve details for.")]
) -> str:
    """
    Retrieves all attributes for a specific node.

    Returns:
        str: JSON-formatted details of the node.
    """
    with get_db_context() as db:
        try:
            import app.logic.search
            result = app.logic.search.get_node_details(network_id, node_id, db)
            if result is None:
                return json.dumps({"error": "Node not found"})
            return json.dumps(result, default=str)
        except Exception as e:
            logger.error(f"get_node_details failed: {e}")
            raise RuntimeError(f"Failed to get node details: {str(e)}") from e
