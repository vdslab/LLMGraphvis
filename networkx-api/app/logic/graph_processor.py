import networkx as nx
from sqlalchemy.orm import Session
from app import models
import io

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


    # Save Nodes
    for node_id, data in G.nodes(data=True):
        db_node = models.Node(
            network_id=network_id,
            node_id=str(node_id),
            label=data.get('label', str(node_id))
        )
        db.add(db_node)
        db.flush() # Get ID for attribute values
        
        # Save Node Attributes
        for key, value in data.items():
            if key == 'label': continue # Already saved
            
            # Determine type and save
            save_node_attribute(network_id, db_node.id, key, value, db)
    
    db.flush() 
    
    # Create node map for edges
    node_map = {n.node_id: n.id for n in db.query(models.Node).filter(models.Node.network_id == network_id).all()}
    
    # Save Edges
    for u, v, data in G.edges(data=True):
        if str(u) in node_map and str(v) in node_map:
            db_edge = models.Edge(
                network_id=network_id,
                edge_id=f"{u}-{v}", # Simple ID generation
                source_node_id=node_map[str(u)],
                target_node_id=node_map[str(v)],
                weight=float(data.get('weight', 1.0))
            )
            db.add(db_edge)
            db.flush() # Get ID
            
            # Save Edge Attributes
            for key, value in data.items():
                if key == 'weight': continue # Already saved
                
                save_edge_attribute(network_id, db_edge.id, key, value, db)
            
    db.commit()

def calculate_layout(network_id: int, layout_name: str, db: Session):
    # Reconstruct graph from DB
    G = nx.Graph()
    nodes = db.query(models.Node).filter(models.Node.network_id == network_id).all()
    
    # Create a map of DB ID to Node ID (string)
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
    
    # Calculate Layout
    if layout_name == "spring":
        pos = nx.spring_layout(G, seed=42) # Seed for reproducibility
    elif layout_name == "circular":
        pos = nx.circular_layout(G)
    elif layout_name == "kamada_kawai":
        pos = nx.kamada_kawai_layout(G)
    elif layout_name == "shell":
        pos = nx.shell_layout(G)
    elif layout_name == "spectral":
        pos = nx.spectral_layout(G)
    else:
        # Fallback to spring
        pos = nx.spring_layout(G, seed=42)
    
    # Save to DB
    attr_x = get_or_create_node_attribute(network_id, f"{layout_name}_x", db)
    attr_y = get_or_create_node_attribute(network_id, f"{layout_name}_y", db)
    
    for node_id, (x, y) in pos.items():
        db_node_id = node_map[node_id]
        save_float_node_attribute_value(db_node_id, attr_x.id, float(x), db)
        save_float_node_attribute_value(db_node_id, attr_y.id, float(y), db)
    
    db.commit()

def calculate_centrality(network_id: int, centrality_type: str, db: Session):
    # Reconstruct graph from DB
    G = nx.Graph()
    nodes = db.query(models.Node).filter(models.Node.network_id == network_id).all()
    
    # Create a map of DB ID to Node ID (string)
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
        
    # Save to DB
    attr_name = f"{centrality_type}_centrality"
    attr = get_or_create_node_attribute(network_id, attr_name, db)
    
    for node_id, value in centrality.items():
        db_node_id = node_map[node_id]
        save_float_node_attribute_value(db_node_id, attr.id, float(value), db)
        
    db.commit()
    return centrality

# Helpers

def save_node_attribute(network_id: int, node_id: int, key: str, value, db: Session):
    attr = get_or_create_node_attribute(network_id, key, db)
    
    if isinstance(value, (int, float)):
        save_float_node_attribute_value(node_id, attr.id, float(value), db)
    else:
        save_text_node_attribute_value(node_id, attr.id, str(value), db)

def save_edge_attribute(network_id: int, edge_id: int, key: str, value, db: Session):
    attr = get_or_create_edge_attribute(network_id, key, db)
    
    if isinstance(value, (int, float)):
        save_float_edge_attribute_value(edge_id, attr.id, float(value), db)
    else:
        save_text_edge_attribute_value(edge_id, attr.id, str(value), db)

