
import pytest
from unittest import mock
from app.mcp import tools
from common import models
from app.core import database

@pytest.fixture
def db():
    session = database.SessionLocal()
    yield session
    session.close()

@pytest.fixture
def setup_network(db):
    # Create network
    net = models.Network(name="Test Label Mode")
    db.add(net)
    db.commit()
    db.refresh(net)
    
    # Create nodes with manual labels
    n1 = models.Node(network_id=net.id, node_id="A", label="Manual A")
    n2 = models.Node(network_id=net.id, node_id="B", label="Manual B")
    db.add_all([n1, n2])
    db.commit()
    
    # Add 'country' attribute
    attr = models.NodeAttribute(network_id=net.id, attribute_name="country", data_type="string")
    db.add(attr)
    db.commit()
    
    val1 = models.NodeAttributeValue(node_id=n1.id, attribute_id=attr.id)
    val2 = models.NodeAttributeValue(node_id=n2.id, attribute_id=attr.id)
    db.add_all([val1, val2])
    db.commit()
    
    db.add(models.NodeTextAttributeValue(node_attribute_value_id=val1.id, text_value="Austria"))
    db.add(models.NodeTextAttributeValue(node_attribute_value_id=val2.id, text_value="Belgium"))
    db.commit()
    
    # Ensure attributes are fully committed and accessible
    db.refresh(val1)
    db.refresh(val2)
    
    return net.id

def test_label_mode_switch(db, setup_network):
    network_id = setup_network
    
    # Mock session to prevent early closing by tools
    session_proxy = mock.MagicMock(wraps=db)
    session_proxy.close.return_value = None
    
    with mock.patch("app.core.database.SessionLocal", return_value=session_proxy):
        # 0. Initial State: Should be manual labels
        # Need layout first? visualization_builder says so.
        tools.calculate_layout(network_id, "forceatlas2")
        
        vis0 = tools.generate_visualization(network_id)
        labels0 = {n["id"]: n["label"] for n in vis0["nodes"]}
        assert labels0["A"] == "Manual A"
        assert labels0["B"] == "Manual B"
        
        # 1. Switch to Attribute Labeling (country)
        vis1 = tools.update_node_label_mode(network_id, attribute="country")
        labels1 = {n["id"]: n["label"] for n in vis1["nodes"]}
        assert labels1["A"] == "Austria"
        assert labels1["B"] == "Belgium"
        
        # 2. Revert to Default (None)
        vis2 = tools.update_node_label_mode(network_id, attribute=None)
        labels2 = {n["id"]: n["label"] for n in vis2["nodes"]}
        assert labels2["A"] == "Manual A"
        assert labels2["B"] == "Manual B"

def test_label_mode_strict_validation(db, setup_network):
    network_id = setup_network
    session_proxy = mock.MagicMock(wraps=db)
    session_proxy.close.return_value = None
    
    with mock.patch("app.core.database.SessionLocal", return_value=session_proxy):
        tools.calculate_layout(network_id, "forceatlas2")
        
        # Try non-existent attribute
        with pytest.raises(RuntimeError) as excinfo:
            tools.update_node_label_mode(network_id, attribute="invalid_attr")
        
        assert "Missing required attributes" in str(excinfo.value)
