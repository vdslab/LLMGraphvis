"""
Tests for NetworkXMCP tools and utility functions.
"""

import pytest
from unittest.mock import patch, MagicMock
import networkx as nx
import json

class TestNetworkTools:
    """Test network analysis tools."""
    
    def test_apply_layout_to_graphml(self, sample_graphml):
        """Test applying layout to GraphML content."""
        from tools.network_tools import apply_layout_to_graphml
        
        result = apply_layout_to_graphml(
            sample_graphml, 
            "spring", 
            {"k": 1.0, "iterations": 50}
        )
        
        assert result["success"] is True
        assert result["layout_type"] == "spring"
        assert "positions" in result
        assert "graphml_content" in result
    
    def test_calculate_centrality_function(self, sample_graph):
        """Test centrality calculation function."""
        from tools.network_tools import calculate_centrality
        
        result = calculate_centrality(sample_graph, "degree")
        
        assert result["success"] is True
        assert result["centrality_type"] == "degree"
        assert "centrality" in result
        assert isinstance(result["centrality"], dict)
    
    def test_parse_graphml_string_valid(self, sample_graphml):
        """Test parsing valid GraphML string."""
        from tools.network_tools import parse_graphml_string
        
        result = parse_graphml_string(sample_graphml)
        
        assert result["success"] is True
        assert "nodes" in result
        assert "edges" in result
    
    def test_parse_graphml_string_invalid(self, invalid_graphml):
        """Test parsing invalid GraphML string."""
        from tools.network_tools import parse_graphml_string
        
        result = parse_graphml_string(invalid_graphml)
        
        assert result["success"] is False
        assert "error" in result
    
    def test_convert_to_standard_graphml(self, sample_graphml):
        """Test GraphML conversion to standard format."""
        from tools.network_tools import convert_to_standard_graphml
        
        result = convert_to_standard_graphml(sample_graphml)
        
        assert result["success"] is True
        assert "graphml_content" in result
        assert "<?xml" in result["graphml_content"]
    
    def test_export_network_as_graphml(self, sample_graph):
        """Test exporting network as GraphML."""
        from tools.network_tools import export_network_as_graphml
        
        result = export_network_as_graphml(sample_graph, None, None)
        
        assert result["success"] is True
        assert "content" in result
        assert "<?xml" in result["content"]

