"""
Tests for network endpoints.
"""

import pytest
from fastapi import status
from unittest.mock import patch, AsyncMock
import json
import io

def test_get_network_cytoscape_format_success(client, auth_headers, test_network):
    """Test getting network in Cytoscape format."""
    response = client.get(
        f"/network/{test_network.id}/cytoscape",
        headers=auth_headers
    )
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "elements" in data
    assert "nodes" in data["elements"]
    assert "edges" in data["elements"]

def test_get_network_cytoscape_format_not_found(client, auth_headers):
    """Test getting non-existent network."""
    response = client.get("/network/99999/cytoscape", headers=auth_headers)
    assert response.status_code == status.HTTP_404_NOT_FOUND

def test_get_network_cytoscape_format_unauthorized(client, test_network):
    """Test accessing network without authentication."""
    response = client.get(f"/network/{test_network.id}/cytoscape")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED

def test_export_network_graphml_success(client, auth_headers, test_network):
    """Test exporting network as GraphML file."""
    response = client.get(
        f"/network/{test_network.id}/export",
        headers=auth_headers
    )
    
    assert response.status_code == status.HTTP_200_OK
    assert response.headers["content-type"] == "application/xml; charset=utf-8"
    assert "attachment" in response.headers["content-disposition"]
    assert "graphml" in response.headers["content-disposition"]

def test_export_network_graphml_not_found(client, auth_headers):
    """Test exporting non-existent network."""
    response = client.get("/network/99999/export", headers=auth_headers)
    assert response.status_code == status.HTTP_404_NOT_FOUND

@patch('httpx.AsyncClient')
def test_upload_new_network_success(mock_client_class, client, auth_headers, sample_graphml, temp_file):
    """Test uploading a new network file."""
    # Mock the NetworkX MCP response
    mock_client = AsyncMock()
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "success": True,
        "graphml_content": sample_graphml
    }
    mock_client.post.return_value = mock_response
    mock_client_class.return_value.__aenter__.return_value = mock_client
    
    with open(temp_file, 'rb') as f:
        response = client.post(
            "/network/upload",
            headers=auth_headers,
            files={"file": ("test.graphml", f, "application/xml")}
        )
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "conversation_id" in data
    assert "network_id" in data

@patch('httpx.AsyncClient')
def test_upload_new_network_invalid_file_type(mock_client_class, client, auth_headers):
    """Test uploading invalid file type."""
    mock_client = AsyncMock()
    mock_client_class.return_value.__aenter__.return_value = mock_client
    
    # Create a temporary text file
    content = b"This is not a GraphML file"
    response = client.post(
        "/network/upload",
        headers=auth_headers,
        files={"file": ("test.txt", io.BytesIO(content), "text/plain")}
    )
    
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Invalid file type" in response.json()["detail"]

@patch('httpx.AsyncClient')
def test_upload_new_network_networkx_mcp_error(mock_client_class, client, auth_headers, temp_file):
    """Test upload when NetworkX MCP returns error."""
    # Mock NetworkX MCP error response
    mock_client = AsyncMock()
    mock_response = AsyncMock()
    mock_response.status_code = 500
    mock_response.text = "Internal server error"
    mock_client.post.return_value = mock_response
    mock_client_class.return_value.__aenter__.return_value = mock_client
    
    with open(temp_file, 'rb') as f:
        response = client.post(
            "/network/upload",
            headers=auth_headers,
            files={"file": ("test.graphml", f, "application/xml")}
        )
    
    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

@patch('httpx.AsyncClient')
def test_calculate_network_layout_success(mock_client_class, client, auth_headers, test_network):
    """Test calculating network layout."""
    # Mock NetworkX MCP response
    mock_client = AsyncMock()
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "result": {
            "success": True,
            "layout_type": "spring",
            "positions": {
                "1": {"x": 0.5, "y": 0.5},
                "2": {"x": 1.0, "y": 0.0},
                "3": {"x": 0.0, "y": 1.0}
            }
        }
    }
    mock_client.post.return_value = mock_response
    mock_client_class.return_value.__aenter__.return_value = mock_client
    
    response = client.post(
        f"/network/{test_network.id}/layout",
        headers=auth_headers,
        params={
            "layout_type": "spring",
            "layout_params": json.dumps({})
        }
    )
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["result"]["success"] is True
    assert "positions" in data["result"]

