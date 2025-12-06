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
    
    final_network_id = network_id
    
    if not network:
        # Should typically exist if called from Backend, but if not, create it
        network = models.Network(id=network_id, name=f"Network {network_id}")
        db.add(network)
        db.commit()
    else:
        # Check if network already has data (nodes)
        existing_node_count = db.query(models.Node).filter(models.Node.network_id == network_id).count()
        if existing_node_count > 0:
            # COLLISION: Network exists and has data.
            # Create a NEW network instead of overwriting.
            import datetime
            new_network = models.Network(
                name=f"{network.name} (Uploaded {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')})"
            )
            db.add(new_network)
            db.commit()
            db.refresh(new_network)
            final_network_id = new_network.id
            
            # Note: We do NOT delete the old data. We just switch to a new ID.

    network_id = final_network_id # Use the confirmed ID for all subsequent operations

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
    
    # Infer Attribute Types
    node_attr_types = {}
    for _, data in G.nodes(data=True):
        for key, val in data.items():
            if key == 'label': continue
            if key not in node_attr_types:
                node_attr_types[key] = "float" # Assume float initially
            
            if node_attr_types[key] == "float":
                if not isinstance(val, (int, float)) or isinstance(val, bool):
                     node_attr_types[key] = "string"

    edge_attr_types = {}
    for _, _, data in G.edges(data=True):
        for key, val in data.items():
            if key == 'weight': continue
            if key not in edge_attr_types:
                edge_attr_types[key] = "float"
            
            if edge_attr_types[key] == "float":
                if not isinstance(val, (int, float)) or isinstance(val, bool):
                     edge_attr_types[key] = "string"

    # Ensure Attributes Exist
    node_attr_map = _ensure_attributes(network_id, node_attr_types, models.NodeAttribute, db)
    edge_attr_map = _ensure_attributes(network_id, edge_attr_types, models.EdgeAttribute, db)

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
    
    return final_network_id


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
    # 1. Ensure attributes exist
    attr_x = _get_or_create_attribute(network_id, f"{layout_name}_x", models.NodeAttribute, db, data_type="float")
    attr_y = _get_or_create_attribute(network_id, f"{layout_name}_y", models.NodeAttribute, db, data_type="float")
    
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
    attr = _get_or_create_attribute(network_id, attr_name, models.NodeAttribute, db, data_type="float")
    
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

def _clear_network_data(network_id: int, db: Session):
    """
    Clears all graph data (nodes, edges, attribute values) for a network.
    Does NOT delete the Network record itself or Attribute Definitions (to preserve schema if reused).
    """
    # 1. Delete Edge Attribute Values (and their children)
    # Get all EdgeAttributeValue IDs for this network
    eav_ids = [r[0] for r in db.query(models.EdgeAttributeValue.id).join(models.Edge).filter(models.Edge.network_id == network_id).all()]
    
    if eav_ids:
        db.query(models.EdgeFloatAttributeValue).filter(models.EdgeFloatAttributeValue.edge_attribute_value_id.in_(eav_ids)).delete(synchronize_session=False)
        db.query(models.EdgeTextAttributeValue).filter(models.EdgeTextAttributeValue.edge_attribute_value_id.in_(eav_ids)).delete(synchronize_session=False)
        db.query(models.EdgeAttributeValue).filter(models.EdgeAttributeValue.id.in_(eav_ids)).delete(synchronize_session=False)

    # 2. Delete Node Attribute Values (and their children)
    # Get all NodeAttributeValue IDs
    nav_ids = [r[0] for r in db.query(models.NodeAttributeValue.id).join(models.Node).filter(models.Node.network_id == network_id).all()]
    
    if nav_ids:
        db.query(models.NodeFloatAttributeValue).filter(models.NodeFloatAttributeValue.node_attribute_value_id.in_(nav_ids)).delete(synchronize_session=False)
        db.query(models.NodeTextAttributeValue).filter(models.NodeTextAttributeValue.node_attribute_value_id.in_(nav_ids)).delete(synchronize_session=False)
        db.query(models.NodeAttributeValue).filter(models.NodeAttributeValue.id.in_(nav_ids)).delete(synchronize_session=False)

    # 3. Delete Edges
    db.query(models.Edge).filter(models.Edge.network_id == network_id).delete(synchronize_session=False)

    # 4. Delete Nodes
    db.query(models.Node).filter(models.Node.network_id == network_id).delete(synchronize_session=False)
    
    db.commit()

