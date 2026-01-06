import math

import networkx as nx
from sqlalchemy.orm import Session

from common import models

from .attributes import delete_attribute_values, get_or_create_attribute
from app.core.logging import get_logger



def determine_layout_params(G, layout_name: str):
    """
    Dynamically determine layout parameters based on graph size (scale).
    Prioritizes 'Beautiful' high-quality layouts over speed.
    """
    num_nodes = len(G.nodes)
    params = {}
    
    # Scale Categories
    is_small = num_nodes < 500
    is_medium = 500 <= num_nodes < 2000
    is_large = num_nodes >= 2000

    if layout_name == "spring" or layout_name == "fruchterman_reingold":
        # k: Optimal distance between nodes. 
        # Increase slightly (2.0/sqrt(N)) to reduce overlap.
        k = 2.0 / math.sqrt(num_nodes) if num_nodes > 0 else None
        
        if is_small:
            # High iterations, strict threshold for beautiful convergence
            iterations = 1000
            threshold = 1e-6
        elif is_medium:
            iterations = 500
            threshold = 1e-5
        else: # Large
            iterations = 200
            threshold = 1e-4

        params = {
            "k": k,
            "iterations": iterations,
            "threshold": threshold,
            "seed": 42
        }

    elif layout_name == "forceatlas2":
        # Native NetworkX ForceAtlas2 optimization
        # Dynamic iterations based on graph size
        # Formula: max_iter = max(1000, min(5000, num_nodes * 2))
        max_iter = max(1000, min(5000, num_nodes * 2))

        # Dynamic Scaling Ratio for Overlap Reduction
        # Use Average Degree as a proxy for local density clumping
        num_edges = len(G.edges)
        avg_degree = (2 * num_edges) / num_nodes if num_nodes > 0 else 0
        
        # If avg_degree is high, nodes are pulled tighter. We increase scaling to compensate.
        # Base scaling is 2.0. Cap at 10.0.
        # Formula: scaling_ratio = max(2.0, min(10.0, avg_degree * 0.5))
        scaling_ratio = max(2.0, min(10.0, avg_degree * 0.5))

        # Force Constants
        params = {
            "max_iter": max_iter,
            "scaling_ratio": scaling_ratio, 
            "gravity": 1.0,        # Standard gravity
            "jitter_tolerance": 1.0, # Standard tolerance for better convergence
            "seed": 42
        }

    elif layout_name == "kamada_kawai":
        # O(N^2) but excellent global structure
        params = {"scale": 1.0} # Standard
        
    return params


def calculate_layout(network_id: int, layout_name: str, db: Session):
    logger = get_logger(__name__)
    
    # Reconstruct graph from DB
    from .utils.graph_builder import build_graph_from_db
    G = build_graph_from_db(network_id, db)

    # Need node_map for saving results (str_id -> db_id)
    nodes_query = db.query(models.Node.id, models.Node.node_id).filter(models.Node.network_id == network_id).all()
    node_map = {row.node_id: row.id for row in nodes_query}

    # Normalize layout name
    if layout_name in ["forceatlas2_layout", "force-directed", "force_directed"]:
        layout_name = "forceatlas2"
        
    num_nodes = len(G.nodes)
    params = determine_layout_params(G, layout_name)
    
    pos = None

    if layout_name == "spring" or layout_name == "fruchterman_reingold":
        pos = nx.spring_layout(G, **params)

    elif layout_name == "forceatlas2":
        # Use native NetworkX implementation
        # Note: Checked availability in NetworkX 3.6+
        pos = nx.forceatlas2_layout(G, **params)

    elif layout_name == "circular" or layout_name == "circle":
        pos = nx.circular_layout(G)

    elif layout_name == "kamada_kawai":
        pos = nx.kamada_kawai_layout(G, **params)

    elif layout_name == "shell":
        pos = nx.shell_layout(G)

    elif layout_name == "spectral":
        pos = nx.spectral_layout(G)

    elif layout_name == "spiral":
        pos = nx.spiral_layout(G)

    elif layout_name == "random":
        pos = nx.random_layout(G, seed=42)

    else:
        raise ValueError(f"Unknown layout algorithm: {layout_name}")

    # Save to DB - Bulk Update Strategy
    # We save two attributes: {layout_name}_x and {layout_name}_y
    
    # Prepare data maps
    data_map_x = {}
    data_map_y = {}

    for node_id, (x, y) in pos.items():
        if node_id in node_map:
            db_node_id = node_map[node_id]
            data_map_x[db_node_id] = float(x)
            data_map_y[db_node_id] = float(y)

    from .attributes import bulk_save_node_attributes
    
    # Save X
    bulk_save_node_attributes(
        network_id, f"{layout_name}_x", "float", data_map_x, db
    )
    
    # Save Y
    bulk_save_node_attributes(
        network_id, f"{layout_name}_y", "float", data_map_y, db
    )

    # 4. Update Network Record with last layout name
    from sqlalchemy import text

    try:
        db.execute(
            text("UPDATE networks SET last_layout_name = :algo WHERE id = :nid"),
            {"algo": layout_name, "nid": network_id},
        )
        db.commit()
    except Exception as e:
        db.rollback()
        print(f"Warning: Failed to update last_layout_name: {e}")
        # non-critical, proceed