@patch('httpx.AsyncClient')
def test_calculate_network_layout_not_found(mock_client_class, client, auth_headers):
    """Test calculating layout for non-existent network."""
    mock_client = AsyncMock()
    mock_client_class.return_value.__aenter__.return_value = mock_client
    
    response = client.post(
        "/network/99999/layout",
        headers=auth_headers,
        params={"layout_type": "spring"}
    )
    
    assert response.status_code == status.HTTP_404_NOT_FOUND

@patch('httpx.AsyncClient')
def test_upload_and_overwrite_network_success(mock_client_class, client, auth_headers, test_conversation, sample_graphml, temp_file):
    """Test uploading file to overwrite existing network."""
    # Mock NetworkX MCP response
    mock_client = AsyncMock()
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "success": True,
        "graphml_content": sample_graphml
    }
    mock_client.post.return_value = mock_response
    mock_client_class.return_value.__aenter__.return_value = mock_client
    
    with open(temp_file, 'rb') as f:
        response = client.post(
            f"/network/{test_conversation.id}/upload",
            headers=auth_headers,
            files={"file": ("updated.graphml", f, "application/xml")}
        )
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["name"] == "updated.graphml"
    assert data["conversation_id"] == test_conversation.id

def test_upload_and_overwrite_network_no_conversation(client, auth_headers, temp_file):
    """Test uploading to non-existent conversation."""
    with open(temp_file, 'rb') as f:
        response = client.post(
            "/network/99999/upload",
            headers=auth_headers,
            files={"file": ("test.graphml", f, "application/xml")}
        )
    
    assert response.status_code == status.HTTP_404_NOT_FOUND

def test_network_access_different_user(client, db_session, test_network, test_user_data):
    """Test that users cannot access networks of other users."""
    import auth
    import models
    
    # Create another user
    other_user_data = {"username": "otheruser", "password": "otherpass"}
    hashed_password = auth.get_password_hash(other_user_data["password"])
    other_user = models.User(
        username=other_user_data["username"],
        hashed_password=hashed_password
    )
    db_session.add(other_user)
    db_session.commit()
    
    # Get token for other user
    response = client.post("/auth/token", data=other_user_data)
    token = response.json()["access_token"]
    other_headers = {"Authorization": f"Bearer {token}"}
    
    # Try to access original user's network
    response = client.get(
        f"/network/{test_network.id}/cytoscape",
        headers=other_headers
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN

def test_invalid_graphml_handling(client, auth_headers):
    """Test handling of invalid GraphML content."""
    invalid_content = b"This is not valid XML"
    
    response = client.post(
        "/network/upload",
        headers=auth_headers,
        files={"file": ("invalid.graphml", io.BytesIO(invalid_content), "application/xml")}
    )
    
    # This should either be handled by NetworkX MCP or result in an error
    assert response.status_code in [400, 500]

@patch('httpx.AsyncClient')
def test_layout_with_custom_parameters(mock_client_class, client, auth_headers, test_network):
    """Test layout calculation with custom parameters."""
    # Mock NetworkX MCP response
    mock_client = AsyncMock()
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "result": {
            "success": True,
            "layout_type": "circular",
            "positions": {
                "1": {"x": 0.0, "y": 1.0},
                "2": {"x": 0.866, "y": -0.5},
                "3": {"x": -0.866, "y": -0.5}
            }
        }
    }
    mock_client.post.return_value = mock_response
    mock_client_class.return_value.__aenter__.return_value = mock_client
    
    layout_params = {"scale": 2.0, "center": [0, 0]}
    
    response = client.post(
        f"/network/{test_network.id}/layout",
        headers=auth_headers,
        params={
            "layout_type": "circular",
            "layout_params": json.dumps(layout_params)
        }
    )
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["result"]["layout_type"] == "circular"
    
    # Verify that the correct parameters were sent to NetworkX MCP
    mock_client.post.assert_called_once()
    call_args = mock_client.post.call_args
    payload = call_args[1]["json"]
    assert payload["layout_type"] == "circular"
    assert payload["layout_params"] == layout_params