from typing import Annotated
from pydantic import Field
from app.core.mcp import mcp
from app.core.database import get_db_context
import logging

logger = logging.getLogger(__name__)

@mcp.tool()
def calculate_centrality(
    network_id: Annotated[int, Field(description="The ID of the network.")],
    centrality_type: Annotated[str, Field(description="The type of centrality to calculate. Valid values: 'degree', 'betweenness', 'closeness', 'eigenvector', 'pagerank'.")]
) -> str:
    """
    Calculates specific centrality for the network and saves it as a node attribute.
            
    Returns:
        str: Status message.
    """
    with get_db_context() as db:
        try:
            from app.logic import centrality
            centrality.calculate_centrality(network_id, centrality_type, db)
            return f"{centrality_type} centrality calculated and saved as node attribute '{centrality_type}_centrality'."
        except Exception as e:
            logger.error(f"calculate_centrality failed: {e}")
            raise RuntimeError(f"Centrality calculation failed: {str(e)}") from e


# @mcp.tool()
def calculate_community(
    network_id: Annotated[int, Field(description="The ID of the network.")],
    algorithm: Annotated[str, Field(description="The algorithm to use for community detection. Valid values: 'louvain', 'greedy_modularity', 'label_propagation'. Default is 'louvain'.")] = "louvain"
) -> str:
    """
    Detects communities in the network and saves them as a node attribute ('community').
            
    Returns:
        str: Status message.
    """
    with get_db_context() as db:
        try:
            from app.logic import community
            community.calculate_community(network_id, algorithm, db)
            return f"Communities detected using {algorithm}."
        except Exception as e:
            logger.error(f"calculate_community failed: {e}")
            raise RuntimeError(f"Community detection failed: {str(e)}") from e


@mcp.tool()
def calculate_layout(
    network_id: Annotated[int, Field(description="The ID of the network.")],
    layout_name: Annotated[str, Field(description="The name of the layout algorithm to use. Supported Layouts: 'forceatlas2' (Default), 'spring', 'kamada_kawai', 'circular', 'shell', 'spectral', 'spiral', 'random'.")]
) -> str:
    """
    Calculates a graph layout and saves x, y coordinates as node attributes.
    This tool DOES NOT return visualization data.
    To visualize the new layout, you must use the `update_layout` tool.
    
    Args:
        network_id: The ID of the network.
        layout_name: The name of the layout algorithm to use.
            Supported Layouts:
            - "forceatlas2" (Default): Best for most networks (force-directed).
            - "spring": Fruchterman-Reingold algorithm. Good for small graphs.
            - "kamada_kawai": Good global structure but slow (O(N^2)).
            - "circular": Position nodes on a circle.
            - "shell": Position nodes in concentric circles.
            - "spectral": Position nodes using the eigenvectors of the graph Laplacian.
            - "spiral": Position nodes in a spiral layout.
            - "random": Position nodes uniformly at random.
            
    Returns:
        str: Status message.
    """
    with get_db_context() as db:
        try:
            from app.logic import layout
            layout.calculate_layout(network_id, layout_name, db)
            return f"Layout '{layout_name}' calculated. Call `update_layout` to visualize it."
        except Exception as e:
            logger.error(f"calculate_layout failed: {e}")
            raise RuntimeError(f"Layout calculation failed: {str(e)}") from e
