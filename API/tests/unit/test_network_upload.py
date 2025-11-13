"""
Unit tests for network upload functionality.

This module tests the network upload endpoint and its integration with
the NetworkXMCP service for layout calculation.
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import io
from fastapi import UploadFile
from fastapi.testclient import TestClient

from main import app
from services import mcp_client

client = TestClient(app)

@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    mock_session = MagicMock()
    mock_session.commit = MagicMock()
    mock_session.refresh = MagicMock()
    mock_session.add = MagicMock()
    return mock_session

@pytest.fixture
def mock_current_user():
    """Create a mock authenticated user."""
    user = MagicMock()
    user.id = 1
    user.username = "testuser"
    return user

@pytest.fixture
def mock_get_db():
    """Mock the get_db dependency."""
    def _get_db():
        return MagicMock()
    return _get_db

@pytest.fixture
def mock_get_current_user():
    """Mock the get_current_user dependency."""
    async def _get_current_user():
        user = MagicMock()
        user.id = 1
        user.username = "testuser"
        return user
    return _get_current_user

@pytest.fixture
def sample_graphml():
    """Sample GraphML content for testing."""
    return """<?xml version="1.0" encoding="UTF-8"?>
<graphml xmlns="http://graphml.graphdrawing.org/xmlns">
  <graph edgedefault="undirected">
    <node id="1"/>
    <node id="2"/>
    <edge source="1" target="2"/>
  </graph>
</graphml>"""

@pytest.mark.asyncio
async def test_upload_new_network_with_layout_calculation(
    mock_db_session, 
    mock_current_user, 
    sample_graphml
):
    """
    Test that uploading a new network triggers layout calculation.
    
    This test verifies that:
    1. The GraphML file is properly converted
    2. A new conversation and network are created
    3. The default spring layout is calculated
    """
    # Mock the convert_graphml function
    with patch.object(
        mcp_client, 
        'convert_graphml', 
        new_callable=AsyncMock
    ) as mock_convert:
        mock_convert.return_value = {
            "success": True,
            "graphml_content": sample_graphml
        }
        
        # Mock the change_layout function
        with patch.object(
            mcp_client, 
            'change_layout', 
            new_callable=AsyncMock
        ) as mock_layout:
            mock_layout.return_value = {
                "result": {
                    "success": True,
                    "layout_type": "spring",
                    "positions": {
                        "1": {"x": 0.1, "y": 0.2},
                        "2": {"x": 0.8, "y": 0.9}
                    }
                }
            }
            
            # Mock the database session and dependencies
            with patch('routers.network.get_db', return_value=mock_db_session):
                with patch('auth.get_current_user', return_value=mock_current_user):
                    # Create a mock file
                    file_content = sample_graphml.encode('utf-8')
                    file = UploadFile(
                        filename="test.graphml",
                        file=io.BytesIO(file_content)
                    )
                    
                    # Mock the conversation and network objects
                    mock_conversation = MagicMock()
                    mock_conversation.id = 123
                    mock_db_session.add.return_value = None
                    mock_db_session.refresh.side_effect = [mock_conversation]
                    
                    mock_network = MagicMock()
                    mock_network.id = 456
                    mock_db_session.refresh.side_effect = [mock_conversation, mock_network]
                    
                    # Call the endpoint
                    from routers.network import upload_new_network
                    response = await upload_new_network(
                        file=file,
                        current_user=mock_current_user,
                        db=mock_db_session
                    )
                    
                    # Verify the response
                    assert response["conversation_id"] == mock_conversation.id
                    assert response["network_id"] == mock_network.id
                    
                    # Verify that convert_graphml was called
                    mock_convert.assert_called_once()
                    
                    # Verify that change_layout was called with the correct parameters
                    mock_layout.assert_called_once()
                    args, kwargs = mock_layout.call_args
                    assert kwargs.get("layout_type") == "spring"

@pytest.mark.asyncio
async def test_upload_new_network_with_layout_calculation_error(
    mock_db_session, 
    mock_current_user, 
    sample_graphml
):
    """
    Test that network upload succeeds even if layout calculation fails.
    
    This test verifies that:
    1. The GraphML file is properly converted
    2. A new conversation and network are created
    3. The layout calculation fails but the upload still succeeds
    """
    # Mock the convert_graphml function
    with patch.object(
        mcp_client, 
        'convert_graphml', 
        new_callable=AsyncMock
    ) as mock_convert:
        mock_convert.return_value = {
            "success": True,
            "graphml_content": sample_graphml
        }
        
        # Mock the change_layout function to raise an exception
        with patch.object(
            mcp_client, 
            'change_layout', 
            new_callable=AsyncMock
        ) as mock_layout:
            mock_layout.side_effect = mcp_client.MCPError(
                message="Layout calculation failed",
                status_code=500
            )
            
            # Mock the database session and dependencies
            with patch('routers.network.get_db', return_value=mock_db_session):
                with patch('auth.get_current_user', return_value=mock_current_user):
                    # Create a mock file
                    file_content = sample_graphml.encode('utf-8')
                    file = UploadFile(
                        filename="test.graphml",
                        file=io.BytesIO(file_content)
                    )
                    
                    # Mock the conversation and network objects
                    mock_conversation = MagicMock()
                    mock_conversation.id = 123
                    mock_db_session.add.return_value = None
                    mock_db_session.refresh.side_effect = [mock_conversation]
                    
                    mock_network = MagicMock()
                    mock_network.id = 456
                    mock_db_session.refresh.side_effect = [mock_conversation, mock_network]
                    
                    # Call the endpoint
                    from routers.network import upload_new_network
                    response = await upload_new_network(
                        file=file,
                        current_user=mock_current_user,
                        db=mock_db_session
                    )
                    
                    # Verify the response - upload should still succeed
                    assert response["conversation_id"] == mock_conversation.id
                    assert response["network_id"] == mock_network.id
                    
                    # Verify that convert_graphml was called
                    mock_convert.assert_called_once()
                    
                    # Verify that change_layout was called
                    mock_layout.assert_called_once()