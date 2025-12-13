from fastapi.testclient import TestClient
from app.main import app
import pytest

client = TestClient(app)

# Assuming network ID 1 exists from previous tests or seed data
# If not, we might need to create one, but let's try with 1 first or use the logic from other tests

def test_get_node_details_success():
    # 1. Create a network
    graphml_data = """<?xml version="1.0" encoding="UTF-8"?>
<graphml xmlns="http://graphml.graphdrawing.org/xmlns">
    <key id="d0" for="node" attr.name="color" attr.type="string"/>
    <key id="d1" for="node" attr.name="description" attr.type="string"/>
    <graph id="G" edgedefault="undirected">
        <node id="n0">
            <data key="d0">red</data>
            <data key="d1">This is a test node</data>
        </node>
    </graph>
</graphml>"""
    
    response = client.post("/api/v1/networks/initialize", json={"network_id": 999, "graphml_data": graphml_data})
    assert response.status_code == 200
    network_id = response.json()["network_id"]

    # 2. Get details for node n0
    response = client.get(f"/api/v1/networks/{network_id}/nodes/n0")
    assert response.status_code == 200
    data = response.json()
    
    assert data["id"] == "n0"
    assert data["attributes"]["color"] == "red"
    assert data["attributes"]["description"] == "This is a test node"
    assert data["description"] == "This is a test node"

def test_get_node_details_not_found():
    # Use a likely non-existent network ID or node ID
    response = client.get("/api/v1/networks/999/nodes/non_existent_node")
    assert response.status_code == 404