def _ensure_attributes(network_id: int, attr_types: Dict[str, str], model_class, db: Session) -> Dict[str, int]:
    """
    Ensure attributes exist for the given keys and return a map of {name: id}.
    attr_types: Dict mapping attribute name to data_type ("float", "string", etc.)
    """
    keys = set(attr_types.keys())
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
        new_attrs.append({
            "network_id": network_id, 
            "attribute_name": key,
            "data_type": attr_types.get(key, "string")
        })
    
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

def _get_or_create_attribute(network_id: int, name: str, model_class, db: Session, data_type: str = "string"):
    attr = db.query(model_class).filter(
        model_class.network_id == network_id,
        model_class.attribute_name == name
    ).first()
    if not attr:
        attr = model_class(network_id=network_id, attribute_name=name, data_type=data_type)
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

# --- Subgraph Operations ---

def create_subgraph_from_nodes(source_network_id: int, node_ids: List[str], db: Session, suffix: str = "Subgraph") -> Dict[str, Any]:
    """
    Creates a new network as a subgraph containing the specified nodes.
    """
    # 1. Get Source Network
    source_network = db.query(models.Network).filter(models.Network.id == source_network_id).first()
    if not source_network:
        raise ValueError(f"Source network {source_network_id} not found")

    # 2. Create New Network
    # Generate a new ID (simple max+1 or random? DB autoincrement is best but we need ID now)
    # We are inserting with explicit ID in parse_and_save_graphml, but here we let DB handle it?
    # Wait, parse_and_save_graphml takes network_id. The Backend generates it.
    # Here, we are inside NetworkXAPI. We should probably generate an ID or let DB do it.
    # If we let DB do it, we need to return it.
    new_network = models.Network(name=f"{source_network.name} - {suffix}", parent_network_id=source_network_id)
    db.add(new_network)
    db.commit()
    db.refresh(new_network)
    new_network_id = new_network.id

    # 3. Copy Nodes
    source_nodes = db.query(models.Node).filter(
        models.Node.network_id == source_network_id,
        models.Node.node_id.in_(node_ids)
    ).all()
    
    node_map = {} # old_pk -> new_pk
    node_str_map = {} # node_id_str -> new_pk
    
    new_nodes_data = []
    for node in source_nodes:
        new_nodes_data.append({
            "network_id": new_network_id,
            "node_id": node.node_id,
            "label": node.label
        })
    
    if new_nodes_data:
        db.bulk_insert_mappings(models.Node, new_nodes_data)
        db.commit()
        
        # Build maps
        new_nodes = db.query(models.Node).filter(models.Node.network_id == new_network_id).all()
        # We need to map old source nodes to new nodes.
        # Since node_id string is unique per network, we can match by that.
        source_node_map = {n.node_id: n.id for n in source_nodes}
        for new_node in new_nodes:
            old_pk = source_node_map.get(new_node.node_id)
            if old_pk:
                node_map[old_pk] = new_node.id
            node_str_map[new_node.node_id] = new_node.id

    # 4. Copy Edges (Induced Subgraph)
    # Edges where BOTH source and target are in the new node set
    source_edges = db.query(models.Edge).filter(
        models.Edge.network_id == source_network_id,
        models.Edge.source_node_id.in_(node_map.keys()),
        models.Edge.target_node_id.in_(node_map.keys())
    ).all()
    
    edge_map = {} # old_pk -> new_pk
    new_edges_data = []
    for edge in source_edges:
        new_edges_data.append({
            "network_id": new_network_id,
            "edge_id": edge.edge_id,
            "source_node_id": node_map[edge.source_node_id],
            "target_node_id": node_map[edge.target_node_id],
            "weight": edge.weight
        })
        
    if new_edges_data:
        db.bulk_insert_mappings(models.Edge, new_edges_data)
        db.commit()
        
        # Build edge map for attributes
        new_edges = db.query(models.Edge).filter(models.Edge.network_id == new_network_id).all()
        source_edge_map = {e.edge_id: e.id for e in source_edges}
        for new_edge in new_edges:
            old_pk = source_edge_map.get(new_edge.edge_id)
            if old_pk:
                edge_map[old_pk] = new_edge.id

    # 5. Copy Attributes Definitions
    # Copy Node Attributes
    source_node_attrs = db.query(models.NodeAttribute).filter(models.NodeAttribute.network_id == source_network_id).all()
    node_attr_id_map = {} # old_attr_id -> new_attr_id
    
    new_node_attrs_data = []
    for attr in source_node_attrs:
        new_node_attrs_data.append({
            "network_id": new_network_id,
            "attribute_name": attr.attribute_name,
            "data_type": attr.data_type
        })
        
    if new_node_attrs_data:
        db.bulk_insert_mappings(models.NodeAttribute, new_node_attrs_data)
        db.commit()
        
        new_attrs = db.query(models.NodeAttribute).filter(models.NodeAttribute.network_id == new_network_id).all()
        source_attr_map = {a.attribute_name: a.id for a in source_node_attrs}
        for new_attr in new_attrs:
            old_id = source_attr_map.get(new_attr.attribute_name)
            if old_id:
                node_attr_id_map[old_id] = new_attr.id

    # Copy Edge Attributes
    source_edge_attrs = db.query(models.EdgeAttribute).filter(models.EdgeAttribute.network_id == source_network_id).all()
    edge_attr_id_map = {} # old_attr_id -> new_attr_id
    
    new_edge_attrs_data = []
    for attr in source_edge_attrs:
        new_edge_attrs_data.append({
            "network_id": new_network_id,
            "attribute_name": attr.attribute_name,
            "data_type": attr.data_type
        })
        
    if new_edge_attrs_data:
        db.bulk_insert_mappings(models.EdgeAttribute, new_edge_attrs_data)
        db.commit()
        
        new_attrs = db.query(models.EdgeAttribute).filter(models.EdgeAttribute.network_id == new_network_id).all()
        source_attr_map = {a.attribute_name: a.id for a in source_edge_attrs}
        for new_attr in new_attrs:
            old_id = source_attr_map.get(new_attr.attribute_name)
            if old_id:
                edge_attr_id_map[old_id] = new_attr.id

    # 6. Copy Attribute Values
    # This is the tricky part. We need to copy values for the nodes/edges we copied.
    
    # Helper to copy values
    def copy_values(model_val, model_float, model_text, id_map, attr_id_map, parent_col, val_parent_col):
        # Fetch old values
        old_ids = list(id_map.keys())
        old_attr_ids = list(attr_id_map.keys())
        
        if not old_ids or not old_attr_ids: return

        # Chunking might be needed for large datasets, but assuming reasonable size for now
        old_vals = db.query(model_val).filter(
            getattr(model_val, parent_col).in_(old_ids),
            model_val.attribute_id.in_(old_attr_ids)
        ).all()
        
        new_vals_data = []
        old_val_id_map = {} # old_val_id -> index in new_vals_data (to track for float/text)
        
        for i, val in enumerate(old_vals):
            new_pk = id_map.get(getattr(val, parent_col))
            new_attr_id = attr_id_map.get(val.attribute_id)
            if new_pk and new_attr_id:
                new_vals_data.append({
                    parent_col: new_pk,
                    "attribute_id": new_attr_id
                })
                old_val_id_map[val.id] = i # We can't use ID yet.
        
        if new_vals_data:
            db.bulk_insert_mappings(model_val, new_vals_data)
            db.commit()
            
            # Fetch back to get IDs
            # We need to match what we just inserted.
            # Strategy: Fetch all for new network's nodes/edges?
            # Or just fetch all for the new nodes/edges and attributes.
            new_ids = list(id_map.values())
            new_attr_ids = list(attr_id_map.values())
            
            inserted_vals = db.query(model_val).filter(
                getattr(model_val, parent_col).in_(new_ids),
                model_val.attribute_id.in_(new_attr_ids)
            ).all()
            
            # Map (parent_id, attr_id) -> new_val_id
            val_map = {(getattr(v, parent_col), v.attribute_id): v.id for v in inserted_vals}
            
            # Now copy Float/Text values
            new_float_data = []
            new_text_data = []
            
            # We need to iterate old_vals again and find corresponding new_val_id
            # Also fetch old float/text values
            old_val_ids = [v.id for v in old_vals]
            
            old_floats = db.query(model_float).filter(getattr(model_float, val_parent_col).in_(old_val_ids)).all()
            old_texts = db.query(model_text).filter(getattr(model_text, val_parent_col).in_(old_val_ids)).all()
            
            float_map = {getattr(f, val_parent_col): f.float_value for f in old_floats}
            text_map = {getattr(t, val_parent_col): t.text_value for t in old_texts}
            
            for val in old_vals:
                new_pk = id_map.get(getattr(val, parent_col))
                new_attr_id = attr_id_map.get(val.attribute_id)
                if new_pk and new_attr_id:
                    new_val_id = val_map.get((new_pk, new_attr_id))
                    if new_val_id:
                        if val.id in float_map:
                            new_float_data.append({val_parent_col: new_val_id, "float_value": float_map[val.id]})
                        if val.id in text_map:
                            new_text_data.append({val_parent_col: new_val_id, "text_value": text_map[val.id]})
            
            if new_float_data:
                db.bulk_insert_mappings(model_float, new_float_data)
            if new_text_data:
                db.bulk_insert_mappings(model_text, new_text_data)
            db.commit()

    # Copy Node Attribute Values
    copy_values(models.NodeAttributeValue, models.NodeFloatAttributeValue, models.NodeTextAttributeValue, 
                node_map, node_attr_id_map, "node_id", "node_attribute_value_id")
                
    # Copy Edge Attribute Values
    copy_values(models.EdgeAttributeValue, models.EdgeFloatAttributeValue, models.EdgeTextAttributeValue, 
                edge_map, edge_attr_id_map, "edge_id", "edge_attribute_value_id")

    # 7. Calculate Initial Layout
    calculate_layout(new_network_id, "spring", db)

    return {"new_network_id": new_network_id, "name": new_network.name}



