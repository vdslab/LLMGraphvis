from typing import Any, Dict, List

import networkx as nx
from sqlalchemy.orm import Session

from common import models

from .attributes import bulk_save_node_attributes


def calculate_community(network_id: int, algorithm: str, db: Session) -> str:
    """
    Calculates communities for the network and saves them as a categorical node attribute.
    
    Args:
        network_id: The ID of the network.
        algorithm: "louvain", "greedy_modularity", "label_propagation"
        db: Database session.
        
    Returns:
        The name of the attribute created (e.g., "louvain_community").
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
    attr_name = f"{algorithm}_community"
    
    # Prepare data for bulk insert
    # db_node_id -> community_id (string)
    data_map = {}
    
    for i, community_nodes in enumerate(partition):
        cluster_id = str(i)
        for node_id in community_nodes:
            if node_id in node_map:
                db_node_id = node_map[node_id]
                data_map[db_node_id] = cluster_id

    # Save to DB
    bulk_save_node_attributes(network_id, attr_name, "string", data_map, db)
    
    return attr_name
