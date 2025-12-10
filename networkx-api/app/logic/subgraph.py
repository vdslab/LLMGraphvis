import networkx as nx
from sqlalchemy.orm import Session
from app import models
from typing import List, Dict, Any
from .layout import calculate_layout

def _copy_values(db: Session, model_val, model_float, model_text, id_map, attr_id_map, parent_col, val_parent_col):
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
    # old_val_id_map = {} # old_val_id -> index in new_vals_data (to track for float/text)
    
    # We need to map old val ID to new parent and attr ID to find it later
    # But we insert in bulk.
    
    for i, val in enumerate(old_vals):
        new_pk = id_map.get(getattr(val, parent_col))
        new_attr_id = attr_id_map.get(val.attribute_id)
        if new_pk and new_attr_id:
            new_vals_data.append({
                parent_col: new_pk,
                "attribute_id": new_attr_id
            })
            # old_val_id_map[val.id] = i 
    
    if new_vals_data:
        db.bulk_insert_mappings(model_val, new_vals_data)
        db.commit()
        
        # Fetch back to get IDs
        # We need to match what we just inserted.
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

def create_subgraph_from_nodes(source_network_id: int, node_ids: List[str], db: Session, suffix: str = "Subgraph") -> Dict[str, Any]:
    """
    Creates a new network as a subgraph containing the specified nodes.
    """
    # 1. Get Source Network
    source_network = db.query(models.Network).filter(models.Network.id == source_network_id).first()
    if not source_network:
        raise ValueError(f"Source network {source_network_id} not found")

    # 2. Determine Network Name
    if suffix == "Subgraph":
        # Create a deterministic name for ad-hoc subgraphs based on node IDs
        # Sort to ensure order doesn't matter
        sorted_ids = sorted(node_ids)
        # Check length to avoid massive names? For now just join.
        # If too long, maybe we truncate? Let's keep it simple as agreed.
        nodes_str = ",".join(sorted_ids)
        if len(nodes_str) > 50:
             nodes_str = nodes_str[:47] + "..."
        target_name = f"Subgraph ({nodes_str})"
    else:
        target_name = suffix

    # 3. Check for Existing Subgraph (Reuse)
    existing_network = db.query(models.Network).filter(
        models.Network.parent_network_id == source_network_id,
        models.Network.name == target_name
    ).first()

    if existing_network:
        return {"new_network_id": existing_network.id, "name": existing_network.name}

    # 4. Create New Network
    new_network = models.Network(
        name=target_name, 
        parent_network_id=source_network_id,
        graphml_content='<?xml version="1.0" encoding="UTF-8"?><graphml xmlns="http://graphml.graphdrawing.org/xmlns"></graphml>'
    )
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
    # node_str_map = {} # node_id_str -> new_pk
    
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
        source_node_map = {n.node_id: n.id for n in source_nodes}
        for new_node in new_nodes:
            old_pk = source_node_map.get(new_node.node_id)
            if old_pk:
                node_map[old_pk] = new_node.id
            # node_str_map[new_node.node_id] = new_node.id

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
    # Copy Node Attribute Values
    _copy_values(db, models.NodeAttributeValue, models.NodeFloatAttributeValue, models.NodeTextAttributeValue, 
                node_map, node_attr_id_map, "node_id", "node_attribute_value_id")
                
    # Copy Edge Attribute Values
    _copy_values(db, models.EdgeAttributeValue, models.EdgeFloatAttributeValue, models.EdgeTextAttributeValue, 
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
