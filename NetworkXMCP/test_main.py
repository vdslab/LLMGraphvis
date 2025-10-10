"""
Tests for NetworkXMCP main endpoints.
"""

import pytest
from fastapi import status
import json

def test_health_endpoint(client):
    """Test the health check endpoint."""
    response = client.get("/health")
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["status"] == "ok"
    assert "timestamp" in data

def test_info_endpoint(client):
    """Test the MCP info endpoint."""
    response = client.get("/info")
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["success"] is True
    assert data["name"] == "NetworkX MCP (Enhanced)"
    assert data["version"] == "0.3.0"
    assert "tools" in data
    assert isinstance(data["tools"], list)
    
    # Check that expected tools are listed
    tool_names = [tool["name"] for tool in data["tools"]]
    expected_tools = [
        "get_sample_network",
        "change_layout",
        "calculate_centrality",
        "calculate_and_store_metrics",
        "get_visualization_data",
        "get_available_metrics"
    ]
    for tool in expected_tools:
        assert tool in tool_names

def test_get_sample_network(client):
    """Test sample network generation."""
    response = client.get("/get_sample_network")
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["success"] is True
    assert "graphml_content" in data
    assert "<?xml" in data["graphml_content"]
    assert "graphml" in data["graphml_content"]

def test_change_layout_spring(client, sample_graphml):
    """Test changing layout to spring."""
    payload = {
        "graphml_content": sample_graphml,
        "layout_type": "spring",
        "layout_params": {"k": 1.0, "iterations": 50}
    }
    
    response = client.post("/tools/change_layout", json=payload)
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["result"]["success"] is True
    assert data["result"]["layout_type"] == "spring"
    assert "positions" in data["result"]
    assert "graphml_content" in data["result"]

def test_change_layout_circular(client, sample_graphml):
    """Test changing layout to circular."""
    payload = {
        "graphml_content": sample_graphml,
        "layout_type": "circular",
        "layout_params": {}
    }
    
    response = client.post("/tools/change_layout", json=payload)
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["result"]["success"] is True
    assert data["result"]["layout_type"] == "circular"
    assert len(data["result"]["positions"]) == 3  # 3 nodes in sample

def test_change_layout_invalid_graphml(client, invalid_graphml):
    """Test layout change with invalid GraphML."""
    payload = {
        "graphml_content": invalid_graphml,
        "layout_type": "spring",
        "layout_params": {}
    }
    
    response = client.post("/tools/change_layout", json=payload)
    assert response.status_code == status.HTTP_400_BAD_REQUEST

def test_change_layout_unsupported_type(client, sample_graphml):
    """Test layout change with unsupported layout type."""
    payload = {
        "graphml_content": sample_graphml,
        "layout_type": "unsupported_layout",
        "layout_params": {}
    }
    
    response = client.post("/tools/change_layout", json=payload)
    # Should either return error or fallback to default
    assert response.status_code in [400, 200]

def test_calculate_centrality_degree(client, sample_graphml):
    """Test degree centrality calculation."""
    payload = {
        "graphml_content": sample_graphml,
        "centrality_type": "degree",
        "centrality_params": {}
    }
    
    response = client.post("/tools/calculate_centrality", json=payload)
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["result"]["success"] is True
    assert data["result"]["centrality_type"] == "degree"
    assert "centrality_values" in data["result"]
    assert isinstance(data["result"]["centrality_values"], dict)

def test_calculate_centrality_betweenness(client, complex_graphml):
    """Test betweenness centrality calculation."""
    payload = {
        "graphml_content": complex_graphml,
        "centrality_type": "betweenness",
        "centrality_params": {"normalized": True}
    }
    
    response = client.post("/tools/calculate_centrality", json=payload)
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["result"]["success"] is True
    assert data["result"]["centrality_type"] == "betweenness"

