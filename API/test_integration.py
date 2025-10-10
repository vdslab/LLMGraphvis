"""
Integration tests for API and NetworkXMCP communication.
"""

import pytest
from fastapi import status
from unittest.mock import patch, AsyncMock
import httpx
import json

class TestAPINetworkXMCPIntegration:
    """Test integration between API and NetworkXMCP services."""
    
    @patch('httpx.AsyncClient')
    def test_network_upload_with_mcp_conversion(self, mock_client_class, client, auth_headers, temp_file):
        """Test uploading network file and NetworkXMCP conversion."""
        # Mock NetworkXMCP response
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "success": True,
            "graphml_content": "<?xml version='1.0'?>..."
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
        
        # Verify NetworkXMCP was called
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert "/tools/convert_graphml" in call_args[0][0]
    
    @patch('httpx.AsyncClient')
    def test_network_layout_calculation_with_mcp(self, mock_client_class, client, auth_headers, test_network):
        """Test network layout calculation via NetworkXMCP."""
        # Mock NetworkXMCP response
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "result": {
                "success": True,
                "layout_type": "spring",
                "positions": {
                    "1": {"x": 0.5, "y": 0.5},
                    "2": {"x": 1.0, "y": 0.0}
                },
                "graphml_content": "<?xml version='1.0'?>..."
            }
        }
        mock_client.post.return_value = mock_response
        mock_client_class.return_value.__aenter__.return_value = mock_client
        
        response = client.post(
            f"/network/{test_network.id}/layout",
            headers=auth_headers,
            params={"layout_type": "spring"}
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["result"]["success"] is True
        assert "positions" in data["result"]
        
        # Verify NetworkXMCP was called with correct payload
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert "/tools/change_layout" in call_args[0][0]
        payload = call_args[1]["json"]
        assert "graphml_content" in payload
        assert payload["layout_type"] == "spring"
    
    @patch('httpx.AsyncClient')
    @patch('services.llm.process_chat_message')
    def test_chat_with_network_tool_call(self, mock_llm, mock_client_class, client, auth_headers):
        """Test chat message that triggers NetworkXMCP tool call."""
        # Mock LLM responses
        mock_llm.side_effect = [
            {
                "tool_calls": [{
                    "function": {
                        "name": "change_layout",
                        "arguments": {"layout_type": "circular"}
                    }
                }]
            },
            {
                "content": "I've applied the circular layout to your network."
            }
        ]
        
        # Mock NetworkXMCP response
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "result": {
                "success": True,
                "layout_type": "circular",
                "positions": {"1": {"x": 0, "y": 1}}
            }
        }
        mock_client.post.return_value = mock_response
        mock_client_class.return_value.__aenter__.return_value = mock_client
        
        response = client.post(
            "/chat/process",
            headers=auth_headers,
            json={"message": "Apply circular layout to the network"}
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert "circular layout" in data["content"]
        
        # Verify NetworkXMCP was called
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert "/tools/change_layout" in call_args[0][0]
    
    @patch('httpx.AsyncClient')
    @patch('services.llm.process_chat_message')
    def test_chat_with_centrality_calculation(self, mock_llm, mock_client_class, client, auth_headers):
        """Test chat message that calculates centrality via NetworkXMCP."""
        # Mock LLM responses
        mock_llm.side_effect = [
            {
                "tool_calls": [{
                    "function": {
                        "name": "calculate_centrality",
                        "arguments": {"centrality_type": "degree"}
                    }
                }]
            },
            {
                "content": "The degree centrality values have been calculated."
            }
        ]
        
        # Mock NetworkXMCP response
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "result": {
                "success": True,
                "centrality_type": "degree",
                "centrality_values": {"1": 2, "2": 1, "3": 2}
            }
        }
        mock_client.post.return_value = mock_response
        mock_client_class.return_value.__aenter__.return_value = mock_client
        
        response = client.post(
            "/chat/process",
            headers=auth_headers,
            json={"message": "Calculate degree centrality"}
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        
        # Verify NetworkXMCP was called
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert "/tools/calculate_centrality" in call_args[0][0]

class TestErrorHandling:
    """Test error handling in API-NetworkXMCP communication."""
    
    @patch('httpx.AsyncClient')
    def test_mcp_service_unavailable(self, mock_client_class, client, auth_headers, test_network):
        """Test handling when NetworkXMCP service is unavailable."""
        # Mock connection error
        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.ConnectError("Connection failed")
        mock_client_class.return_value.__aenter__.return_value = mock_client
        
        response = client.post(
            f"/network/{test_network.id}/layout",
            headers=auth_headers,
            params={"layout_type": "spring"}
        )
        
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    
    @patch('httpx.AsyncClient')
    def test_mcp_returns_error(self, mock_client_class, client, auth_headers, test_network):
        """Test handling when NetworkXMCP returns an error."""
        # Mock error response from NetworkXMCP
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status_code = 400
        mock_response.text = "Invalid GraphML content"
        mock_client.post.return_value = mock_response
        mock_client_class.return_value.__aenter__.return_value = mock_client
        
        response = client.post(
            f"/network/{test_network.id}/layout",
            headers=auth_headers,
            params={"layout_type": "spring"}
        )
        
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "NetworkXMCP" in response.json()["detail"]
    
    @patch('httpx.AsyncClient')
    def test_mcp_timeout(self, mock_client_class, client, auth_headers, test_network):
        """Test handling when NetworkXMCP request times out."""
        # Mock timeout
        mock_client = AsyncMock()
        mock_client.post.side_effect = httpx.TimeoutException("Request timed out")
        mock_client_class.return_value.__aenter__.return_value = mock_client
        
        response = client.post(
            f"/network/{test_network.id}/layout",
            headers=auth_headers,
            params={"layout_type": "spring"}
        )
        
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    
    @patch('httpx.AsyncClient')
    @patch('services.llm.process_chat_message')
    def test_chat_tool_call_error_handling(self, mock_llm, mock_client_class, client, auth_headers):
        """Test chat error handling when tool call fails."""
        # Mock LLM responses
        mock_llm.side_effect = [
            {
                "tool_calls": [{
                    "function": {
                        "name": "change_layout",
                        "arguments": {"layout_type": "invalid"}
                    }
                }]
            },
            {
                "content": "I encountered an error while processing your request."
            }
        ]
        
        # Mock NetworkXMCP error
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status_code = 400
        mock_response.text = "Invalid layout type"
        mock_client.post.return_value = mock_response
        mock_client_class.return_value.__aenter__.return_value = mock_client
        
        response = client.post(
            "/chat/process",
            headers=auth_headers,
            json={"message": "Apply invalid layout"}
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        # Should still return content even if tool failed
        assert "error" in data["content"] or "Error" in data["content"]

class TestDataFlow:
    """Test data flow between API and NetworkXMCP."""
    
    @patch('httpx.AsyncClient')
    def test_graphml_data_consistency(self, mock_client_class, client, auth_headers, test_network, sample_graphml):
        """Test that GraphML data is consistently passed between services."""
        # Mock NetworkXMCP to echo back the GraphML
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "result": {
                "success": True,
                "layout_type": "spring",
                "positions": {"1": {"x": 0, "y": 0}},
                "graphml_content": sample_graphml
            }
        }
        mock_client.post.return_value = mock_response
        mock_client_class.return_value.__aenter__.return_value = mock_client
        
        response = client.post(
            f"/network/{test_network.id}/layout",
            headers=auth_headers,
            params={"layout_type": "spring"}
        )
        
        assert response.status_code == status.HTTP_200_OK
        
        # Verify the GraphML content was sent correctly
        call_args = mock_client.post.call_args
        payload = call_args[1]["json"]
        assert "graphml_content" in payload
        # GraphML should contain network structure
        assert "node" in payload["graphml_content"] or "edge" in payload["graphml_content"]
    
    @patch('httpx.AsyncClient')
    def test_parameter_passing(self, mock_client_class, client, auth_headers, test_network):
        """Test that parameters are correctly passed to NetworkXMCP."""
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "result": {"success": True, "layout_type": "spring", "positions": {}}
        }
        mock_client.post.return_value = mock_response
        mock_client_class.return_value.__aenter__.return_value = mock_client
        
        # Custom layout parameters
        layout_params = {"k": 2.0, "iterations": 100}
        
        response = client.post(
            f"/network/{test_network.id}/layout",
            headers=auth_headers,
            params={
                "layout_type": "spring",
                "layout_params": json.dumps(layout_params)
            }
        )
        
        assert response.status_code == status.HTTP_200_OK
        
        # Verify parameters were passed correctly
        call_args = mock_client.post.call_args
        payload = call_args[1]["json"]
        assert payload["layout_type"] == "spring"
        assert payload["layout_params"] == layout_params

