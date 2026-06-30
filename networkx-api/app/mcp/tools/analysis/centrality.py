from typing import Annotated
from pydantic import Field
from app.core.mcp import mcp
from app.core.database import get_db_context
from app.core.decorators import handle_tool_errors
import logging

logger = logging.getLogger(__name__)


@mcp.tool()
@handle_tool_errors
def analysis_degree_centrality(
    network_id: Annotated[int, Field(description="The ID of the network.")]
) -> str:
    """
    Calculates degree centrality for all nodes and saves as 'degree_centrality' attribute.

    Degree centrality = fraction of other nodes each node is connected to.
    Simple but effective: high-degree nodes are direct hubs.
    Saved attribute name: 'degree_centrality'

    Returns:
        str: Status message.
    """
    with get_db_context() as db:
        from app.logic import centrality
        centrality.calculate_centrality(network_id, "degree", db)
        return "Degree centrality calculated and saved as 'degree_centrality'."


@mcp.tool()
@handle_tool_errors
def analysis_betweenness_centrality(
    network_id: Annotated[int, Field(description="The ID of the network.")]
) -> str:
    """
    Calculates betweenness centrality for all nodes and saves as 'betweenness_centrality' attribute.

    Betweenness centrality measures how often a node lies on the shortest path between other nodes.
    High values = bridge/broker nodes controlling information flow.
    WARNING: O(N * E) complexity — can be slow on very large graphs.
    Saved attribute name: 'betweenness_centrality'

    Returns:
        str: Status message.
    """
    with get_db_context() as db:
        from app.logic import centrality
        centrality.calculate_centrality(network_id, "betweenness", db)
        return "Betweenness centrality calculated and saved as 'betweenness_centrality'."


@mcp.tool()
@handle_tool_errors
def analysis_closeness_centrality(
    network_id: Annotated[int, Field(description="The ID of the network.")]
) -> str:
    """
    Calculates closeness centrality for all nodes and saves as 'closeness_centrality' attribute.

    Closeness centrality = inverse of average shortest-path distance to all other nodes.
    High values = nodes that can quickly reach all others; useful for diffusion analysis.
    Saved attribute name: 'closeness_centrality'

    Returns:
        str: Status message.
    """
    with get_db_context() as db:
        from app.logic import centrality
        centrality.calculate_centrality(network_id, "closeness", db)
        return "Closeness centrality calculated and saved as 'closeness_centrality'."


@mcp.tool()
@handle_tool_errors
def analysis_eigenvector_centrality(
    network_id: Annotated[int, Field(description="The ID of the network.")]
) -> str:
    """
    Calculates eigenvector centrality for all nodes and saves as 'eigenvector_centrality' attribute.

    Eigenvector centrality rewards being connected to other high-centrality nodes.
    Similar to PageRank but undirected. Useful for finding influential nodes in dense networks.
    Saved attribute name: 'eigenvector_centrality'

    Returns:
        str: Status message.
    """
    with get_db_context() as db:
        from app.logic import centrality
        centrality.calculate_centrality(network_id, "eigenvector", db)
        return "Eigenvector centrality calculated and saved as 'eigenvector_centrality'."


@mcp.tool()
@handle_tool_errors
def analysis_pagerank(
    network_id: Annotated[int, Field(description="The ID of the network.")],
    damping_factor: Annotated[float, Field(description="Damping factor (alpha) for PageRank. Default 0.85.")] = 0.85
) -> str:
    """
    Calculates PageRank for all nodes and saves as 'pagerank' attribute.

    PageRank scores nodes by the quality and quantity of links pointing to them
    (originally developed by Google). High PageRank = important node in the network.
    Saved attribute name: 'pagerank'

    Returns:
        str: Status message.
    """
    with get_db_context() as db:
        from app.logic import centrality
        centrality.calculate_centrality(network_id, "pagerank", db)
        return "PageRank calculated and saved as 'pagerank'."


@mcp.tool()
@handle_tool_errors
def analysis_clustering_coefficient(
    network_id: Annotated[int, Field(description="The ID of the network.")]
) -> str:
    """
    Calculates the local clustering coefficient for each node and saves as 'clustering' attribute.

    The clustering coefficient measures the fraction of a node's neighbors that are
    also connected to each other (i.e., how clique-like the local neighborhood is).
    Values range from 0 (no triangles) to 1 (all neighbors are fully connected).
    Saved attribute name: 'clustering'

    Returns:
        str: Status message.
    """
    with get_db_context() as db:
        import networkx as nx
        from app.logic.utils.graph_builder import build_graph_from_db
        from app.logic.attributes import bulk_save_node_attributes
        from common import models

        G = build_graph_from_db(network_id, db)
        clustering = nx.clustering(G)

        nodes = db.query(models.Node.id, models.Node.node_id).filter(
            models.Node.network_id == network_id
        ).all()
        node_map = {n.node_id: n.id for n in nodes}

        data_map = {
            node_map[nid]: val
            for nid, val in clustering.items()
            if nid in node_map
        }

        bulk_save_node_attributes(network_id, "clustering", "float", data_map, db)
        avg = sum(clustering.values()) / len(clustering) if clustering else 0
        return f"Clustering coefficients calculated and saved as 'clustering'. Average: {avg:.4f}"
