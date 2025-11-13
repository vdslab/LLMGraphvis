"""
Unit tests for network visualization data endpoint.

This module tests the network visualization data endpoint that generates
rendering data from GraphML content.
"""

import pytest
from unittest.mock import patch, MagicMock
import networkx as nx
import io
import json
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)

@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    mock_session = MagicMock()
    return mock_session

@pytest.fixture
def mock_current_user():
    """Create a mock authenticated user."""
    user = MagicMock()
    user.id = 1
    user.username = "testuser"
    return user

@pytest.fixture
def sample_network():
    """Create a sample network for testing."""
    network = MagicMock()
    network.id = 123
    
    # Sample GraphML content with position and visual attributes
    network.graphml_content = """<?xml version="1.0" encoding="UTF-8"?>
<graphml xmlns="http://graphml.graphdrawing.org/xmlns">
  <key id="d0" for="node" attr.name="name" attr.type="string"/>
  <key id="d1" for="node" attr.name="size" attr.type="double"/>
  <key id="d2" for="node" attr.name="color" attr.type="string"/>
  <key id="d3" for="node" attr.name="x" attr.type="double"/>
  <key id="d4" for="node" attr.name="y" attr.type="double"/>
  <key id="d5" for="edge" attr.name="width" attr.type="double"/>
  <key id="d6" for="edge" attr.name="color" attr.type="string"/>
  <graph edgedefault="undirected">
    <node id="1">
      <data key="d0">Node 1</data>
      <data key="d1">7.5</data>
      <data key="d2">#ff0000</data>
      <data key="d3">0.1</data>
      <data key="d4">0.2</data>
    </node>
    <node id="2">
      <data key="d0">Node 2</data>
      <data key="d1">5.0</data>
      <data key="d2">#00ff00</data>
      <data key="d3">0.8</data>
      <data key="d4">0.9</data>
    </node>
    <node id="3">
      <data key="d0">Node 3</data>
      <data key="d3">0.5</data>
      <data key="d4">0.5</data>
    </node>
    <edge source="1" target="2">
      <data key="d5">2.0</data>
      <data key="d6">#0000ff</data>
    </edge>
    <edge source="2" target="3">
      <data key="d5">1.0</data>
      <data key="d6">#cccccc</data>
    </edge>
    <edge source="3" target="1"/>
  </graph>
</graphml>"""
    
    # Mock the conversation relationship
    conversation = MagicMock()
    conversation.user_id = 1
    network.conversation = conversation
    
    return network

@pytest.mark.asyncio
async def test_get_network_visualization_data(
    mock_db_session, 
    mock_current_user,
    sample_network
):
    """
    Test that the visualization data endpoint returns properly formatted data.
    
    This test verifies that:
    1. The GraphML is correctly parsed
    2. Node and edge attributes are properly extracted
    3. Default values are applied where attributes are missing
    4. The response format matches the expected structure
    """
    # Mock the database query to return the sample network
    mock_db_session.query.return_value.filter.return_value.first.return_value = sample_network
    
    # Mock the dependencies
    with patch('routers.network.get_db', return_value=mock_db_session):
        with patch('auth.get_current_user', return_value=mock_current_user):
            # Call the endpoint
            from routers.network import get_network_visualization_data
            response = await get_network_visualization_data(
                network_id=123,
                current_user=mock_current_user,
                db=mock_db_session
            )
            
            # Verify the response structure
            assert "nodes" in response
            assert "links" in response
            
            # Verify the nodes data
            nodes = response["nodes"]
            assert len(nodes) == 3
            
            # Check node 1 with all attributes
            node1 = next(node for node in nodes if node["id"] == "1")
            assert node1["label"] == "Node 1"
            assert node1["size"] == 7.5
            assert node1["color"] == "#ff0000"
            assert node1["x"] == 0.1
            assert node1["y"] == 0.2
            
            # Check node 2 with all attributes
            node2 = next(node for node in nodes if node["id"] == "2")
            assert node2["label"] == "Node 2"
            assert node2["size"] == 5.0
            assert node2["color"] == "#00ff00"
            assert node2["x"] == 0.8
            assert node2["y"] == 0.9
            
            # Check node 3 with default values for missing attributes
            node3 = next(node for node in nodes if node["id"] == "3")
            assert node3["label"] == "Node 3"
            assert node3["size"] == 5  # Default value
            assert node3["color"] == "#82b3ff"  # Default value
            assert node3["x"] == 0.5
            assert node3["y"] == 0.5
            
            # Verify the links data
            links = response["links"]
            assert len(links) == 3
            
            # Check edge 1-2 with all attributes
            edge1_2 = next(edge for edge in links if edge["source"] == "1" and edge["target"] == "2")
            assert edge1_2["width"] == 2.0
            assert edge1_2["color"] == "#0000ff"
            
            # Check edge 2-3 with all attributes
            edge2_3 = next(edge for edge in links if edge["source"] == "2" and edge["target"] == "3")
            assert edge2_3["width"] == 1.0
            assert edge2_3["color"] == "#cccccc"
            
            # Check edge 3-1 with default values
            edge3_1 = next(edge for edge in links if edge["source"] == "3" and edge["target"] == "1")
            assert edge3_1["width"] == 1  # Default value
            assert edge3_1["color"] == "#cccccc"  # Default value

@pytest.mark.asyncio
async def test_get_network_visualization_data_not_found(
    mock_db_session, 
    mock_current_user
):
    """
    Test that the visualization data endpoint returns 404 when network is not found.
    """
    # Mock the database query to return None
    mock_db_session.query.return_value.filter.return_value.first.return_value = None
    
    # Mock the dependencies
    with patch('routers.network.get_db', return_value=mock_db_session):
        with patch('auth.get_current_user', return_value=mock_current_user):
            # Call the endpoint and expect an exception
            from routers.network import get_network_visualization_data
            from fastapi import HTTPException
            
            with pytest.raises(HTTPException) as excinfo:
                await get_network_visualization_data(
                    network_id=999,
                    current_user=mock_current_user,
                    db=mock_db_session
                )
            
            # Verify the exception
            assert excinfo.value.status_code == 404
            assert "Network not found" in str(excinfo.value.detail)

@pytest.mark.asyncio
async def test_get_network_visualization_data_unauthorized(
    mock_db_session, 
    mock_current_user,
    sample_network
):
    """
    Test that the visualization data endpoint returns 403 when user is not authorized.
    """
    # Modify the sample network to have a different user
    sample_network.conversation.user_id = 999  # Different from mock_current_user.id
    
    # Mock the database query to return the sample network
    mock_db_session.query.return_value.filter.return_value.first.return_value = sample_network
    
    # Mock the dependencies
    with patch('routers.network.get_db', return_value=mock_db_session):
        with patch('auth.get_current_user', return_value=mock_current_user):
            # Call the endpoint and expect an exception
            from routers.network import get_network_visualization_data
            from fastapi import HTTPException
            
            with pytest.raises(HTTPException) as excinfo:
                await get_network_visualization_data(
                    network_id=123,
                    current_user=mock_current_user,
                    db=mock_db_session
                )
            
            # Verify the exception
            assert excinfo.value.status_code == 403
            assert "Not authorized" in str(excinfo.value.detail)