from typing import Any, Dict, List

import networkx as nx
from sqlalchemy.orm import Session

from common import models

from .attributes import delete_attribute_values, get_or_create_attribute


def calculate_community(network_id: int, algorithm: str, db: Session) -> str:
    """
    Calculates communities for the network and saves them as a categorical node attribute.
    
    Args:
        network_id: The ID of the network.
        algorithm: "louvain", "greedy_modularity", "label_propagation"
        db: Database session.
        
    Returns:
        The name of the attribute created (e.g., "community").
    """
    # Reconstruct graph
    G = nx.Graph()
    nodes = db.query(models.Node).filter(models.Node.network_id == network_id).all()
    # Map internal ID -> database ID
    id_map = {n.id: n.node_id for n in nodes}
    # Map database ID -> internal ID (for saving)
    node_map = {n.node_id: n.id for n in nodes}

    for n in nodes:
        G.add_node(n.node_id)

    edges = db.query(models.Edge).filter(models.Edge.network_id == network_id).all()
    for e in edges:
        u = id_map.get(e.source_node_id)
        v = id_map.get(e.target_node_id)
        if u and v:
            G.add_edge(u, v)

    # Detect Communities
    # Returns list of sets of nodes, e.g. [{n1, n2}, {n3, n4}]
    partition = []
    
    if algorithm == "louvain":
        # nx.community.louvain_communities returns list of sets
        try:
             partition = nx.community.louvain_communities(G)
        except AttributeError:
             # Fallback for older NetworkX versions or if not available
             partition = nx.community.greedy_modularity_communities(G)
    elif algorithm == "greedy_modularity":
        partition = nx.community.greedy_modularity_communities(G)
    elif algorithm == "label_propagation":
        partition = nx.community.label_propagation_communities(G)
    else:
        raise ValueError(f"Unknown community algorithm: {algorithm}")

    # attribute name to save
    attr_name = "community" # Simplified name for easier usage
    
    # Save to DB
    attr = get_or_create_attribute(
        network_id, attr_name, models.NodeAttribute, db, data_type="string"
    )

    # Delete existing values for this attribute
    delete_attribute_values(network_id, attr.id, models.NodeAttributeValue, db)

    # Prepare data for bulk insert
    node_text_values = []
    
    # Map node_id -> community_id (string)
    # partition is a list of sets. Index can be the community ID.
    for i, community_nodes in enumerate(partition):
        cluster_id = str(i)
        for node_id in community_nodes:
            if node_id in node_map:
                db_node_id = node_map[node_id]
                
                # We need to create a NodeAttributeValue first (or do it efficiently)
                # But our models separate the mapping from the value.
                # Common pattern in centrality.py:
                # 1. Bulk insert NodeAttributeValue mappings
                # 2. Bulk insert value tables (NodeFloatAttributeValue, etc.)
                # However, for text attributes, we might want to just create them.
                # Let's check logic/centrality.py pattern again.
                pass

    # Centrality.py does:
    # 1. Bulk insert NodeAttributeValue
    # 2. Query back to get IDs
    # 3. Bulk insert Value table
    
    # Let's replicate this pattern
    
    # 1. Prepare NodeAttributeValue data
    nav_data = []
    # Temporarily store the value mapping to use in step 3
    node_to_cluster = {}
    
    for i, community_nodes in enumerate(partition):
        cluster_id = str(i)
        for node_id in community_nodes:
            if node_id in node_map:
                db_node_id = node_map[node_id]
                nav_data.append({"node_id": db_node_id, "attribute_id": attr.id})
                node_to_cluster[db_node_id] = cluster_id

    if nav_data:
        db.bulk_insert_mappings(models.NodeAttributeValue, nav_data)
        db.commit()

        # 2. Get IDs back
        all_navs = (
            db.query(models.NodeAttributeValue)
            .filter(
                models.NodeAttributeValue.attribute_id == attr.id,
                models.NodeAttributeValue.node_id.in_(node_to_cluster.keys()),
            )
            .all()
        )
        
        # 3. Insert into NodeTextAttributeValue
        text_vals = []
        for nav in all_navs:
            cluster_id = node_to_cluster.get(nav.node_id)
            if cluster_id is not None:
                text_vals.append({
                    "node_attribute_value_id": nav.id,
                    "text_value": cluster_id
                })
        
        if text_vals:
            db.bulk_insert_mappings(models.NodeTextAttributeValue, text_vals)
        db.commit()
    
    return attr_name
