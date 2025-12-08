
import sys
import os
import httpx
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from app.core.database import SQLALCHEMY_DATABASE_URL
from app import models
from app.logic import importer
from fastapi.testclient import TestClient
from app.api.v1.endpoints.tools import router
from fastapi import FastAPI

# Create a dummy app to test the router
app = FastAPI()
app.include_router(router)
client = TestClient(app)

def verify_initial_upload():
    engine = create_engine(SQLALCHEMY_DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    network_id = 8888
    
    # Clean up
    try:
        db.execute(text(f"DELETE FROM node_float_attribute_values WHERE node_attribute_value_id IN (SELECT id FROM node_attribute_values WHERE node_id IN (SELECT id FROM nodes WHERE network_id = {network_id}))"))
        db.execute(text(f"DELETE FROM node_text_attribute_values WHERE node_attribute_value_id IN (SELECT id FROM node_attribute_values WHERE node_id IN (SELECT id FROM nodes WHERE network_id = {network_id}))"))
        db.execute(text(f"DELETE FROM node_attribute_values WHERE node_id IN (SELECT id FROM nodes WHERE network_id = {network_id})"))
        
        db.execute(text(f"DELETE FROM edge_float_attribute_values WHERE edge_attribute_value_id IN (SELECT id FROM edge_attribute_values WHERE edge_id IN (SELECT id FROM edges WHERE network_id = {network_id}))"))
        db.execute(text(f"DELETE FROM edge_text_attribute_values WHERE edge_attribute_value_id IN (SELECT id FROM edge_attribute_values WHERE edge_id IN (SELECT id FROM edges WHERE network_id = {network_id}))"))
        db.execute(text(f"DELETE FROM edge_attribute_values WHERE edge_id IN (SELECT id FROM edges WHERE network_id = {network_id})"))

        db.execute(text(f"DELETE FROM node_attributes WHERE network_id = {network_id}"))
        db.execute(text(f"DELETE FROM edge_attributes WHERE network_id = {network_id}"))

        db.execute(text(f"DELETE FROM edges WHERE network_id = {network_id}"))
        db.execute(text(f"DELETE FROM nodes WHERE network_id = {network_id}"))
        db.execute(text(f"DELETE FROM networks WHERE id = {network_id}"))
        
        db.commit()
    except Exception as e:
        print(f"Cleanup warning: {e}")
        db.rollback()

    graphml = '''<?xml version="1.0" encoding="UTF-8"?>
<graphml xmlns="http://graphml.graphdrawing.org/xmlns"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xsi:schemaLocation="http://graphml.graphdrawing.org/xmlns
     http://graphml.graphdrawing.org/xmlns/1.0/graphml.xsd">
  <graph id="G" edgedefault="undirected">
    <node id="n0"/>
    <node id="n1"/>
    <edge source="n0" target="n1"/>
  </graph>
</graphml>'''

    print("Calling initialize_network endpoint...")
    response = client.post(
        "/tools/initialize_network",
        json={"network_id": network_id, "graphml_data": graphml}
    )
    
    if response.status_code != 200:
        print(f"❌ Failed to initialize network: {response.text}")
        return

    data = response.json()
    new_network_id = data["network_id"]
    print(f"Network initialized with ID: {new_network_id}")

    # Check if forceatlas2_x/y attributes were created
    attr_x = db.query(models.NodeAttribute).filter(
        models.NodeAttribute.network_id == new_network_id, 
        models.NodeAttribute.attribute_name == "forceatlas2_x"
    ).first()
    
    if attr_x:
        print("✅ forceatlas2_x attribute found. Initialization used ForceAtlas2!")
        
        # Check for values
        count = db.query(models.NodeFloatAttributeValue)\
            .join(models.NodeAttributeValue)\
            .filter(models.NodeAttributeValue.attribute_id == attr_x.id)\
            .count()
            
        if count > 0:
             print(f"✅ Found {count} node positions calculated.")
        else:
             print("❌ Attribute exists but no values found!")
             
    else:
        print("❌ forceatlas2_x attribute NOT found. Default layout might still be Spring or something else.")

if __name__ == "__main__":
    verify_initial_upload()
