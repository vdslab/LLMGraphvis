import pytest
from app.logic.visualizer import generate_visualization_data
from app.logic.visualization_builder import VisualizationBuilder
from app.logic import layout
from common import models

@pytest.fixture
def network(db):
    net = models.Network(name="Test Network", description="For Legend Test")
    db.add(net)
    db.commit()
    db.refresh(net)
    return net

@pytest.fixture
def node_list(db, network):
    nodes = []
    for i in range(10):
        n = models.Node(network_id=network.id, node_id=f"node_{i}", label=f"Node {i}")
        db.add(n)
        nodes.append(n)
    db.commit()
    return nodes

def test_generate_visualization_data_returns_legend(db, network, node_list):
    """
    Verifies that the visualization data generation includes a 'legend' field
    with correct details about applied visual mappings.
    """
    # 1. Setup Data: Assign a 'community' attribute to nodes
    for i, node in enumerate(node_list):
        comm_val = "Group A" if i % 2 == 0 else "Group B"
        # Check if attribute definition exists, if not create
        attr_def = db.query(models.NodeAttribute).filter_by(network_id=network.id, attribute_name="community").first()
        if not attr_def:
            attr_def = models.NodeAttribute(network_id=network.id, attribute_name="community", data_type="TEXT")
            db.add(attr_def)
            db.commit()
            db.refresh(attr_def)
        
        # Add value
        val = models.NodeTextAttributeValue(node_attribute_value_id=None, text_value=comm_val)
        # Note: In the actual schema, NodeTextAttributeValue links to NodeAttributeValue which links to Node/Attribute.
        # Let's use the proper relationship structure or helpers if available.
        # But for valid test setup, let's rely on standard object creation if possible or just mock.
        
        # Simpler approach: Insert directly
        nav = models.NodeAttributeValue(node_id=node.id, attribute_id=attr_def.id)
        db.add(nav)
        db.commit()
        db.refresh(nav)
        
        ntav = models.NodeTextAttributeValue(node_attribute_value_id=nav.id, text_value=comm_val)
        db.add(ntav)
    
    db.commit()
    
    # Pre-calculate layout
    layout.calculate_layout(network.id, "forceatlas2", db)

    # 2. Call generate_visualization_data with a Categorical Config
    node_color_config = {
        "attribute": "community",
        "scale_type": "CATEGORICAL",
        "default_color": "#CCCCCC"
    }

    result = generate_visualization_data(
        network_id=network.id,
        db=db,
        node_color_config=node_color_config,
        layout_name="forceatlas2"
    )

    # 3. Assertions
    assert "nodes" in result
    assert "links" in result
    assert "legend" in result, "Result should contain a 'legend' field"

    legend = result["legend"]
    assert "node_color" in legend
    nc_legend = legend["node_color"]
    assert nc_legend["attribute"] == "community"
    assert nc_legend["type"] == "categorical"
    assert "mapping" in nc_legend
    
    mapping = nc_legend["mapping"]
    assert "Group A" in mapping
    assert "Group B" in mapping
    assert mapping["Group A"] != mapping["Group B"]

    print("\nLegend verification passed!")
    print(legend)
