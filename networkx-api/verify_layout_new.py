
import sys
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.database import SQLALCHEMY_DATABASE_URL
from app import models
from app.logic.importer import parse_and_save_graphml
from app.logic import layout

def verify():
    engine = create_engine(SQLALCHEMY_DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    network_id = 999
    
    # Clean up
    try:
        from sqlalchemy import text
        # Delete attribute values (children first)
        db.execute(text(f"DELETE FROM node_float_attribute_values WHERE node_attribute_value_id IN (SELECT id FROM node_attribute_values WHERE node_id IN (SELECT id FROM nodes WHERE network_id = {network_id}))"))
        db.execute(text(f"DELETE FROM node_text_attribute_values WHERE node_attribute_value_id IN (SELECT id FROM node_attribute_values WHERE node_id IN (SELECT id FROM nodes WHERE network_id = {network_id}))"))
        db.execute(text(f"DELETE FROM node_attribute_values WHERE node_id IN (SELECT id FROM nodes WHERE network_id = {network_id})"))
        
        db.execute(text(f"DELETE FROM edge_float_attribute_values WHERE edge_attribute_value_id IN (SELECT id FROM edge_attribute_values WHERE edge_id IN (SELECT id FROM edges WHERE network_id = {network_id}))"))
        db.execute(text(f"DELETE FROM edge_text_attribute_values WHERE edge_attribute_value_id IN (SELECT id FROM edge_attribute_values WHERE edge_id IN (SELECT id FROM edges WHERE network_id = {network_id}))"))
        db.execute(text(f"DELETE FROM edge_attribute_values WHERE edge_id IN (SELECT id FROM edges WHERE network_id = {network_id})"))

        # Delete attributes
        db.execute(text(f"DELETE FROM node_attributes WHERE network_id = {network_id}"))
        db.execute(text(f"DELETE FROM edge_attributes WHERE network_id = {network_id}"))

        # Delete edges (references nodes)
        db.execute(text(f"DELETE FROM edges WHERE network_id = {network_id}"))
        
        # Delete nodes
        db.execute(text(f"DELETE FROM nodes WHERE network_id = {network_id}"))
        
        # Delete network
        db.execute(text(f"DELETE FROM networks WHERE id = {network_id}"))
        
        db.commit()
        print("Cleaned up old test data.")
    except Exception as e:
        print(f"Cleanup failed: {e}")
        db.rollback()
    
    # Dummy GraphML - minimal graph
    graphml = '''<?xml version="1.0" encoding="UTF-8"?>
<graphml xmlns="http://graphml.graphdrawing.org/xmlns"  
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xsi:schemaLocation="http://graphml.graphdrawing.org/xmlns
     http://graphml.graphdrawing.org/xmlns/1.0/graphml.xsd">
  <graph id="G" edgedefault="undirected">
    <node id="n0"/>
    <node id="n1"/>
    <node id="n2"/>
    <edge source="n0" target="n1"/>
    <edge source="n1" target="n2"/>
    <edge source="n2" target="n0"/>
  </graph>
</graphml>'''

    try:
        parse_and_save_graphml(network_id, graphml, db)
        print("Test graph created successfully.")
    except Exception as e:
        print(f"Failed to create test graph: {e}")
        return

    layouts_to_test = ["forceatlas2", "spiral", "fruchterman_reingold"]
    
    for layout_name in layouts_to_test:
        print(f"Testing layout: {layout_name}...")
        try:
            layout.calculate_layout(network_id, layout_name, db)
            
            # Verify basic x/y exists
            attr_x_name = f"{layout_name}_x"
            attr_y_name = f"{layout_name}_y"
            
            attr_x = db.query(models.NodeAttribute).filter(models.NodeAttribute.network_id == network_id, models.NodeAttribute.attribute_name == attr_x_name).first()
            attr_y = db.query(models.NodeAttribute).filter(models.NodeAttribute.network_id == network_id, models.NodeAttribute.attribute_name == attr_y_name).first()
            
            if attr_x and attr_y:
                vals_x = db.query(models.NodeFloatAttributeValue).join(models.NodeAttributeValue).filter(models.NodeAttributeValue.attribute_id == attr_x.id).count()
                if vals_x > 0:
                    print(f"SUCCESS: {layout_name} generated {vals_x} coordinate pairs.")
                else:
                     print(f"FAILURE: {layout_name} attributes created but NO values found.")
            else:
                print(f"FAILURE: {layout_name} attributes NOT found.")
                
        except Exception as e:
            print(f"FAILURE: {layout_name} raised exception: {e}")

if __name__ == "__main__":
    verify()