def _resolve_node_id(G, node_id_input: str) -> str:
    """
    Tries to resolve the node_id_input to a node in G.
    Handles cases where LLM adds 'Node ' prefix or similar.
    """
    if node_id_input in G:
        return node_id_input
    
    # Try stripping "node " or "Node " (case insensitive)
    lower_input = node_id_input.lower()
    if lower_input.startswith("node"):
        # Remove "node" and any following whitespace
        cleaned = lower_input.replace("node", "").strip()
        if cleaned in G:
            return cleaned
            
    # Try stripping whitespace
    stripped = node_id_input.strip()
    if stripped in G:
        return stripped
        
    return node_id_input

def create_ego_network(source_network_id: int, center_node_id: str, radius: int, db: Session) -> Dict[str, Any]:
    # Reconstruct graph structure to run ego_graph
    G = nx.Graph()
    # We only need structure, not attributes, for ego_graph (unless radius depends on weight?)
    # Assuming unweighted radius (hops).
    
    # Fetch edges
    edges = db.query(models.Edge).filter(models.Edge.network_id == source_network_id).all()
    nodes = db.query(models.Node).filter(models.Node.network_id == source_network_id).all()
    
    id_map = {n.id: n.node_id for n in nodes}
    
    for n in nodes:
        G.add_node(n.node_id)
    
    for e in edges:
        u = id_map.get(e.source_node_id)
        v = id_map.get(e.target_node_id)
        if u and v:
            G.add_edge(u, v)
            
    # Resolve node ID
    center_node_id = _resolve_node_id(G, center_node_id)
            
    if center_node_id not in G:
        raise ValueError(f"Node {center_node_id} not found in network")
        
    ego_G = nx.ego_graph(G, center_node_id, radius=radius)
    node_ids = list(ego_G.nodes())
    
    return create_subgraph_from_nodes(source_network_id, node_ids, db, suffix=f"Ego {center_node_id} (r={radius})")

