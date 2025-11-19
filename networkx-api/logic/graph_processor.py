import networkx as nx
from sqlalchemy.orm import Session
import models
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

    # Save Nodes
    for node_id, data in G.nodes(data=True):
        db_node = models.Node(
            network_id=network_id,
            node_id=str(node_id),
            label=data.get('label', str(node_id))
        )
        db.add(db_node)
        # TODO: Save other attributes
    
    db.flush() # Get IDs
    
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
            
    db.commit()

def calculate_layout(network_id: int, layout_name: str, db: Session):
    # Reconstruct graph from DB
    G = nx.Graph()
    nodes = db.query(models.Node).filter(models.Node.network_id == network_id).all()
    edges = db.query(models.Edge).filter(models.Edge.network_id == network_id).all()
    
    for n in nodes:
        G.add_node(n.node_id)
    for e in edges:
        # Need to get node_ids from IDs
        # Simplified: assume we can get them efficiently
        # For MVP, let's just use the IDs if we had them loaded
        pass 
    
    # For MVP, let's just calculate random layout or spring if we had the graph
    # Since reconstructing from DB is heavy, in a real app we might cache or load optimized
    
    # Placeholder logic:
    # 1. Define attributes for x and y
    attr_x = get_or_create_attribute(network_id, f"{layout_name}_x", db)
    attr_y = get_or_create_attribute(network_id, f"{layout_name}_y", db)
    
    # 2. Calculate (mock)
    import random
    for n in nodes:
        save_float_attribute_value(n.id, attr_x.id, random.random(), db)
        save_float_attribute_value(n.id, attr_y.id, random.random(), db)
    
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
    attr = get_or_create_attribute(network_id, attr_name, db)
    
    for node_id, value in centrality.items():
        db_node_id = node_map[node_id]
        save_float_attribute_value(db_node_id, attr.id, float(value), db)
        
    db.commit()
    return centrality

# Helpers
def get_or_create_attribute(network_id: int, name: str, db: Session):
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

def save_float_attribute_value(node_id: int, attribute_id: int, value: float, db: Session):
    # Check if exists
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
        # Update
        if val.float_value:
            val.float_value.float_value = value
        else:
            float_val = models.NodeFloatAttributeValue(node_attribute_value_id=val.id, float_value=value)
            db.add(float_val)