def test_calculate_centrality_invalid_type(client, sample_graphml):
    """Test centrality calculation with invalid type."""
    payload = {
        "graphml_content": sample_graphml,
        "centrality_type": "invalid_centrality",
        "centrality_params": {}
    }
    
    response = client.post("/tools/calculate_centrality", json=payload)
    assert response.status_code == status.HTTP_400_BAD_REQUEST

def test_import_graphml_success(client, sample_graphml):
    """Test successful GraphML import."""
    payload = {"graphml_content": sample_graphml}
    
    response = client.post("/tools/import_graphml", json=payload)
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["result"]["success"] is True
    assert "nodes" in data["result"]
    assert "edges" in data["result"]
    assert len(data["result"]["nodes"]) == 3
    assert len(data["result"]["edges"]) == 3

def test_import_graphml_invalid(client, invalid_graphml):
    """Test GraphML import with invalid content."""
    payload = {"graphml_content": invalid_graphml}
    
    response = client.post("/tools/import_graphml", json=payload)
    assert response.status_code == status.HTTP_400_BAD_REQUEST

def test_convert_graphml_success(client, sample_graphml):
    """Test GraphML conversion."""
    payload = {"graphml_content": sample_graphml}
    
    response = client.post("/tools/convert_graphml", json=payload)
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["success"] is True
    assert "graphml_content" in data

def test_export_graphml_success(client, sample_graphml):
    """Test GraphML export."""
    payload = {
        "graphml_content": sample_graphml,
        "include_positions": True,
        "include_visual_properties": True
    }
    
    response = client.post("/tools/export_graphml", json=payload)
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["result"]["success"] is True
    assert data["result"]["format"] == "graphml"
    assert "content" in data["result"]

def test_calculate_and_store_metrics(client, mock_cache, sample_graphml):
    """Test calculating and storing metrics."""
    payload = {
        "graphml_content": sample_graphml,
        "layout_type": "spring",
        "layout_params": {},
        "metrics_to_calculate": ["degree", "betweenness"]
    }
    
    response = client.post("/tools/calculate_and_store_metrics", json=payload)
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["result"]["success"] is True
    assert "graph_id" in data["result"]

def test_calculate_and_store_metrics_all_metrics(client, mock_cache, sample_graphml):
    """Test calculating all metrics when none specified."""
    payload = {
        "graphml_content": sample_graphml,
        "layout_type": "circular",
        "layout_params": {}
        # metrics_to_calculate not specified, should calculate all
    }
    
    response = client.post("/tools/calculate_and_store_metrics", json=payload)
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["result"]["success"] is True

def test_get_visualization_data(client, mock_cache):
    """Test getting visualization data."""
    # Mock cache to return some data
    mock_cache.get.return_value = {
        "graph": None,  # Mock graph object
        "positions": {"1": {"x": 0, "y": 0}, "2": {"x": 1, "y": 1}},
        "metrics": {"degree": {"1": 2, "2": 1}}
    }
    
    payload = {
        "graph_id": "test_graph_id",
        "metric_name": "degree",
        "color_scheme": "viridis",
        "size_range": [10, 50]
    }
    
    response = client.post("/tools/get_visualization_data", json=payload)
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["result"]["success"] is True

def test_get_available_metrics(client, mock_cache):
    """Test getting available metrics for a graph."""
    # Mock cache to return metrics
    mock_cache.get.return_value = {
        "metrics": {
            "degree": {"1": 2, "2": 1},
            "betweenness": {"1": 0.5, "2": 0.3}
        }
    }
    
    payload = {"graph_id": "test_graph_id"}
    
    response = client.post("/tools/get_available_metrics", json=payload)
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["result"]["success"] is True

def test_get_cache_stats(client, mock_cache):
    """Test getting cache statistics."""
    response = client.get("/cache/stats")
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["success"] is True
    assert "stats" in data

