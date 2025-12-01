
import sys
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.database import SQLALCHEMY_DATABASE_URL
from app import models
from app.logic.graph_processor import parse_and_save_graphml

def verify():
    engine = create_engine(SQLALCHEMY_DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    # Clean up
    try:
        from sqlalchemy import text
        # Delete attribute values (children first)
        db.execute(text("DELETE FROM node_float_attribute_values WHERE node_attribute_value_id IN (SELECT id FROM node_attribute_values WHERE node_id IN (SELECT id FROM nodes WHERE network_id = 999))"))
        db.execute(text("DELETE FROM node_text_attribute_values WHERE node_attribute_value_id IN (SELECT id FROM node_attribute_values WHERE node_id IN (SELECT id FROM nodes WHERE network_id = 999))"))
        db.execute(text("DELETE FROM node_attribute_values WHERE node_id IN (SELECT id FROM nodes WHERE network_id = 999)"))
        
        db.execute(text("DELETE FROM edge_float_attribute_values WHERE edge_attribute_value_id IN (SELECT id FROM edge_attribute_values WHERE edge_id IN (SELECT id FROM edges WHERE network_id = 999))"))
        db.execute(text("DELETE FROM edge_text_attribute_values WHERE edge_attribute_value_id IN (SELECT id FROM edge_attribute_values WHERE edge_id IN (SELECT id FROM edges WHERE network_id = 999))"))
        db.execute(text("DELETE FROM edge_attribute_values WHERE edge_id IN (SELECT id FROM edges WHERE network_id = 999)"))

        # Delete attributes
        db.execute(text("DELETE FROM node_attributes WHERE network_id = 999"))
        db.execute(text("DELETE FROM edge_attributes WHERE network_id = 999"))

        # Delete edges (references nodes)
        db.execute(text("DELETE FROM edges WHERE network_id = 999"))
        
        # Delete nodes
        db.execute(text("DELETE FROM nodes WHERE network_id = 999"))
        
        # Delete network
        db.execute(text("DELETE FROM networks WHERE id = 999"))
        
        db.commit()
        print("Cleaned up old test data.")
    except Exception as e:
        print(f"Cleanup failed: {e}")
        db.rollback()
    
    # Dummy GraphML
    graphml = '''<?xml version="1.0" encoding="UTF-8"?>
<graphml xmlns="http://graphml.graphdrawing.org/xmlns"  
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xsi:schemaLocation="http://graphml.graphdrawing.org/xmlns
     http://graphml.graphdrawing.org/xmlns/1.0/graphml.xsd">
  <key id="d0" for="node" attr.name="weight" attr.type="double"/>
  <key id="d1" for="node" attr.name="type" attr.type="string"/>
  <graph id="G" edgedefault="undirected">
    <node id="n0">
      <data key="d0">1.5</data>
      <data key="d1">A</data>
    </node>
    <node id="n1">
      <data key="d0">2.0</data>
      <data key="d1">B</data>
    </node>
  </graph>
</graphml>'''

    print("Parsing GraphML...")
    try:
        print("Calling parse_and_save_graphml...")
        parse_and_save_graphml(999, graphml, db)
        print("Parsed successfully.")
    except Exception as e:
        print(f"Failed: {e}")
        return

    # Verify
    print("Verifying attributes...")
    attrs = db.query(models.NodeAttribute).filter(models.NodeAttribute.network_id == 999).all()
    for attr in attrs:
        print(f"Attribute: {attr.attribute_name}, Type: {attr.data_type}")
        if attr.attribute_name == "weight" and attr.data_type != "float":
            print("FAILURE: weight should be float")
        if attr.attribute_name == "type" and attr.data_type != "string":
            print("FAILURE: type should be string")

if __name__ == "__main__":
    verify()