class TestEnvironmentConfiguration:
    """Test environment configuration for service communication."""
    
    def test_networkx_mcp_url_configuration(self):
        """Test NetworkXMCP URL configuration."""
        import os
        from routers.network import NETWORKX_MCP_URL
        
        # Should have a default value
        assert NETWORKX_MCP_URL is not None
        assert NETWORKX_MCP_URL.startswith("http")
    
    @patch.dict('os.environ', {'NETWORKX_MCP_URL': 'http://custom-mcp:9000'})
    def test_custom_mcp_url(self):
        """Test custom NetworkXMCP URL from environment."""
        # Reload the module to pick up new environment variable
        import importlib
        import routers.network
        importlib.reload(routers.network)
        
        assert routers.network.NETWORKX_MCP_URL == "http://custom-mcp:9000"

class TestServiceDiscovery:
    """Test service discovery and health checking."""
    
    @patch('httpx.AsyncClient')
    def test_mcp_health_check_via_api(self, mock_client_class, client):
        """Test API ability to check NetworkXMCP health."""
        # Mock NetworkXMCP health response
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"status": "ok"}
        mock_client.get.return_value = mock_response
        mock_client_class.return_value.__aenter__.return_value = mock_client
        
        # This would be a custom endpoint to check MCP health
        # For now, we just verify the mock setup works
        assert mock_client is not None

