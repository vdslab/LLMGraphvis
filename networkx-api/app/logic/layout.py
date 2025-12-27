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
        # Native NetworkX ForceAtlas2
        # Tuning for quality
        
        # Iterations
        if is_small:
            max_iter = 2000 # Let it settle completely
        elif is_medium:
            max_iter = 1000
        else: # Large
            max_iter = 500 # Practical limit for interactive response

        # Force Constants
        # gravity: Attracts to center. Too high = collapse, Too low = drift.
        # scaling_ratio: Repulsion strength. High = more spread.
        params = {
            "max_iter": max_iter,
            "scaling_ratio": 80.0, # Standard scaling
            "gravity": 0.03,      # Gentle gravity to keep shape
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
    # 1. Ensure attributes exist
    attr_x = get_or_create_attribute(
        network_id, f"{layout_name}_x", models.NodeAttribute, db, data_type="float"
    )
    attr_y = get_or_create_attribute(
        network_id, f"{layout_name}_y", models.NodeAttribute, db, data_type="float"
    )
    print(f"DEBUG: layout.calculate_layout created attributes {attr_x.id}, {attr_y.id} for network {network_id}")


    # 2. Delete existing values for these attributes (Clean slate)
    delete_attribute_values(network_id, attr_x.id, models.NodeAttributeValue, db, commit=False)
    delete_attribute_values(network_id, attr_y.id, models.NodeAttributeValue, db, commit=False)

    # 3. Bulk Insert New Values
    nav_data = []
    for node_id in pos:
        db_node_id = node_map[node_id]
        nav_data.append({"node_id": db_node_id, "attribute_id": attr_x.id})
        nav_data.append({"node_id": db_node_id, "attribute_id": attr_y.id})

    if nav_data:
        db.bulk_insert_mappings(models.NodeAttributeValue, nav_data)
        db.commit()

        # Fetch back IDs
        all_navs = (
            db.query(models.NodeAttributeValue)
            .filter(
                models.NodeAttributeValue.attribute_id.in_([attr_x.id, attr_y.id]),
                models.NodeAttributeValue.node_id.in_(node_map.values()),
            )
            .all()
        )

        nav_map = {(nav.node_id, nav.attribute_id): nav.id for nav in all_navs}

        float_vals = []
        for node_id, (x, y) in pos.items():
            db_node_id = node_map[node_id]

            nav_x_id = nav_map.get((db_node_id, attr_x.id))
            if nav_x_id:
                float_vals.append(
                    {"node_attribute_value_id": nav_x_id, "float_value": float(x)}
                )

            nav_y_id = nav_map.get((db_node_id, attr_y.id))
            if nav_y_id:
                float_vals.append(
                    {"node_attribute_value_id": nav_y_id, "float_value": float(y)}
                )

        if float_vals:
            db.bulk_insert_mappings(models.NodeFloatAttributeValue, float_vals)
        db.commit()

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
