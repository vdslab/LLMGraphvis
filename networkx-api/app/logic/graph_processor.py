import networkx as nx
from sqlalchemy.orm import Session
from app import models
import io
from typing import Dict, List, Any

def parse_and_save_graphml(network_id: int, graphml_content: str, db: Session):
    # Parse GraphML
    try:
        # NetworkX expects bytes or file-like object
        if isinstance(graphml_content, str):
            graphml_content = graphml_content.encode('utf-8')
        
        G = nx.read_graphml(io.BytesIO(graphml_content))
    except Exception as e:
        raise ValueError(f"Failed to parse GraphML: {e}")

    # Ensure Network exists in DB
    network = db.query(models.Network).filter(models.Network.id == network_id).first()
    if not network:
        network = models.Network(id=network_id, name=f"Network {network_id}")
        db.add(network)
        db.commit()

    # --- 1. Bulk Insert Nodes ---
    nodes_data = []
    for node_id, data in G.nodes(data=True):
        nodes_data.append({
            "network_id": network_id,
            "node_id": str(node_id),
            "label": data.get('label', str(node_id))
        })
    
    if nodes_data:
        db.bulk_insert_mappings(models.Node, nodes_data)
        db.commit()

    # Build Node Map (node_id_str -> db_id)
    # We need this for edges and attributes
    db_nodes = db.query(models.Node).filter(models.Node.network_id == network_id).all()
    node_map = {n.node_id: n.id for n in db_nodes}

    # --- 2. Bulk Insert Edges ---
    edges_data = []
    for u, v, data in G.edges(data=True):
        if str(u) in node_map and str(v) in node_map:
            edges_data.append({
                "network_id": network_id,
                "edge_id": f"{u}-{v}",
                "source_node_id": node_map[str(u)],
                "target_node_id": node_map[str(v)],
                "weight": float(data.get('weight', 1.0))
            })
    
    if edges_data:
        db.bulk_insert_mappings(models.Edge, edges_data)
        db.commit()
    
    # Build Edge Map (edge_id_str -> db_id)
    db_edges = db.query(models.Edge).filter(models.Edge.network_id == network_id).all()
    edge_map = {e.edge_id: e.id for e in db_edges}

    # --- 3. Process Attributes ---
    
    # Collect all unique attribute names
    node_attr_keys = set()
    for _, data in G.nodes(data=True):
        for key in data.keys():
            if key != 'label': node_attr_keys.add(key)

    edge_attr_keys = set()
    for _, _, data in G.edges(data=True):
        for key in data.keys():
            if key != 'weight': edge_attr_keys.add(key)

    # Ensure Attributes Exist
    node_attr_map = _ensure_attributes(network_id, node_attr_keys, models.NodeAttribute, db)
    edge_attr_map = _ensure_attributes(network_id, edge_attr_keys, models.EdgeAttribute, db)

    # --- 4. Bulk Insert Attribute Values ---
    
    # Prepare Node Attribute Values
    node_val_mappings = []
    node_float_vals = []
    node_text_vals = []
    
    # We need to insert NodeAttributeValue first to get IDs, but bulk_insert_mappings doesn't return IDs easily in all drivers.
    # Strategy: Insert NodeAttributeValue, then query them back.
    
    # Prepare data for NodeAttributeValue
    nav_data = []
    for node_id, data in G.nodes(data=True):
        db_node_id = node_map[str(node_id)]
        for key, value in data.items():
            if key == 'label': continue
            if key in node_attr_map:
                nav_data.append({
                    "node_id": db_node_id,
                    "attribute_id": node_attr_map[key]
                })
    
    if nav_data:
        db.bulk_insert_mappings(models.NodeAttributeValue, nav_data)
        db.commit()
        
        # Fetch back to map (node_id, attr_id) -> nav_id
        # This might be heavy if millions of rows, but better than N+1.
        # Optimization: Filter by network's nodes.
        # Since we just inserted them, we can fetch all NAVs for these nodes.
        # But to be safe and simple:
        all_navs = db.query(models.NodeAttributeValue).join(models.Node).filter(models.Node.network_id == network_id).all()
        nav_map = {(nav.node_id, nav.attribute_id): nav.id for nav in all_navs}
        
        # Prepare specific values
        for node_id, data in G.nodes(data=True):
            db_node_id = node_map[str(node_id)]
            for key, value in data.items():
                if key == 'label': continue
                if key in node_attr_map:
                    nav_id = nav_map.get((db_node_id, node_attr_map[key]))
                    if nav_id:
                        if isinstance(value, (int, float)):
                            node_float_vals.append({"node_attribute_value_id": nav_id, "float_value": float(value)})
                        else:
                            node_text_vals.append({"node_attribute_value_id": nav_id, "text_value": str(value)})

        if node_float_vals:
            db.bulk_insert_mappings(models.NodeFloatAttributeValue, node_float_vals)
        if node_text_vals:
            db.bulk_insert_mappings(models.NodeTextAttributeValue, node_text_vals)
        db.commit()

    # Prepare Edge Attribute Values (Similar logic)
    eav_data = []
    for u, v, data in G.edges(data=True):
        edge_id_str = f"{u}-{v}"
        if edge_id_str in edge_map:
            db_edge_id = edge_map[edge_id_str]
            for key, value in data.items():
                if key == 'weight': continue
                if key in edge_attr_map:
                    eav_data.append({
                        "edge_id": db_edge_id,
                        "attribute_id": edge_attr_map[key]
                    })

    if eav_data:
        db.bulk_insert_mappings(models.EdgeAttributeValue, eav_data)
        db.commit()
        
        all_eavs = db.query(models.EdgeAttributeValue).join(models.Edge).filter(models.Edge.network_id == network_id).all()
        eav_map = {(eav.edge_id, eav.attribute_id): eav.id for eav in all_eavs}
        
        edge_float_vals = []
        edge_text_vals = []
        
        for u, v, data in G.edges(data=True):
            edge_id_str = f"{u}-{v}"
            if edge_id_str in edge_map:
                db_edge_id = edge_map[edge_id_str]
                for key, value in data.items():
                    if key == 'weight': continue
                    if key in edge_attr_map:
                        eav_id = eav_map.get((db_edge_id, edge_attr_map[key]))
                        if eav_id:
                            if isinstance(value, (int, float)):
                                edge_float_vals.append({"edge_attribute_value_id": eav_id, "float_value": float(value)})
                            else:
                                edge_text_vals.append({"edge_attribute_value_id": eav_id, "text_value": str(value)})

        if edge_float_vals:
            db.bulk_insert_mappings(models.EdgeFloatAttributeValue, edge_float_vals)
        if edge_text_vals:
            db.bulk_insert_mappings(models.EdgeTextAttributeValue, edge_text_vals)
        db.commit()


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
    if layout_name == "spring":
        # Heuristic for k: 1/sqrt(N) is default. 
        # Increasing it slightly (e.g. 1.5/sqrt(N)) helps spread nodes out.
        import math
        num_nodes = len(G.nodes)
        k = 1.5 / math.sqrt(num_nodes) if num_nodes > 0 else None
        pos = nx.spring_layout(G, k=k, iterations=100, seed=42)
    elif layout_name == "circular":
        pos = nx.circular_layout(G)
    elif layout_name == "kamada_kawai":
        pos = nx.kamada_kawai_layout(G)
    elif layout_name == "shell":
        pos = nx.shell_layout(G)
    elif layout_name == "spectral":
        pos = nx.spectral_layout(G)
    else:
        pos = nx.spring_layout(G, seed=42)
    
    # Save to DB - Bulk Update Strategy
    # 1. Ensure attributes exist
    attr_x = _get_or_create_attribute(network_id, f"{layout_name}_x", models.NodeAttribute, db)
    attr_y = _get_or_create_attribute(network_id, f"{layout_name}_y", models.NodeAttribute, db)
    
    # 2. Delete existing values for these attributes (Clean slate)
    # This avoids complex upsert logic and is safe for re-calculation
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
        # Optimization: We know we just inserted for these attributes
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
    else:
        raise ValueError(f"Unknown centrality type: {centrality_type}")
        
    # Save to DB - Bulk Update Strategy
    attr_name = f"{centrality_type}_centrality"
    attr = _get_or_create_attribute(network_id, attr_name, models.NodeAttribute, db)
    
    # Delete existing
    _delete_attribute_values(network_id, attr.id, models.NodeAttributeValue, db)
    
    # Bulk Insert
    nav_data = []
    for node_id in centrality:
        db_node_id = node_map[node_id]
        nav_data.append({"node_id": db_node_id, "attribute_id": attr.id})
        
    if nav_data:
        db.bulk_insert_mappings(models.NodeAttributeValue, nav_data)
        db.commit()
        
        all_navs = db.query(models.NodeAttributeValue).filter(
            models.NodeAttributeValue.attribute_id == attr.id,
            models.NodeAttributeValue.node_id.in_(node_map.values())
        ).all()
        nav_map = {(nav.node_id, nav.attribute_id): nav.id for nav in all_navs}
        
        float_vals = []
        for node_id, value in centrality.items():
            db_node_id = node_map[node_id]
            nav_id = nav_map.get((db_node_id, attr.id))
            if nav_id:
                float_vals.append({"node_attribute_value_id": nav_id, "float_value": float(value)})
                
        if float_vals:
            db.bulk_insert_mappings(models.NodeFloatAttributeValue, float_vals)
        db.commit()
        
    return centrality