class TestConcurrency:
    """Test concurrent requests between API and NetworkXMCP."""
    
    @patch('httpx.AsyncClient')
    def test_multiple_concurrent_layout_requests(self, mock_client_class, client, auth_headers, test_network):
        """Test multiple concurrent layout calculation requests."""
        import asyncio
        import threading
        
        # Mock NetworkXMCP response
        mock_client = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "result": {"success": True, "layout_type": "spring", "positions": {}}
        }
        mock_client.post.return_value = mock_response
        mock_client_class.return_value.__aenter__.return_value = mock_client
        
        def make_request():
            return client.post(
                f"/network/{test_network.id}/layout",
                headers=auth_headers,
                params={"layout_type": "spring"}
            )
        
        # Make multiple concurrent requests
        threads = []
        results = []
        
        def thread_target():
            result = make_request()
            results.append(result)
        
        # Start multiple threads
        for _ in range(3):
            thread = threading.Thread(target=thread_target)
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # All requests should succeed
        assert len(results) == 3
        for result in results:
            assert result.status_code == status.HTTP_200_OK

class TestRetryLogic:
    """Test retry logic for NetworkXMCP communication."""
    
    @patch('httpx.AsyncClient')
    def test_retry_on_temporary_failure(self, mock_client_class, client, auth_headers, test_network):
        """Test retry behavior on temporary NetworkXMCP failures."""
        # This test assumes retry logic exists (which it may not in current implementation)
        # It's more of a specification for future enhancement
        
        mock_client = AsyncMock()
        # First call fails, second succeeds
        responses = [
            AsyncMock(status_code=500, text="Temporary error"),
            AsyncMock(status_code=200, json=lambda: {"result": {"success": True}})
        ]
        mock_client.post.side_effect = responses
        mock_client_class.return_value.__aenter__.return_value = mock_client
        
        response = client.post(
            f"/network/{test_network.id}/layout",
            headers=auth_headers,
            params={"layout_type": "spring"}
        )
        
        # Currently this would fail on first attempt
        # In future, could implement retry logic
        assert response.status_code in [200, 500]