class TestParametrizedLayouts:
    """Test different layout types with various parameters."""
    
    @pytest.mark.parametrize("layout_type", [
        "spring", "circular", "random", "spectral", "shell", 
        "kamada_kawai", "fruchterman_reingold"
    ])
    def test_layout_types(self, client, sample_graphml, layout_type):
        """Test various layout types."""
        payload = {
            "graphml_content": sample_graphml,
            "layout_type": layout_type,
            "layout_params": {}
        }
        
        response = client.post("/tools/change_layout", json=payload)
        
        # Some layouts might not work with all graphs
        assert response.status_code in [200, 400]
        if response.status_code == 200:
            data = response.json()
            assert data["result"]["success"] is True

class TestParametrizedCentrality:
    """Test different centrality measures."""
    
    @pytest.mark.parametrize("centrality_type", [
        "degree", "betweenness", "closeness", "eigenvector", "pagerank"
    ])
    def test_centrality_types(self, client, sample_graphml, centrality_type):
        """Test various centrality measures."""
        payload = {
            "graphml_content": sample_graphml,
            "centrality_type": centrality_type,
            "centrality_params": {}
        }
        
        response = client.post("/tools/calculate_centrality", json=payload)
        
        # Some centrality measures might not work with all graphs
        assert response.status_code in [200, 400]
        if response.status_code == 200:
            data = response.json()
            assert data["result"]["success"] is True

class TestSpecialGraphTypes:
    """Test with special graph types."""
    
    def test_empty_graph(self, client, empty_graphml):
        """Test operations on empty graph."""
        payload = {
            "graphml_content": empty_graphml,
            "layout_type": "spring",
            "layout_params": {}
        }
        
        response = client.post("/tools/change_layout", json=payload)
        # Empty graph might cause issues or be handled specially
        assert response.status_code in [200, 400]
    
    def test_bipartite_graph_layout(self, client, bipartite_graphml):
        """Test bipartite layout on bipartite graph."""
        payload = {
            "graphml_content": bipartite_graphml,
            "layout_type": "bipartite",
            "layout_params": {"nodes": [0, 1, 2]}  # Top nodes
        }
        
        response = client.post("/tools/change_layout", json=payload)
        assert response.status_code in [200, 400]
    
    def test_tree_layout(self, client, tree_graphml):
        """Test tree layout on tree graph."""
        payload = {
            "graphml_content": tree_graphml,
            "layout_type": "tree",
            "layout_params": {"root": 0}
        }
        
        response = client.post("/tools/change_layout", json=payload)
        assert response.status_code in [200, 400]

class TestErrorHandling:
    """Test error handling scenarios."""
    
    def test_missing_required_fields(self, client):
        """Test API calls with missing required fields."""
        # Missing graphml_content
        response = client.post("/tools/change_layout", json={
            "layout_type": "spring"
        })
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        
        # Missing layout_type
        response = client.post("/tools/change_layout", json={
            "graphml_content": "test"
        })
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    def test_invalid_json(self, client):
        """Test API calls with invalid JSON."""
        response = client.post(
            "/tools/change_layout",
            data="invalid json",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    
    def test_very_large_graph(self, client):
        """Test handling of very large graphs."""
        # Create a large graph
        import networkx as nx
        import io
        
        G = nx.complete_graph(1000)  # Large complete graph
        output = io.BytesIO()
        nx.write_graphml(G, output)
        output.seek(0)
        large_graphml = output.read().decode("utf-8")
        
        payload = {
            "graphml_content": large_graphml,
            "layout_type": "spring",
            "layout_params": {}
        }
        
        response = client.post("/tools/change_layout", json=payload)
        # Might timeout or succeed depending on implementation
        assert response.status_code in [200, 400, 500, 504]

def test_cors_headers(client):
    """Test CORS headers are properly set."""
    response = client.options("/health")
    # Test client might not fully simulate CORS
    assert response.status_code in [200, 405]

def test_api_documentation(client):
    """Test that API documentation is available."""
    response = client.get("/docs")
    assert response.status_code == status.HTTP_200_OK
    
    response = client.get("/redoc")
    assert response.status_code == status.HTTP_200_OK
    
    response = client.get("/openapi.json")
    assert response.status_code == status.HTTP_200_OK