# --- Helpers ---

def _ensure_attributes(network_id: int, keys: set, model_class, db: Session) -> Dict[str, int]:
    """
    Ensure attributes exist for the given keys and return a map of {name: id}.
    """
    if not keys: return {}
    
    # Find existing
    existing = db.query(model_class).filter(
        model_class.network_id == network_id,
        model_class.attribute_name.in_(keys)
    ).all()
    
    attr_map = {attr.attribute_name: attr.id for attr in existing}
    
    # Create missing
    missing = keys - set(attr_map.keys())
    new_attrs = []
    for key in missing:
        new_attrs.append({"network_id": network_id, "attribute_name": key})
    
    if new_attrs:
        db.bulk_insert_mappings(model_class, new_attrs)
        db.commit()
        
        # Fetch all again to get IDs
        all_attrs = db.query(model_class).filter(
            model_class.network_id == network_id,
            model_class.attribute_name.in_(keys)
        ).all()
        attr_map = {attr.attribute_name: attr.id for attr in all_attrs}
        
    return attr_map

def _get_or_create_attribute(network_id: int, name: str, model_class, db: Session):
    attr = db.query(model_class).filter(
        model_class.network_id == network_id,
        model_class.attribute_name == name
    ).first()
    if not attr:
        attr = model_class(network_id=network_id, attribute_name=name)
        db.add(attr)
        db.commit()
        db.refresh(attr)
    return attr

