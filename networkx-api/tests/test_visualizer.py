import pytest
from app.logic import visualizer
from app import models

# Helper to load data
def create_test_network(db):
    network = models.Network(id=999, name="Test Network")
    db.add(network)
    
    # Nodes
    n1 = models.Node(id=1, network_id=999, node_id="n1", label="Node 1")
    n2 = models.Node(id=2, network_id=999, node_id="n2", label="Node 2")
    db.add(n1)
    db.add(n2)
    
    # Edge
    e1 = models.Edge(id=1, network_id=999, edge_id="e1", source_node_id=1, target_node_id=2)
    db.add(e1)
    
    # Attribute (required for some strict checks, though basics should pass)
    # Adding a dummy layout attribute to satisfy "existing attribute" Check
    lay_x = models.NodeAttribute(id=100, network_id=999, attribute_name="forceatlas2_x", data_type="float")
    lay_y = models.NodeAttribute(id=101, network_id=999, attribute_name="forceatlas2_y", data_type="float")
    db.add(lay_x)
    db.add(lay_y)
    
    db.commit()
    return network.id

def test_basic_generation(db):
    network_id = create_test_network(db)
    
    result = visualizer.generate_visualization_data(network_id, db)
    
    assert "nodes" in result
    assert "links" in result
    assert len(result["nodes"]) == 2
    assert len(result["links"]) == 1
    
    n1 = next(n for n in result["nodes"] if n["id"] == "n1")
    assert n1["label"] == "Node 1"
    # Basic defaults
    assert "color" in n1
    assert "size" in n1

def test_missing_attribute_raises_error(db):
    network_id = create_test_network(db)
    
    # Config referencing non-existent attribute
    node_size_config = {"attribute": "non_existent_centrality"}
    
    with pytest.raises(ValueError) as excinfo:
        visualizer.generate_visualization_data(
            network_id, 
            db, 
            node_size_config=node_size_config
        )
    assert "Missing required attributes" in str(excinfo.value)
    assert "non_existent_centrality" in str(excinfo.value)

def test_generate_with_none_config(db):
    """Test robustness when configs are None."""
    network_id = create_test_network(db)
    
    # Should not raise exception
    result = visualizer.generate_visualization_data(
        network_id, 
        db,
        node_size_config=None,
        node_color_config=None,
        edge_width_config=None,
        edge_color_config=None
    )
    
    assert "nodes" in result
    assert len(result["nodes"]) == 2
    # Verify default colors applied without error
    for node in result["nodes"]:
        assert node["color"] is not None
