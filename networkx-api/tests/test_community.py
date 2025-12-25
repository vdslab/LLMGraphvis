
import pytest
from common import models
from app.logic.community import calculate_community

def setup_clique_network(db):
    """Creates two disconnected cliques (communities)"""
    network = models.Network(id=1, name="Test Net")
    db.add(network)
    
    # Cluster 1: n0, n1, n2
    nodes = []
    for i in range(6):
        n = models.Node(network_id=1, node_id=f"n{i}")
        db.add(n)
        nodes.append(n)
    db.commit()
    
    # Map str_id -> db_id
    node_map = {n.node_id: n.id for n in nodes}
    
    # Edges - Clique 1 (0,1,2)
    db.add(models.Edge(network_id=1, source_node_id=node_map["n0"], target_node_id=node_map["n1"], edge_id="e01"))
    db.add(models.Edge(network_id=1, source_node_id=node_map["n1"], target_node_id=node_map["n2"], edge_id="e12"))
    db.add(models.Edge(network_id=1, source_node_id=node_map["n2"], target_node_id=node_map["n0"], edge_id="e20"))
    
    # Edges - Clique 2 (3,4,5)
    db.add(models.Edge(network_id=1, source_node_id=node_map["n3"], target_node_id=node_map["n4"], edge_id="e34"))
    db.add(models.Edge(network_id=1, source_node_id=node_map["n4"], target_node_id=node_map["n5"], edge_id="e45"))
    db.add(models.Edge(network_id=1, source_node_id=node_map["n5"], target_node_id=node_map["n3"], edge_id="e53"))
    
    db.commit()
    return network

def test_calculate_community_greedy_modularity(db):
    setup_clique_network(db)
    
    attr_name = calculate_community(1, "greedy_modularity", db)
    
    assert attr_name == "community"
    
    # Verify DB
    attr = db.query(models.NodeAttribute).filter_by(network_id=1, attribute_name="community").first()
    assert attr is not None
    assert attr.data_type == "string"
    
    # Check values
    # We expect 2 distinct communities
    navs = db.query(models.NodeAttributeValue).filter_by(attribute_id=attr.id).all()
    assert len(navs) == 6
    
    # Check text values
    communities = set()
    for nav in navs:
        val = db.query(models.NodeTextAttributeValue).filter_by(node_attribute_value_id=nav.id).first()
        if val:
            communities.add(val.text_value)
            
    assert len(communities) == 2

def test_calculate_community_unknown_algo(db):
    with pytest.raises(ValueError):
        calculate_community(1, "invalid_algo", db)
