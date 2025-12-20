from typing import Any, Dict, List

import networkx as nx
from sqlalchemy.orm import Session

from app import models

from .attributes import delete_attribute_values, get_or_create_attribute


def calculate_centrality(network_id: int, centrality_type: str, db: Session):
    # Reconstruct graph (Same as layout)
    G = nx.Graph()
    nodes = db.query(models.Node).filter(models.Node.network_id == network_id).all()
    id_map = {n.id: n.node_id for n in nodes}
    node_map = {n.node_id: n.id for n in nodes}

    for n in nodes:
        G.add_node(n.node_id)

    edges = db.query(models.Edge).filter(models.Edge.network_id == network_id).all()
    for e in edges:
        u = id_map.get(e.source_node_id)
        v = id_map.get(e.target_node_id)
        if u and v:
            G.add_edge(u, v)

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
    delete_attribute_values(network_id, attr.id, models.NodeAttributeValue, db)

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
