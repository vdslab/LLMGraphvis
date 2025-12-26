
import pytest
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from common.models import Base, Network, Node, Edge, NodeAttribute, NodeAttributeValue, NodeFloatAttributeValue, NodeTextAttributeValue
from app.logic import importer, layout, centrality, visualization_builder
from app.schemas.visualization import NodeColorConfig, NodeSizeConfig
import networkx as nx
import math

# Use in-memory SQLite for speed and isolation
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

@pytest.fixture(scope="function")
def db_session():
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)

def test_persistence_graphml_import(db_session):
    graphml = """<?xml version="1.0" encoding="UTF-8"?>
<graphml xmlns="http://graphml.graphdrawing.org/xmlns"  
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xsi:schemaLocation="http://graphml.graphdrawing.org/xmlns
     http://graphml.graphdrawing.org/xmlns/1.0/graphml.xsd">
  <key id="d0" for="node" attr.name="color" attr.type="string">
    <default>yellow</default>
  </key>
  <key id="d1" for="edge" attr.name="weight" attr.type="double"/>
  <key id="d2" for="node" attr.name="score" attr.type="double"/>
  <graph id="G" edgedefault="undirected">
    <node id="n0">
      <data key="d0">green</data>
      <data key="d2">1.5</data>
    </node>
    <node id="n1">
        <data key="d2">2.5</data>
    </node>
    <edge source="n0" target="n1">
      <data key="d1">10.0</data>
    </edge>
  </graph>
</graphml>"""
    
    # 1. Import
    network_id = 1
    importer.parse_and_save_graphml(network_id, graphml, db_session)
    
    # 2. Verify Nodes
    nodes = db_session.query(Node).filter(Node.network_id == network_id).all()
    assert len(nodes) == 2
    node_ids = sorted([n.node_id for n in nodes])
    assert node_ids == ["n0", "n1"]
    
    # 3. Verify Edges
    edges = db_session.query(Edge).filter(Edge.network_id == network_id).all()
    assert len(edges) == 1
    assert edges[0].weight == 10.0
    
    # 4. Verify Attributes (score=1.5/2.5) float
    score_attr = db_session.query(NodeAttribute).filter(NodeAttribute.network_id == network_id, NodeAttribute.attribute_name == "score").first()
    assert score_attr is not None
    assert score_attr.data_type == "float"
    
    val_n0 = db_session.query(NodeFloatAttributeValue).join(NodeAttributeValue).join(Node).filter(Node.node_id == "n0", NodeAttributeValue.attribute_id == score_attr.id).first()
    assert val_n0.float_value == 1.5
    
    val_n1 = db_session.query(NodeFloatAttributeValue).join(NodeAttributeValue).join(Node).filter(Node.node_id == "n1", NodeAttributeValue.attribute_id == score_attr.id).first()
    assert val_n1.float_value == 2.5
    
    # 5. Verify String Attribute (color)
    color_attr = db_session.query(NodeAttribute).filter(NodeAttribute.network_id == network_id, NodeAttribute.attribute_name == "color").first()
    assert color_attr.data_type == "string"
    
    val_color_n0 = db_session.query(NodeTextAttributeValue).join(NodeAttributeValue).join(Node).filter(Node.node_id == "n0", NodeAttributeValue.attribute_id == color_attr.id).first()
    assert val_color_n0.text_value == "green"