def _delete_attribute_values(network_id: int, attribute_id: int, model_val_class, db: Session):
    """
    Delete all attribute values for a specific attribute in a network.
    """
    # We need to join with Node/Edge to ensure we only delete for this network?
    # Actually, attribute_id is unique to the network (NodeAttribute has network_id).
    # So deleting by attribute_id is safe.
    
    # Note: Cascading deletes might handle child tables (Float/Text values), 
    # but SQLAlchemy bulk delete doesn't always cascade automatically unless configured in DB.
    # Assuming standard ON DELETE CASCADE in DB or manually deleting.
    # Let's try simple delete. If it fails due to FK, we need to delete children first.
    
    # Delete children first (safe approach)
    # Find IDs to delete
    subquery = db.query(model_val_class.id).filter(model_val_class.attribute_id == attribute_id)
    
    # Delete Float/Text values
    if model_val_class == models.NodeAttributeValue:
        db.query(models.NodeFloatAttributeValue).filter(models.NodeFloatAttributeValue.node_attribute_value_id.in_(subquery)).delete(synchronize_session=False)
        db.query(models.NodeTextAttributeValue).filter(models.NodeTextAttributeValue.node_attribute_value_id.in_(subquery)).delete(synchronize_session=False)
    elif model_val_class == models.EdgeAttributeValue:
        db.query(models.EdgeFloatAttributeValue).filter(models.EdgeFloatAttributeValue.edge_attribute_value_id.in_(subquery)).delete(synchronize_session=False)
        db.query(models.EdgeTextAttributeValue).filter(models.EdgeTextAttributeValue.edge_attribute_value_id.in_(subquery)).delete(synchronize_session=False)
        
    # Delete parent values
    db.query(model_val_class).filter(model_val_class.attribute_id == attribute_id).delete(synchronize_session=False)
    db.commit()