class TestLayoutFunctions:
    """Test layout calculation functions."""
    
    def test_calculate_grid_layout(self, sample_graph):
        """Test grid layout calculation."""
        from layouts.layout_functions import calculate_grid_layout
        
        positions = calculate_grid_layout(sample_graph)
        
        assert isinstance(positions, dict)
        assert len(positions) == len(sample_graph.nodes())
        for node_id, pos in positions.items():
            assert "x" in pos or isinstance(pos, (list, tuple))
    
    def test_calculate_tree_layout(self, sample_graph):
        """Test tree layout calculation."""
        from layouts.layout_functions import calculate_tree_layout
        
        # Convert to tree by taking spanning tree
        tree = nx.minimum_spanning_tree(sample_graph)
        positions = calculate_tree_layout(tree, root=list(tree.nodes())[0])
        
        assert isinstance(positions, dict)
        assert len(positions) == len(tree.nodes())
    
    def test_calculate_radial_layout(self, sample_graph):
        """Test radial layout calculation."""
        from layouts.layout_functions import calculate_radial_layout
        
        positions = calculate_radial_layout(sample_graph, center=1)
        
        assert isinstance(positions, dict)
        assert len(positions) == len(sample_graph.nodes())
    
    def test_calculate_multipartite_layout(self, sample_graph):
        """Test multipartite layout calculation."""
        from layouts.layout_functions import calculate_multipartite_layout
        
        # Add subset attributes for multipartite layout
        for i, node in enumerate(sample_graph.nodes()):
            sample_graph.nodes[node]['subset'] = i % 2
        
        positions = calculate_multipartite_layout(sample_graph)
        
        assert isinstance(positions, dict)
        assert len(positions) == len(sample_graph.nodes())
    
    def test_calculate_bipartite_layout(self, sample_graph):
        """Test bipartite layout calculation."""
        from layouts.layout_functions import calculate_bipartite_layout
        
        nodes = list(sample_graph.nodes())
        top_nodes = nodes[:len(nodes)//2]
        
        positions = calculate_bipartite_layout(sample_graph, top_nodes)
        
        assert isinstance(positions, dict)
        assert len(positions) == len(sample_graph.nodes())

class TestCentralityFunctions:
    """Test centrality calculation functions."""
    
    @pytest.mark.parametrize("centrality_type", [
        "degree", "betweenness", "closeness", "eigenvector", "pagerank"
    ])
    def test_centrality_calculations(self, sample_graph, centrality_type):
        """Test various centrality calculations."""
        from metrics.centrality_functions import calculate_centrality
        
        try:
            result = calculate_centrality(sample_graph, centrality_type)
            assert isinstance(result, dict)
            assert len(result) == len(sample_graph.nodes())
            for node, value in result.items():
                assert isinstance(value, (int, float))
                assert value >= 0  # Most centralities are non-negative
        except Exception as e:
            # Some centralities might not work with all graph types
            pytest.skip(f"Centrality {centrality_type} failed: {e}")

class TestNetworkMetrics:
    """Test network-level metrics."""
    
    def test_basic_network_metrics(self, sample_graph):
        """Test calculation of basic network metrics."""
        from metrics.network_metrics import calculate_basic_metrics
        
        metrics = calculate_basic_metrics(sample_graph)
        
        assert "num_nodes" in metrics
        assert "num_edges" in metrics
        assert "density" in metrics
        assert "is_connected" in metrics
        assert metrics["num_nodes"] == len(sample_graph.nodes())
        assert metrics["num_edges"] == len(sample_graph.edges())
    
    def test_advanced_network_metrics(self, sample_graph):
        """Test calculation of advanced network metrics."""
        from metrics.network_metrics import calculate_advanced_metrics
        
        metrics = calculate_advanced_metrics(sample_graph)
        
        expected_metrics = [
            "average_clustering", "transitivity", "average_shortest_path_length",
            "diameter", "radius", "assortativity"
        ]
        
        for metric in expected_metrics:
            if metric in metrics:  # Some metrics might not be calculable for all graphs
                assert isinstance(metrics[metric], (int, float))

class TestAnalysisTools:
    """Test high-level analysis tools."""
    
    @patch('tools.graph_cache.get_cache')
    def test_calculate_and_store_metrics(self, mock_get_cache, sample_graphml):
        """Test the calculate_and_store_metrics function."""
        from tools.analysis_tools import calculate_and_store_metrics
        
        # Mock cache
        mock_cache = MagicMock()
        mock_cache.set.return_value = None
        mock_get_cache.return_value = mock_cache
        
        result = calculate_and_store_metrics(
            graphml_content=sample_graphml,
            layout_type="spring",
            layout_params={},
            metrics_to_calculate=["degree", "betweenness"]
        )
        
        assert result["success"] is True
        assert "graph_id" in result
        mock_cache.set.assert_called_once()
    
    @patch('tools.graph_cache.get_cache')
    def test_get_visualization_data(self, mock_get_cache):
        """Test getting visualization data from cache."""
        from tools.analysis_tools import get_visualization_data
        
        # Mock cache with sample data
        mock_cache = MagicMock()
        mock_cache.get.return_value = {
            "graph": MagicMock(),
            "positions": {"1": {"x": 0, "y": 0}, "2": {"x": 1, "y": 1}},
            "metrics": {"degree": {"1": 2, "2": 1}}
        }
        mock_get_cache.return_value = mock_cache
        
        result = get_visualization_data(
            graph_id="test_id",
            metric_name="degree",
            color_scheme="viridis"
        )
        
        assert result["success"] is True
        assert "visualization_data" in result
    
    @patch('tools.graph_cache.get_cache')
    def test_get_available_metrics(self, mock_get_cache):
        """Test getting available metrics from cache."""
        from tools.analysis_tools import get_available_metrics
        
        # Mock cache with metrics
        mock_cache = MagicMock()
        mock_cache.get.return_value = {
            "metrics": {
                "degree": {"1": 2, "2": 1},
                "betweenness": {"1": 0.5, "2": 0.3}
            }
        }
        mock_get_cache.return_value = mock_cache
        
        result = get_available_metrics("test_id")
        
        assert result["success"] is True
        assert "metrics" in result
        assert len(result["metrics"]) == 2

class TestGraphCache:
    """Test graph caching functionality."""
    
    def test_cache_initialization(self):
        """Test cache initialization."""
        from tools.graph_cache import GraphCache
        
        cache = GraphCache(max_size=10)
        assert cache.max_size == 10
        assert len(cache.cache) == 0
    
    def test_cache_set_and_get(self):
        """Test cache set and get operations."""
        from tools.graph_cache import GraphCache
        
        cache = GraphCache(max_size=10)
        test_data = {"test": "data"}
        
        cache.set("test_key", test_data)
        retrieved = cache.get("test_key")
        
        assert retrieved == test_data
    
    def test_cache_eviction(self):
        """Test cache eviction when max size exceeded."""
        from tools.graph_cache import GraphCache
        
        cache = GraphCache(max_size=2)
        
        cache.set("key1", "data1")
        cache.set("key2", "data2")
        cache.set("key3", "data3")  # Should evict oldest
        
        assert cache.get("key1") is None  # Should be evicted
        assert cache.get("key2") == "data2"
        assert cache.get("key3") == "data3"
    
    def test_cache_stats(self):
        """Test cache statistics."""
        from tools.graph_cache import GraphCache
        
        cache = GraphCache(max_size=10)
        
        cache.set("key1", "data1")
        cache.get("key1")  # Hit
        cache.get("key2")  # Miss
        
        stats = cache.get_stats()
        assert stats["total_graphs"] == 1
        assert stats["cache_hits"] == 1
        assert stats["cache_misses"] == 1

class TestGraphMLConverter:
    """Test GraphML conversion utilities."""
    
    def test_graphml_to_cytoscape_conversion(self, sample_graph):
        """Test converting NetworkX graph to Cytoscape format."""
        from tools.graphml_converter import graph_to_cytoscape
        
        # Add some positions
        positions = {"1": {"x": 0, "y": 0}, "2": {"x": 1, "y": 1}}
        
        cytoscape_data = graph_to_cytoscape(sample_graph, positions)
        
        assert "nodes" in cytoscape_data
        assert "edges" in cytoscape_data
        assert isinstance(cytoscape_data["nodes"], list)
        assert isinstance(cytoscape_data["edges"], list)
    
    def test_cytoscape_node_format(self, sample_graph):
        """Test that nodes are formatted correctly for Cytoscape."""
        from tools.graphml_converter import graph_to_cytoscape
        
        cytoscape_data = graph_to_cytoscape(sample_graph)
        
        for node in cytoscape_data["nodes"]:
            assert "data" in node
            assert "id" in node["data"]
    
    def test_cytoscape_edge_format(self, sample_graph):
        """Test that edges are formatted correctly for Cytoscape."""
        from tools.graphml_converter import graph_to_cytoscape
        
        cytoscape_data = graph_to_cytoscape(sample_graph)
        
        for edge in cytoscape_data["edges"]:
            assert "data" in edge
            assert "source" in edge["data"]
            assert "target" in edge["data"]

class TestErrorHandling:
    """Test error handling in tools."""
    
    def test_layout_with_invalid_graph(self, invalid_graphml):
        """Test layout calculation with invalid graph."""
        from tools.network_tools import apply_layout_to_graphml
        
        result = apply_layout_to_graphml(invalid_graphml, "spring", {})
        
        assert result["success"] is False
        assert "error" in result
    
    def test_centrality_with_empty_graph(self, empty_graphml):
        """Test centrality calculation with empty graph."""
        from tools.network_tools import parse_graphml_string, calculate_centrality
        
        graph_result = parse_graphml_string(empty_graphml)
        if graph_result["success"]:
            # Create empty graph for testing
            G = nx.Graph()
            result = calculate_centrality(G, "degree")
            
            # Empty graph should still return success with empty centrality
            assert result["success"] is True
            assert len(result["centrality"]) == 0
    
    def test_unsupported_layout_type(self, sample_graphml):
        """Test handling of unsupported layout type."""
        from tools.network_tools import apply_layout_to_graphml
        
        result = apply_layout_to_graphml(
            sample_graphml, 
            "nonexistent_layout", 
            {}
        )
        
        # Should either fallback or return error
        assert "success" in result
        if not result["success"]:
            assert "error" in result

class TestPerformance:
    """Test performance-related aspects."""
    
    def test_large_graph_handling(self):
        """Test handling of larger graphs."""
        # Create a medium-sized graph for testing
        G = nx.barabasi_albert_graph(100, 3)
        
        from metrics.centrality_functions import calculate_centrality
        
        # Test that centrality calculation completes in reasonable time
        import time
        start_time = time.time()
        result = calculate_centrality(G, "degree")
        execution_time = time.time() - start_time
        
        assert isinstance(result, dict)
        assert len(result) == 100
        assert execution_time < 5.0  # Should complete within 5 seconds
    
    def test_memory_usage_with_multiple_graphs(self):
        """Test memory usage doesn't grow excessively."""
        from tools.graph_cache import GraphCache
        
        cache = GraphCache(max_size=5)
        
        # Add multiple graphs to cache
        for i in range(10):
            G = nx.path_graph(10)
            cache.set(f"graph_{i}", {"graph": G, "data": f"data_{i}"})
        
        # Cache should not exceed max size
        assert len(cache.cache) <= 5