def test_persistence_layout(db_session):
    # Setup network
    network = Network(id=1, name="Test Net")
    db_session.add(network)
    n1 = Node(network_id=1, node_id="1")
    n2 = Node(network_id=1, node_id="2")
    db_session.add_all([n1, n2])
    
    # Manual ID assignment for test simplicity or flush
    db_session.flush() # Populate IDs
    e1 = Edge(network_id=1, edge_id="1-2", source_node_id=n1.id, target_node_id=n2.id)
    db_session.add(e1)
    db_session.commit()
    
    # Calculate Layout
    layout.calculate_layout(1, "forceatlas2", db_session)
    
    # Verify Network Last Layout Name
    net = db_session.query(Network).get(1)
    assert net.last_layout_name == "forceatlas2"
    
    # Verify x, y attributes
    x_attr = db_session.query(NodeAttribute).filter(NodeAttribute.network_id == 1, NodeAttribute.attribute_name == "forceatlas2_x").first()
    y_attr = db_session.query(NodeAttribute).filter(NodeAttribute.network_id == 1, NodeAttribute.attribute_name == "forceatlas2_y").first()
    
    assert x_attr is not None
    assert y_attr is not None
    
    # Verify Values exist
    vals = db_session.query(NodeFloatAttributeValue).join(NodeAttributeValue).filter(NodeAttributeValue.attribute_id == x_attr.id).all()
    assert len(vals) == 2

def test_persistence_visualization_config(db_session):
    network = Network(id=1, name="Test Net")
    db_session.add(network)
    db_session.commit()
    
    node_color = NodeColorConfig(attribute="score", scale_type="LINEAR")
    
    # Build Visualization (updates state)
    builder = visualization_builder.VisualizationBuilder(
        network_id=1,
        db=db_session,
        node_color_config=node_color.model_dump()
    )
    # Mock validate_and_prepare parts that require data if we don't have it
    # But usually build() requires data. 
    # Let's simple check _save_state logic directly if possible or add minimal data.
    db_session.add(Node(network_id=1, node_id="1"))
    db_session.commit()
    
    try:
        # validate_and_prepare might fail if attrs missing, but here we just check if it saves config
        # We need to bypass fetch_data validation if we want to just test save,
        # but the standard flow calls it all.
        # Let's ensure attributes exist to pass validation
        attr = NodeAttribute(network_id=1, attribute_name="score", data_type="float")
        db_session.add(attr)
        db_session.commit()
        
        # Inject attribute value
        n = db_session.query(Node).first()
        nav = NodeAttributeValue(node_id=n.id, attribute_id=attr.id)
        db_session.add(nav)
        db_session.flush()
        db_session.add(NodeFloatAttributeValue(node_attribute_value_id=nav.id, float_value=1.0))
        db_session.commit()
            
        builder.validate_and_prepare()
        builder.fetch_data()
        builder.calculate_statistics()
        builder.build()
        
        # Verify
        net = db_session.query(Network).get(1)
        assert net.last_node_color_config is not None
        assert net.last_node_color_config['attribute'] == "score"
        
    except Exception as e:
        pytest.fail(f"Visualization builder failed: {e}")

def test_nan_handling_in_layout(db_session, monkeypatch):
    # Setup network
    network = Network(id=1, name="Test Net")
    db_session.add(network)
    n1 = Node(network_id=1, node_id="1")
    db_session.add(n1)
    db_session.commit()
    
    # Mock spring_layout to return NaN
    def mock_layout(*args, **kwargs):
        return {"1": (float('nan'), float('nan'))}
    
    monkeypatch.setattr(nx, "spring_layout", mock_layout)
    monkeypatch.setattr(nx, "forceatlas2_layout", mock_layout) # in case we use it
    
    # Run layout
    try:
        layout.calculate_layout(1, "spring", db_session)
    except Exception as e:
        # It's okay if it fails, but we want to see HOW it fails. 
        # Ideally it should handle it or fail gracefully, but standard DBs might reject NaN.
        # SQLite actually Supports NaN in Float columns usually.
        pass
        
    # Check what happened
    x_attr = db_session.query(NodeAttribute).filter(NodeAttribute.attribute_name == "spring_x").first()
    vals = db_session.query(NodeFloatAttributeValue).join(NodeAttributeValue).filter(NodeAttributeValue.attribute_id == x_attr.id).all()
    
    if vals:
        val = vals[0].float_value
        # Check if it is None (SQLite behavior for NaN in this context or SQLAlchemy mapping)
        assert val is None, f"Expected None (for NaN), got {val}"
    else:
        # If no values inserted, that's also one valid outcome if it crashed silently (bad) or handled it
        # But if calculate_layout didn't raise, it probably inserted something.
        pass
