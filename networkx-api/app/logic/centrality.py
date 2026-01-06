from typing import Any, Dict, List

import networkx as nx
from sqlalchemy.orm import Session

from common import models

from .attributes import bulk_save_node_attributes


def calculate_centrality(network_id: int, centrality_type: str, db: Session):
    # Reconstruct graph (Optimized)
    from .utils.graph_builder import build_graph_from_db
    G = build_graph_from_db(network_id, db)

    # Need node_map for saving results later (node_id -> db_id)
    # We can fetch this efficiently or reconstruct it.
    # Since we need to map back to DB IDs for saving, let's fetch map.
    nodes = db.query(models.Node.id, models.Node.node_id).filter(models.Node.network_id == network_id).all()
    node_map = {n.node_id: n.id for n in nodes}

    # Calculate Centrality
    if centrality_type == "degree":
        centrality = nx.degree_centrality(G)
    elif centrality_type == "betweenness":
        centrality = nx.betweenness_centrality(G)
    elif centrality_type == "closeness":
        centrality = nx.closeness_centrality(G)
    elif centrality_type == "eigenvector":
        centrality = nx.eigenvector_centrality(G, max_iter=1000)
    elif centrality_type == "pagerank":
        centrality = nx.pagerank(G, alpha=0.85)
    else:
        raise ValueError(f"Unknown centrality type: {centrality_type}")

    # Prepare data for bulk save (db_node_id -> value)
    data_map = {}
    for node_id, score in centrality.items():
        if node_id in node_map:
            db_node_id = node_map[node_id]
            data_map[db_node_id] = score

    # Save to DB - Bulk Update Strategy
    attr_name = f"{centrality_type}_centrality"
    bulk_save_node_attributes(network_id, attr_name, "float", data_map, db)

    return centrality


def get_top_nodes(
    network_id: int, metric: str, k: int, order: str, db: Session
) -> List[Dict[str, Any]]:
    """
    Returns the top k nodes based on the specified centrality metric.
    """
    # Calculate centrality (this also saves to DB, which is fine)
    # We reuse the existing logic.
    centrality = calculate_centrality(network_id, metric, db)

    # Determine reverse flag based on order
    reverse = True
    if order == "asc":
        reverse = False

    # Sort by score
    sorted_nodes = sorted(centrality.items(), key=lambda item: item[1], reverse=reverse)

    # Take top k
    top_nodes = sorted_nodes[:k]

    return [{"node_id": node_id, "score": score} for node_id, score in top_nodes]
