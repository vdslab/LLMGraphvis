
import pytest
from common import models
from app.logic.layout import calculate_layout

def setup_simple_graph(db):
    network = models.Network(id=1, name="Layout Net")
    db.add(network)
    
    nodes = []
    for i in range(3):
        n = models.Node(network_id=1, node_id=f"n{i}")
        db.add(n)
        nodes.append(n)
    db.commit()
    
    # Map str_id -> db_id
    node_map = {n.node_id: n.id for n in nodes}
    
    db.add(models.Edge(network_id=1, source_node_id=node_map["n0"], target_node_id=node_map["n1"], edge_id="e0"))
    db.add(models.Edge(network_id=1, source_node_id=node_map["n1"], target_node_id=node_map["n2"], edge_id="e1"))
    
    db.commit()

def test_calculate_layout_spring(db):
    setup_simple_graph(db)
    
    # Use 'spring' which is valid
    calculate_layout(1, "spring", db)
    
    # Verify DB persistence of X/Y coordinates as attributes
    attr_x = db.query(models.NodeAttribute).filter_by(network_id=1, attribute_name="spring_x").first()
    assert attr_x is not None
    assert attr_x.data_type == "float"

    attr_y = db.query(models.NodeAttribute).filter_by(network_id=1, attribute_name="spring_y").first()
    assert attr_y is not None

def test_calculate_layout_circular(db):
    setup_simple_graph(db)
    
    calculate_layout(1, "circular", db)
    
    # Check attributes exist
    attr = db.query(models.NodeAttribute).filter_by(network_id=1, attribute_name="circular_x").first()
    assert attr is not None