def get_or_create_node_attribute(network_id: int, name: str, db: Session):
    attr = db.query(models.NodeAttribute).filter(
        models.NodeAttribute.network_id == network_id,
        models.NodeAttribute.attribute_name == name
    ).first()
    if not attr:
        attr = models.NodeAttribute(network_id=network_id, attribute_name=name)
        db.add(attr)
        db.commit()
        db.refresh(attr)
    return attr

def get_or_create_edge_attribute(network_id: int, name: str, db: Session):
    attr = db.query(models.EdgeAttribute).filter(
        models.EdgeAttribute.network_id == network_id,
        models.EdgeAttribute.attribute_name == name
    ).first()
    if not attr:
        attr = models.EdgeAttribute(network_id=network_id, attribute_name=name)
        db.add(attr)
        db.commit()
        db.refresh(attr)
    return attr

def save_float_node_attribute_value(node_id: int, attribute_id: int, value: float, db: Session):
    val = db.query(models.NodeAttributeValue).filter(
        models.NodeAttributeValue.node_id == node_id,
        models.NodeAttributeValue.attribute_id == attribute_id
    ).first()
    
    if not val:
        val = models.NodeAttributeValue(node_id=node_id, attribute_id=attribute_id)
        db.add(val)
        db.flush()
        float_val = models.NodeFloatAttributeValue(node_attribute_value_id=val.id, float_value=value)
        db.add(float_val)
    else:
        if val.float_value:
            val.float_value.float_value = value
        else:
            # If it was text before, this might fail or we need to handle type change. 
            # For now assume consistent types or overwrite.
            # If it was text, we should probably delete text_value and add float_value.
            if val.text_value:
                db.delete(val.text_value)
            float_val = models.NodeFloatAttributeValue(node_attribute_value_id=val.id, float_value=value)
            db.add(float_val)

def save_text_node_attribute_value(node_id: int, attribute_id: int, value: str, db: Session):
    val = db.query(models.NodeAttributeValue).filter(
        models.NodeAttributeValue.node_id == node_id,
        models.NodeAttributeValue.attribute_id == attribute_id
    ).first()
    
    if not val:
        val = models.NodeAttributeValue(node_id=node_id, attribute_id=attribute_id)
        db.add(val)
        db.flush()
        text_val = models.NodeTextAttributeValue(node_attribute_value_id=val.id, text_value=value)
        db.add(text_val)
    else:
        if val.text_value:
            val.text_value.text_value = value
        else:
            if val.float_value:
                db.delete(val.float_value)
            text_val = models.NodeTextAttributeValue(node_attribute_value_id=val.id, text_value=value)
            db.add(text_val)

def save_float_edge_attribute_value(edge_id: int, attribute_id: int, value: float, db: Session):
    val = db.query(models.EdgeAttributeValue).filter(
        models.EdgeAttributeValue.edge_id == edge_id,
        models.EdgeAttributeValue.attribute_id == attribute_id
    ).first()
    
    if not val:
        val = models.EdgeAttributeValue(edge_id=edge_id, attribute_id=attribute_id)
        db.add(val)
        db.flush()
        float_val = models.EdgeFloatAttributeValue(edge_attribute_value_id=val.id, float_value=value)
        db.add(float_val)
    else:
        if val.float_value:
            val.float_value.float_value = value
        else:
            if val.text_value:
                db.delete(val.text_value)
            float_val = models.EdgeFloatAttributeValue(edge_attribute_value_id=val.id, float_value=value)
            db.add(float_val)

def save_text_edge_attribute_value(edge_id: int, attribute_id: int, value: str, db: Session):
    val = db.query(models.EdgeAttributeValue).filter(
        models.EdgeAttributeValue.edge_id == edge_id,
        models.EdgeAttributeValue.attribute_id == attribute_id
    ).first()
    
    if not val:
        val = models.EdgeAttributeValue(edge_id=edge_id, attribute_id=attribute_id)
        db.add(val)
        db.flush()
        text_val = models.EdgeTextAttributeValue(edge_attribute_value_id=val.id, text_value=value)
        db.add(text_val)
    else:
        if val.text_value:
            val.text_value.text_value = value
        else:
            if val.float_value:
                db.delete(val.float_value)
            text_val = models.EdgeTextAttributeValue(edge_attribute_value_id=val.id, text_value=value)
            db.add(text_val)
