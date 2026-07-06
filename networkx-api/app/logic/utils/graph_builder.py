import networkx as nx
from sqlalchemy.orm import Session

from common import models
from app.core.logging import get_logger

logger = get_logger(__name__)


def build_graph_from_db(
    network_id: int, db: Session, include_weights: bool = False
) -> nx.Graph:
    """
    Reconstructs a NetworkX graph from the database for a given network_id.
    Optimized to fetch only necessary ID columns.

    Args:
        network_id: The ID of the network.
        db: Database session.
        include_weights: If True, also fetches `models.Edge.weight` and sets it as
            the `weight` edge attribute on the constructed graph (so weighted
            centrality algorithms can use it via `weight="weight"`). Defaults to
            False to keep the common (unweighted) path as fast as before this
            option existed — omitting it reproduces the exact prior behavior.
    """
    G = nx.Graph()

    # Optimized Node Query: Fetch only id (pk) and node_id (string id)
    nodes_query = (
        db.query(models.Node.id, models.Node.node_id)
        .filter(models.Node.network_id == network_id)
        .all()
    )

    id_map = {row.id: row.node_id for row in nodes_query}  # db_id -> str_id

    for row in nodes_query:
        G.add_node(row.node_id)

    logger.info(
        f"GraphBuilder: Loaded {len(G.nodes)} nodes for Network {network_id}."
    )

    # Optimized Edge Query: Fetch only source/target IDs (plus weight if requested)
    if include_weights:
        edges_query = (
            db.query(
                models.Edge.source_node_id,
                models.Edge.target_node_id,
                models.Edge.weight,
            )
            .filter(models.Edge.network_id == network_id)
            .all()
        )
    else:
        edges_query = (
            db.query(models.Edge.source_node_id, models.Edge.target_node_id)
            .filter(models.Edge.network_id == network_id)
            .all()
        )

    edge_count = 0
    for row in edges_query:
        u = id_map.get(row.source_node_id)
        v = id_map.get(row.target_node_id)
        if u and v:
            if include_weights:
                weight = row.weight if row.weight is not None else 1.0
                G.add_edge(u, v, weight=weight)
            else:
                G.add_edge(u, v)
            edge_count += 1
        else:
            # This might happen if edges point to non-existent nodes
            # (shouldn't happen with FKs but good to be safe)
            pass

    logger.info(
        f"GraphBuilder: Loaded {edge_count} edges for Network {network_id}."
    )

    return G
