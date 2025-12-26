from typing import Any, Dict, List

import networkx as nx
from sqlalchemy.orm import Session

from common import models

from .attributes import delete_attribute_values, get_or_create_attribute


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

    # Save to DB - Bulk Update Strategy
    attr_name = f"{centrality_type}_centrality"
    attr = get_or_create_attribute(
        network_id, attr_name, models.NodeAttribute, db, data_type="float"
    )

    # Delete existing
    delete_attribute_values(network_id, attr.id, models.NodeAttributeValue, db, commit=False)

    # Bulk Insert
    nav_data = []
    for node_id in centrality:
        db_node_id = node_map[node_id]
        nav_data.append({"node_id": db_node_id, "attribute_id": attr.id})

    if nav_data:
        db.bulk_insert_mappings(models.NodeAttributeValue, nav_data)
        db.commit()

        all_navs = (
            db.query(models.NodeAttributeValue)
            .filter(
                models.NodeAttributeValue.attribute_id == attr.id,
                models.NodeAttributeValue.node_id.in_(node_map.values()),
            )
            .all()
        )
        nav_map = {(nav.node_id, nav.attribute_id): nav.id for nav in all_navs}

        float_vals = []
        for node_id, value in centrality.items():
            db_node_id = node_map[node_id]
            nav_id = nav_map.get((db_node_id, attr.id))
            if nav_id:
                float_vals.append(
                    {"node_attribute_value_id": nav_id, "float_value": float(value)}
                )

        if float_vals:
            db.bulk_insert_mappings(models.NodeFloatAttributeValue, float_vals)
        db.commit()

    return centrality


def get_top_nodes(
    network_id: int, metric: str, k: int, db: Session
) -> List[Dict[str, Any]]:
    """
    Returns the top k nodes based on the specified centrality metric.
    """
    # Calculate centrality (this also saves to DB, which is fine)
    # We reuse the existing logic.
    centrality = calculate_centrality(network_id, metric, db)

    # Sort by score descending
    sorted_nodes = sorted(centrality.items(), key=lambda item: item[1], reverse=True)

    # Take top k
    top_nodes = sorted_nodes[:k]

    return [{"node_id": node_id, "score": score} for node_id, score in top_nodes]
