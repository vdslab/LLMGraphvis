import math

import networkx as nx
from sqlalchemy.orm import Session

from common import models

from .attributes import delete_attribute_values, get_or_create_attribute
from app.core.logging import get_logger



def calculate_layout(network_id: int, layout_name: str, db: Session):
    logger = get_logger(__name__)
    
    # Reconstruct graph from DB - OPTIMIZED: Fetch only needed columns
    # Reconstruct graph from DB
    from .utils.graph_builder import build_graph_from_db
    G = build_graph_from_db(network_id, db)

    # Need node_map for saving results (str_id -> db_id)
    nodes_query = db.query(models.Node.id, models.Node.node_id).filter(models.Node.network_id == network_id).all()
    node_map = {row.node_id: row.id for row in nodes_query}

    # Calculate Layout
    # Dynamic parameter adjustment based on network size
    num_nodes = len(G.nodes)

    if layout_name == "spring" or layout_name == "fruchterman_reingold":
        # Heuristic for k: 1/sqrt(N) is default.
        # Increasing it to 2.5/sqrt(N) helps spread nodes out more significantly.
        k = 2.5 / math.sqrt(num_nodes) if num_nodes > 0 else None

        # Dynamic iterations: increased for smaller graphs for better convergence
        iterations = 100 if num_nodes < 500 else 50

        pos = nx.spring_layout(G, k=k, iterations=iterations, seed=42)

    elif layout_name == "forceatlas2":
        # Use native NetworkX implementation
        try:
            # Parameters tuned for typical visualization needs
            # iter=500 for good convergence
            # gravity=0.05 is quite weak, standard is 1.0.
            # The user complained about previous one being bad.
            # Let's use defaults but slightly more iterations.
            pos = nx.forceatlas2_layout(G, max_iter=700, scaling_ratio=100.0, seed=42)
        except AttributeError:
            # Fallback if somehow not available (though we verified it is)
            # or if older version in prod? (Unlikely given verification)
            pos = nx.spring_layout(G, seed=42)

    elif layout_name == "circular" or layout_name == "circle":
        pos = nx.circular_layout(G)

    elif layout_name == "kamada_kawai":
        pos = nx.kamada_kawai_layout(G)

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
