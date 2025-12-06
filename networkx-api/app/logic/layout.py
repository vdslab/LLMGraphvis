import networkx as nx
import math
from sqlalchemy.orm import Session
from app import models
from .attributes import _get_or_create_attribute, _delete_attribute_values

def calculate_layout(network_id: int, layout_name: str, db: Session):
    # Reconstruct graph from DB
    G = nx.Graph()
    nodes = db.query(models.Node).filter(models.Node.network_id == network_id).all()
    
    id_map = {n.id: n.node_id for n in nodes} # db_id -> str_id
    node_map = {n.node_id: n.id for n in nodes} # str_id -> db_id
    
    for n in nodes:
        G.add_node(n.node_id)
        
    edges = db.query(models.Edge).filter(models.Edge.network_id == network_id).all()
    for e in edges:
        u = id_map.get(e.source_node_id)
        v = id_map.get(e.target_node_id)
        if u and v:
            G.add_edge(u, v)
    
    # Calculate Layout
    # Calculate Layout
    if layout_name == "spring" or layout_name == "fruchterman_reingold":
        # Heuristic for k: 1/sqrt(N) is default. 
        # Increasing it to 2.0/sqrt(N) helps spread nodes out more significantly.
        num_nodes = len(G.nodes)
        k = 2.0 / math.sqrt(num_nodes) if num_nodes > 0 else None
        # Increased iterations for better convergence
        pos = nx.spring_layout(G, k=k, iterations=1000, seed=42)
        
    elif layout_name == "forceatlas2":
        # ForceAtlas2 - requires verify if available, but confirmed in environment
        try:
            # Attempt to use the networkx wrapper if available
            if hasattr(nx, 'forceatlas2_layout'):
                 pos = nx.forceatlas2_layout(G, metric="euclidean", seed=42)
            else:
                 # Fallback to spring if not actually available despite checks
                 print("ForceAtlas2 not found, falling back to spring")
                 pos = nx.spring_layout(G, seed=42)
        except Exception as e:
            print(f"Error checking ForceAtlas2: {e}, falling back to spring")
            pos = nx.spring_layout(G, seed=42)

    elif layout_name == "circular":
        pos = nx.circular_layout(G)
        
    elif layout_name == "kamada_kawai":
        pos = nx.kamada_kawai_layout(G)
        
    elif layout_name == "shell":
        pos = nx.shell_layout(G)
        
    elif layout_name == "spectral":
        pos = nx.spectral_layout(G)
        
    elif layout_name == "spiral":
        pos = nx.spiral_layout(G)
        
    else:
        # Default fallback
        pos = nx.spring_layout(G, seed=42)
    
    # Save to DB - Bulk Update Strategy
    # 1. Ensure attributes exist
    attr_x = _get_or_create_attribute(network_id, f"{layout_name}_x", models.NodeAttribute, db, data_type="float")
    attr_y = _get_or_create_attribute(network_id, f"{layout_name}_y", models.NodeAttribute, db, data_type="float")
    
    # 2. Delete existing values for these attributes (Clean slate)
    _delete_attribute_values(network_id, attr_x.id, models.NodeAttributeValue, db)
    _delete_attribute_values(network_id, attr_y.id, models.NodeAttributeValue, db)
    
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
        all_navs = db.query(models.NodeAttributeValue).filter(
            models.NodeAttributeValue.attribute_id.in_([attr_x.id, attr_y.id]),
            models.NodeAttributeValue.node_id.in_(node_map.values())
        ).all()
        
        nav_map = {(nav.node_id, nav.attribute_id): nav.id for nav in all_navs}
        
        float_vals = []
        for node_id, (x, y) in pos.items():
            db_node_id = node_map[node_id]
            
            nav_x_id = nav_map.get((db_node_id, attr_x.id))
            if nav_x_id:
                float_vals.append({"node_attribute_value_id": nav_x_id, "float_value": float(x)})
                
            nav_y_id = nav_map.get((db_node_id, attr_y.id))
            if nav_y_id:
                float_vals.append({"node_attribute_value_id": nav_y_id, "float_value": float(y)})
        
        if float_vals:
            db.bulk_insert_mappings(models.NodeFloatAttributeValue, float_vals)
        db.commit()
