
import pytest
import io
from app.logic.importer import parse_and_save_graphml
from app.logic.attributes import clear_network_data
from app import models
from app.core.database import SessionLocal

@pytest.fixture
def db_session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def test_graphml_desc_import(db_session):
    graphml_content = """<?xml version="1.0" encoding="UTF-8"?>
<graphml xmlns="http://graphml.graphdrawing.org/xmlns"
  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
  xsi:schemaLocation="http://graphml.graphdrawing.org/xmlns http://graphml.graphdrawing.org/xmlns/1.0/graphml.xsd">
  <graph id="G" edgedefault="undirected">
    <desc>This is a test network description</desc>
    <node id="n0">
      <desc>Description for Node 0</desc>
      <data key="d0">green</data>
    </node>
    <node id="n1">
      <desc>Description for Node 1</desc>
    </node>
    <edge id="e0" source="n0" target="n1">
      <desc>Description for Edge 0-1</desc>
    </edge>
  </graph>
  <key id="d0" for="node" attr.name="color" attr.type="string">
    <desc>Color of the node</desc>
    <default>yellow</default>
  </key>
</graphml>
"""
    
    # Use a random network ID to avoid collision
    network_id = 9999
    
    # Clean up before test
    existing = db_session.query(models.Network).filter(models.Network.id == network_id).first()
    if existing:
         clear_network_data(network_id, db_session)
         db_session.query(models.Network).filter(models.Network.id == network_id).delete()
         db_session.commit()
    
    final_network_id = parse_and_save_graphml(network_id, graphml_content, db_session)
    
    # Verify Network Description
    network = db_session.query(models.Network).filter(models.Network.id == final_network_id).first()
    assert network.description == "This is a test network description"
    
    # Verify Attribute Description (Key Desc)
    color_attr = db_session.query(models.NodeAttribute).filter(
        models.NodeAttribute.network_id == final_network_id,
        models.NodeAttribute.attribute_name == "color"
    ).first()
    assert color_attr is not None
    assert color_attr.description == "Color of the node"
    
    # Verify Node Attribute Definition (Implicit description attr)
    desc_attr = db_session.query(models.NodeAttribute).filter(
        models.NodeAttribute.network_id == final_network_id,
        models.NodeAttribute.attribute_name == "description"
    ).first()
    assert desc_attr is not None
    assert desc_attr.data_type == "string"
    
    # Verify Node Descriptions (values)
    # n0
    n0 = db_session.query(models.Node).filter(models.Node.network_id == final_network_id, models.Node.node_id == "n0").first()
    assert n0 is not None
    n0_desc_val = db_session.query(models.NodeTextAttributeValue).join(models.NodeAttributeValue).filter(
        models.NodeAttributeValue.node_id == n0.id,
        models.NodeAttributeValue.attribute_id == desc_attr.id
    ).first()
    assert n0_desc_val is not None
    assert n0_desc_val.text_value == "Description for Node 0"

    # n1
    n1 = db_session.query(models.Node).filter(models.Node.network_id == final_network_id, models.Node.node_id == "n1").first()
    n1_desc_val = db_session.query(models.NodeTextAttributeValue).join(models.NodeAttributeValue).filter(
        models.NodeAttributeValue.node_id == n1.id,
        models.NodeAttributeValue.attribute_id == desc_attr.id
    ).first()
    assert n1_desc_val is not None
    assert n1_desc_val.text_value == "Description for Node 1"

    # Verify Edge Descriptions
    edge_desc_attr = db_session.query(models.EdgeAttribute).filter(
        models.EdgeAttribute.network_id == final_network_id,
        models.EdgeAttribute.attribute_name == "description"
    ).first()
    assert edge_desc_attr is not None
    
    # Edge e0 (n0-n1)
    edge = db_session.query(models.Edge).filter(
        models.Edge.network_id == final_network_id,
        models.Edge.source_node_id == n0.id,
        models.Edge.target_node_id == n1.id
    ).first()
    if not edge:
         edge = db_session.query(models.Edge).filter(
            models.Edge.network_id == final_network_id,
            models.Edge.source_node_id == n1.id,
            models.Edge.target_node_id == n0.id
        ).first()
    assert edge is not None
    
    edge_val = db_session.query(models.EdgeTextAttributeValue).join(models.EdgeAttributeValue).filter(
        models.EdgeAttributeValue.edge_id == edge.id,
        models.EdgeAttributeValue.attribute_id == edge_desc_attr.id
    ).first()
    assert edge_val is not None
    assert edge_val.text_value == "Description for Edge 0-1"

    print("Verification Passed!")
