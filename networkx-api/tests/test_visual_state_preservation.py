import pytest
from common import models
from app.logic import visualizer
from sqlalchemy.orm import Session

def create_test_network_with_attributes(db: Session):
    network = models.Network(id=2025, name="State Test Net")
    db.add(network)
    
    n1 = models.Node(id=1, network_id=2025, node_id="n1")
    n2 = models.Node(id=2, network_id=2025, node_id="n2")
    db.add(n1)
    db.add(n2)
    
    # Layout attributes
    db.add(models.NodeAttribute(id=10, network_id=2025, attribute_name="forceatlas2_x", data_type="float"))
    db.add(models.NodeAttribute(id=11, network_id=2025, attribute_name="forceatlas2_y", data_type="float"))
    
    # Score attribute for coloring
    attr = models.NodeAttribute(id=20, network_id=2025, attribute_name="score", data_type="float")
    db.add(attr)
    db.add(models.NodeAttributeValue(id=30, node_id=1, attribute_id=20))
    db.add(models.NodeFloatAttributeValue(node_attribute_value_id=30, float_value=10.0))
    db.add(models.NodeAttributeValue(id=31, node_id=2, attribute_id=20))
    db.add(models.NodeFloatAttributeValue(node_attribute_value_id=31, float_value=20.0))
    
    db.flush()
    return network.id

def test_preserve_visual_state(db: Session):
    net_id = create_test_network_with_attributes(db)
    
    # 1. First Pass: Apply Color by 'score'
    color_config = {
        "attribute": "score", 
        "scale_type": "LINEAR",
        "gradient": ["#FFFFFF", "#000000"] # White to Black
    }
    
    res1 = visualizer.generate_visualization_data(
        net_id, db,
        node_color_config=color_config
    )
    
    # Verify DB State
    net = db.query(models.Network).filter(models.Network.id == net_id).first()
    assert net.last_node_color_config is not None
    assert net.last_node_color_config["attribute"] == "score"
    
    # Verify Output
    assert "legend" in res1
    assert res1["legend"]["node_color"]["attribute"] == "score"
    
    # 2. Second Pass: Change Layout ONLY (pass None for colors)
    # This simulates the user saying "Fix the layout" without mentioning colors.
    
    res2 = visualizer.generate_visualization_data(
        net_id, db,
        layout_name="forceatlas2", # Explicit or default doesn't matter much as long as we don't pass node_color_config
        node_color_config=None,
        node_size_config={"default": 50} # Apply some size change
    )
    
    # Verify that Color Config was PRESERVED
    # The output should still have node_color based on 'score'
    assert "legend" in res2
    assert "node_color" in res2["legend"], "node_color info missing in legend - implies it was lost?"
    assert res2["legend"]["node_color"]["attribute"] == "score", "Previous color attribute was NOT preserved!"
    
    # Verify that Size Config was APPLIED
    assert "node_size" in res2["legend"]
    # Size doesn't have attribute, but it was set.
    
    # Check that net.last_node_size_config was updated
    db.expire(net)
    db.refresh(net)
    assert net.last_node_size_config == {"default": 50}
    assert net.last_node_color_config["attribute"] == "score" # Should be untouched

def test_override_visual_state(db: Session):
    net_id = create_test_network_with_attributes(db)
    
    # 1. Set Color
    visualizer.generate_visualization_data(
        net_id, db,
        node_color_config={"attribute": "score", "scale_type": "LINEAR"}
    )
    
    # 2. Override Color (Reset to default/static?)
    # If we pass a config without attribute, it means "Static" or "Default"?
    # The user request said "Use previous... unless newly specified".
    # So if I specify a new config, it should overwrite.
    
    new_color_config = {"default_color": "#FF0000"} # Valid config (no attribute)
    
    res3 = visualizer.generate_visualization_data(
        net_id, db,
        node_color_config=new_color_config
    )
    
    assert res3["legend"].get("node_color") and res3["legend"]["node_color"]["attribute"] is None
    
    # Verify DB
    net = db.query(models.Network).filter(models.Network.id == net_id).first()
    assert net.last_node_color_config == new_color_config
