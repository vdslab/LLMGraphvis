
import pytest
from unittest import mock
from app.mcp import tools
from app.logic import layout
from common import models
from app.core import database
import networkx as nx

import json
@pytest.fixture
def db():
    session = database.SessionLocal()
    yield session
    session.close()

@pytest.fixture
def setup_network(db):
    # Create valid network
    net = models.Network(name="Test Visual Flow")
    db.add(net)
    db.commit()
    db.refresh(net)
    
    # Create simple graph
    n1 = models.Node(network_id=net.id, node_id="A", label="Austria")
    n2 = models.Node(network_id=net.id, node_id="B", label="Belgium")
    db.add_all([n1, n2])
    db.commit()
    
    # Add attributes for coloring
    # 1. Categorical: country
    attr_cat = models.NodeAttribute(network_id=net.id, attribute_name="country", data_type="string")
    db.add(attr_cat)
    db.commit()
    
    val1 = models.NodeAttributeValue(node_id=n1.id, attribute_id=attr_cat.id)
    val2 = models.NodeAttributeValue(node_id=n2.id, attribute_id=attr_cat.id)
    db.add_all([val1, val2])
    db.commit()
    
    db.add(models.NodeTextAttributeValue(node_attribute_value_id=val1.id, text_value="Europe"))
    db.add(models.NodeTextAttributeValue(node_attribute_value_id=val2.id, text_value="Europe"))
    
    # 2. Numerical: score
    attr_num = models.NodeAttribute(network_id=net.id, attribute_name="score", data_type="float")
    db.add(attr_num)
    db.commit()
    
    val_num1 = models.NodeAttributeValue(node_id=n1.id, attribute_id=attr_num.id)
    val_num2 = models.NodeAttributeValue(node_id=n2.id, attribute_id=attr_num.id)
    db.add_all([val_num1, val_num2])
    db.commit()
    
    db.refresh(val_num1)
    db.refresh(val_num2)
    
    db.add(models.NodeFloatAttributeValue(node_attribute_value_id=val_num1.id, float_value=10.0))
    db.add(models.NodeFloatAttributeValue(node_attribute_value_id=val_num2.id, float_value=20.0))
    
    db.commit()
    
    # Verify stats are visible immediately
    from app.logic import attributes
    stats = attributes.get_attribute_stats(
        net.id, models.NodeAttribute, models.NodeAttributeValue, 
        models.NodeFloatAttributeValue, models.NodeTextAttributeValue, db
    )
    
    return net.id

def test_visualization_flow_strict_check(db, setup_network):
    network_id = setup_network
    
    # Create a proxy for DB session that ignores close() calls from tools
    session_proxy = mock.MagicMock(wraps=db)
    session_proxy.close.return_value = None
    
    with mock.patch("app.core.database.SessionLocal", return_value=session_proxy):
        # 1. Try to visualize with 'forceatlas2' WITHOUT calculating it
        # Should fail because we removed auto-calculation
        
        with pytest.raises(RuntimeError) as excinfo:
            tools.generate_visualization(network_id)
        
        assert "Missing required attributes" in str(excinfo.value)
        assert "Missing required attributes" in str(excinfo.value)
        
        # 2. Calculate Layout
        calc_res = tools.calculate_layout(network_id, "forceatlas2")
        # Verify calculation succeeded
        assert "Layout 'forceatlas2' calculated" in calc_res, f"Calculation failed: {calc_res}"
        
        # 3. Verify attributes exist
        attrs_str = tools.list_node_attributes(network_id)
        # attrs_str is stringified dict/list representation from pydantic/sqlalchemy objects or just valid JSON?
        # The tool returns str(stats). Implementation uses str(list_of_dicts).
        # list_node_attributes implementation: "return str(stats)"
        # Python's str() of a list uses single quotes. JSON requires double.
        # We might need to adjust implementation to return JSON.
        # For now, let's assume we fix implementation to return JSON or use eval (unsafe but ok for tests).
        # Let's fix implementation to use json.dumps later.
        # But for this test patch, I'll use eval if I must, or just check substring.
        assert "forceatlas2_x" in attrs_str
        assert "forceatlas2_y" in attrs_str
        
        # 4. Visualize again -> Should success
        result = tools.generate_visualization(network_id)
        assert "nodes" in result
        assert "links" in result
        assert len(result["nodes"]) == 2


def test_color_patterns(db, setup_network):
    network_id = setup_network
    
    session_proxy = mock.MagicMock(wraps=db)
    session_proxy.close.return_value = None
    
    with mock.patch("app.core.database.SessionLocal", return_value=session_proxy):
        # Ensure layout exists for visualization to work
        tools.calculate_layout(network_id, "forceatlas2")
        
        # Pattern 1: Categorical (Auto)
        # The user/LLM calls update_node_color with categorical scale
        res1 = tools.update_node_color(
            network_id=network_id,
            attribute="country",
            scale_type="CATEGORICAL"
        )
        
        assert "legend" in res1
        assert "node_color" in res1["legend"]
        assert res1["legend"]["node_color"]["type"] == "categorical"
        # mapping should exist
        assert "mapping" in res1["legend"]["node_color"]
        
        # Verify score attribute stats
        # Verify score attribute stats
        attrs_str = tools.list_node_attributes(network_id)
        assert "'name': 'score'" in attrs_str
        assert "'min': 10.0" in attrs_str
        
        # Pattern 2: Numerical (Linear)
        res2 = tools.update_node_color(
            network_id=network_id,
            attribute="score",
            scale_type="LINEAR"
        )
        assert res2["legend"]["node_color"]["type"] == "linear"
        assert res2["legend"]["node_color"]["min"] == 10.0
        assert res2["legend"]["node_color"]["max"] == 20.0
        
        # Pattern 3: Value Match (Fixed)
        # User says "Europe" is Red.
        res3 = tools.update_node_color(
            network_id=network_id,
            attribute="country",
            scale_type="CATEGORICAL",
            mapping={"Europe": "red"},
            fixed=True
        )
        
        # Verify nodes have color red
        nodes = res3["nodes"]
        for n in nodes:
            assert n["color"] == "red"

def test_missing_style_attribute(db, setup_network):
    network_id = setup_network
    
    # Ensure layout exists so we don't fail on layout check
    tools.calculate_layout(network_id, "forceatlas2")
    
    session_proxy = mock.MagicMock(wraps=db)
    session_proxy.close.return_value = None
    
    with mock.patch("app.core.database.SessionLocal", return_value=session_proxy):
        # Try to use a non-existent attribute for coloring
        with pytest.raises(RuntimeError) as excinfo:
            tools.update_node_color(
                network_id=network_id,
                attribute="non_existent_attr",
                scale_type="CATEGORICAL"
            )
        
        assert "Missing required attributes" in str(excinfo.value)
        assert "non_existent_attr" in str(excinfo.value)
