
import pytest
from common import models
from app.logic.centrality import calculate_centrality, get_top_nodes

def setup_simple_network(db):
    """Creates a simple star graph: Node 0 connected to 1, 2, 3, 4"""
    network = models.Network(id=1, name="Test Net")
    db.add(network)
    
    # Nodes
    nodes = []
    for i in range(5):
        n = models.Node(network_id=1, node_id=f"n{i}")
        db.add(n)
        nodes.append(n)
    db.commit() # Commit to get IDs
    
    # Map str_id -> db_id
    node_map = {n.node_id: n.id for n in nodes}
    
    # Edges (Star graph center at n0)
    edges = []
    for i in range(1, 5):
        e = models.Edge(
            network_id=1, 
            source_node_id=node_map["n0"], 
            target_node_id=node_map[f"n{i}"], 
            edge_id=f"e{i}"
        )
        db.add(e)
    db.commit()
    return network

def test_calculate_degree_centrality(db):
    setup_simple_network(db)
    
    # Calculate
    centrality = calculate_centrality(1, "degree", db)
    
    # Check results
    assert "n0" in centrality
    assert centrality["n0"] > centrality["n1"]
    
    # Verify DB persistence
    # 1. Attribute created
    attr = db.query(models.NodeAttribute).filter_by(network_id=1, attribute_name="degree_centrality").first()
    assert attr is not None
    assert attr.data_type == "float"
    
    # 2. Values saved
    nav = db.query(models.NodeAttributeValue).filter_by(attribute_id=attr.id).first()
    assert nav is not None
    
    # 3. Float value saved
    val = db.query(models.NodeFloatAttributeValue).filter_by(node_attribute_value_id=nav.id).first()
    assert val is not None

def test_calculate_unknown_metric(db):
    with pytest.raises(ValueError):
        calculate_centrality(1, "invalid_metric", db)

def test_get_top_nodes(db):
    setup_simple_network(db)
    
    # Get top 1 node by degree
    top = get_top_nodes(1, "degree", 1, "desc", db)
    
    assert len(top) == 1
    assert top[0]["node_id"] == "n0"
