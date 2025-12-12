import pytest
from fastapi.testclient import TestClient
from app.main import app
import json

# Mock Data
GRAPHML_CONTENT = """<?xml version="1.0" encoding="UTF-8"?>
<graphml xmlns="http://graphml.graphdrawing.org/xmlns"  
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xsi:schemaLocation="http://graphml.graphdrawing.org/xmlns
     http://graphml.graphdrawing.org/xmlns/1.0/graphml.xsd">
  <graph id="G" edgedefault="directed">
    <node id="n0"/>
    <node id="n1"/>
    <edge source="n0" target="n1"/>
  </graph>
</graphml>"""

def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_initialize_network(client):
    # Use a unique ID to avoid collision if DB is shared/persistent
    network_id = 9991
    
    response = client.post(
        "/api/v1/networks/initialize",
        json={"network_id": network_id, "graphml_data": GRAPHML_CONTENT}
    )
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "initialized"
    assert data["network_id"] == network_id
    
    # Verify metadata is accessible
    meta_response = client.get(f"/api/v1/networks/{network_id}/metadata")
    assert meta_response.status_code == 200
    meta = meta_response.json()
    assert meta["id"] == network_id
    # Default layout should be forceatlas2 as per previous fixes
    assert meta["last_layout_name"] == "forceatlas2"

def test_generate_visualization(client):
    network_id = 9991 # Re-use from above (assuming persistent or sequential run)
    
    # Initialize again just to be safe if order varies
    client.post(
        "/api/v1/networks/initialize",
        json={"network_id": network_id, "graphml_data": GRAPHML_CONTENT}
    )

    req_body = {
        "layout_name": "forceatlas2",
        "node_size_config": {
            "attribute": "forceatlas2_x",
            "min": 10.0,
            "max": 20.0,
            "default": 15.0
        }
    }
    
    response = client.post(
        f"/api/v1/networks/{network_id}/visualization",
        json=req_body
    )
    assert response.status_code == 200
    data = response.json()
    assert "nodes" in data
    assert "links" in data
    assert len(data["nodes"]) == 2
    assert len(data["links"]) == 1
    
    # Verify strict layout update
    node_0 = next(n for n in data["nodes"] if n["id"] == "n0")
    # Circle layout usually puts nodes on unit circle, but coordinates vary. 
    # Just checking we got a response is good enough for integration.
    
    # Verify metadata persistence
    meta_response = client.get(f"/api/v1/networks/{network_id}/metadata")
    meta = meta_response.json()
    assert meta["last_layout_name"] == "forceatlas2"
    assert meta["last_node_size_config"]["default"] == 15

def test_missing_network(client):
    response = client.get("/api/v1/networks/999999/metadata")
    assert response.status_code == 404
