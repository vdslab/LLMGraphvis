
import sys
import os
import xml.etree.ElementTree as ET

# Add current directory to path
sys.path.append(os.getcwd())

from app.logic.importer import parse_and_save_graphml
from app.logic.attributes import _clear_network_data
from app import models
from app.core.database import SessionLocal

def log(msg):
    with open("verification.log", "a") as f:
        f.write(msg + "\n")
    print(msg)

def verify_graphml_desc_import():
    if os.path.exists("verification.log"):
        os.remove("verification.log")
        
    db = SessionLocal()
    try:
        log("Starting verification...")
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
        
        log(f"Cleaning up network {network_id}...")
        # Clean up before test
        existing = db.query(models.Network).filter(models.Network.id == network_id).first()
        if existing:
             _clear_network_data(network_id, db)
             db.query(models.Network).filter(models.Network.id == network_id).delete()
             db.commit()
        
        log("Parsing GraphML...")
        final_network_id = parse_and_save_graphml(network_id, graphml_content, db)
        log(f"Imported Network ID: {final_network_id}")
        
        # Verify Network Description
        network = db.query(models.Network).filter(models.Network.id == final_network_id).first()
        log(f"Network Description: {network.description}")
        assert network.description == "This is a test network description"
        
        # Verify Attribute Description (Key Desc)
        color_attr = db.query(models.NodeAttribute).filter(
            models.NodeAttribute.network_id == final_network_id,
            models.NodeAttribute.attribute_name == "color"
        ).first()
        assert color_attr is not None
        log(f"Color Attribute Description: {color_attr.description}")
        assert color_attr.description == "Color of the node"
        
        # Verify Node Attribute Definition (Implicit description attr)
        desc_attr = db.query(models.NodeAttribute).filter(
            models.NodeAttribute.network_id == final_network_id,
            models.NodeAttribute.attribute_name == "description"
        ).first()
        assert desc_attr is not None
        assert desc_attr.data_type == "string"
        log(f"Description Attribute ID: {desc_attr.id}")
        
        # Verify Node Descriptions (values)
        # n0
        n0 = db.query(models.Node).filter(models.Node.network_id == final_network_id, models.Node.node_id == "n0").first()
        assert n0 is not None
        n0_desc_val = db.query(models.NodeTextAttributeValue).join(models.NodeAttributeValue).filter(
            models.NodeAttributeValue.node_id == n0.id,
            models.NodeAttributeValue.attribute_id == desc_attr.id
        ).first()
        assert n0_desc_val is not None
        log(f"Node n0 Description: {n0_desc_val.text_value}")
        assert n0_desc_val.text_value == "Description for Node 0"
    
        # n1
        n1 = db.query(models.Node).filter(models.Node.network_id == final_network_id, models.Node.node_id == "n1").first()
        n1_desc_val = db.query(models.NodeTextAttributeValue).join(models.NodeAttributeValue).filter(
            models.NodeAttributeValue.node_id == n1.id,
            models.NodeAttributeValue.attribute_id == desc_attr.id
        ).first()
        assert n1_desc_val is not None
        log(f"Node n1 Description: {n1_desc_val.text_value}")
        assert n1_desc_val.text_value == "Description for Node 1"
    
        # Verify Edge Descriptions
        edge_desc_attr = db.query(models.EdgeAttribute).filter(
            models.EdgeAttribute.network_id == final_network_id,
            models.EdgeAttribute.attribute_name == "description"
        ).first()
        assert edge_desc_attr is not None
        
        # Edge e0 (n0-n1)
        edge = db.query(models.Edge).filter(
            models.Edge.network_id == final_network_id,
            models.Edge.source_node_id == n0.id,
            models.Edge.target_node_id == n1.id
        ).first()
        if not edge:
             edge = db.query(models.Edge).filter(
                models.Edge.network_id == final_network_id,
                models.Edge.source_node_id == n1.id,
                models.Edge.target_node_id == n0.id
            ).first()
        assert edge is not None
        
        edge_val = db.query(models.EdgeTextAttributeValue).join(models.EdgeAttributeValue).filter(
            models.EdgeAttributeValue.edge_id == edge.id,
            models.EdgeAttributeValue.attribute_id == edge_desc_attr.id
        ).first()
        assert edge_val is not None
        log(f"Edge e0 Description: {edge_val.text_value}")
        assert edge_val.text_value == "Description for Edge 0-1"
    
        log("\nSUCCESS: All verifications passed!")
        
    except Exception as e:
        log(f"ERROR: {e}")
        import traceback
        log(traceback.format_exc())
        raise
    finally:
        db.close()

if __name__ == "__main__":
    verify_graphml_desc_import()