def create_path_subgraph(source_network_id: int, source_node_id: str, target_node_id: str, db: Session) -> Dict[str, Any]:
    G = nx.Graph()
    edges = db.query(models.Edge).filter(models.Edge.network_id == source_network_id).all()
    nodes = db.query(models.Node).filter(models.Node.network_id == source_network_id).all()
    id_map = {n.id: n.node_id for n in nodes}
    for n in nodes:
        G.add_node(n.node_id)
    for e in edges:
        u = id_map.get(e.source_node_id)
        v = id_map.get(e.target_node_id)
        if u and v:
            G.add_edge(u, v)
            
    # Resolve node IDs
    source_node_id = _resolve_node_id(G, source_node_id)
    target_node_id = _resolve_node_id(G, target_node_id)
            
    try:
        path_nodes = nx.shortest_path(G, source=source_node_id, target=target_node_id)
    except nx.NetworkXNoPath:
        raise ValueError(f"No path between {source_node_id} and {target_node_id}")
        
    return create_subgraph_from_nodes(source_network_id, path_nodes, db, suffix=f"Path {source_node_id}->{target_node_id}")

def create_k_core_subgraph(source_network_id: int, k: int, db: Session) -> Dict[str, Any]:
    G = nx.Graph()
    edges = db.query(models.Edge).filter(models.Edge.network_id == source_network_id).all()
    nodes = db.query(models.Node).filter(models.Node.network_id == source_network_id).all()
    id_map = {n.id: n.node_id for n in nodes}
    for n in nodes:
        G.add_node(n.node_id)
    for e in edges:
        u = id_map.get(e.source_node_id)
        v = id_map.get(e.target_node_id)
        if u and v:
            G.add_edge(u, v)
            
    # Remove self-loops as k-core is defined for simple graphs usually
    G.remove_edges_from(nx.selfloop_edges(G))
    
    k_core_G = nx.k_core(G, k=k)
    node_ids = list(k_core_G.nodes())
    
    if not node_ids:
        raise ValueError(f"No k-core found for k={k}")
        
    return create_subgraph_from_nodes(source_network_id, node_ids, db, suffix=f"K-Core (k={k})")

def create_largest_component_subgraph(source_network_id: int, db: Session) -> Dict[str, Any]:
    G = nx.Graph()
    edges = db.query(models.Edge).filter(models.Edge.network_id == source_network_id).all()
    nodes = db.query(models.Node).filter(models.Node.network_id == source_network_id).all()
    id_map = {n.id: n.node_id for n in nodes}
    for n in nodes:
        G.add_node(n.node_id)
    for e in edges:
        u = id_map.get(e.source_node_id)
        v = id_map.get(e.target_node_id)
        if u and v:
            G.add_edge(u, v)
            
    components = list(nx.connected_components(G))
    if not components:
        raise ValueError("Network is empty")
        
    largest_component = max(components, key=len)
    node_ids = list(largest_component)
    
    return create_subgraph_from_nodes(source_network_id, node_ids, db, suffix="Largest Component")

def get_top_nodes(network_id: int, metric: str, k: int, db: Session) -> List[Dict[str, Any]]:
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
