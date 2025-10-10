"""
Test configuration and fixtures for NetworkXMCP testing.
"""

import pytest
import networkx as nx
import io
from fastapi.testclient import TestClient
from unittest.mock import patch

from main import app

@pytest.fixture
def client():
    """Create FastAPI test client."""
    with TestClient(app) as test_client:
        yield test_client

@pytest.fixture
def sample_graphml():
    """Sample GraphML content for testing."""
    return """<?xml version="1.0" encoding="UTF-8"?>
<graphml xmlns="http://graphml.graphdrawing.org/xmlns"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://graphml.graphdrawing.org/xmlns
         http://graphml.graphdrawing.org/xmlns/1.0/graphml.xsd">
  <key id="name" for="node" attr.name="name" attr.type="string"/>
  <graph id="G" edgedefault="undirected">
    <node id="1">
      <data key="name">Node 1</data>
    </node>
    <node id="2">
      <data key="name">Node 2</data>
    </node>
    <node id="3">
      <data key="name">Node 3</data>
    </node>
    <edge id="e1" source="1" target="2"/>
    <edge id="e2" source="2" target="3"/>
    <edge id="e3" source="3" target="1"/>
  </graph>
</graphml>"""

@pytest.fixture
def sample_graph():
    """Create a sample NetworkX graph for testing."""
    G = nx.Graph()
    G.add_nodes_from([1, 2, 3, 4, 5])
    G.add_edges_from([(1, 2), (2, 3), (3, 4), (4, 5), (5, 1), (1, 3)])
    return G

@pytest.fixture
def complex_graphml():
    """Complex GraphML with more nodes and edges for layout testing."""
    G = nx.karate_club_graph()
    output = io.BytesIO()
    nx.write_graphml(G, output)
    output.seek(0)
    return output.read().decode("utf-8")

@pytest.fixture
def bipartite_graphml():
    """GraphML for bipartite graph testing."""
    G = nx.complete_bipartite_graph(3, 4)
    # Add bipartite attribute
    for node in G.nodes():
        G.nodes[node]['bipartite'] = 0 if node < 3 else 1
    
    output = io.BytesIO()
    nx.write_graphml(G, output)
    output.seek(0)
    return output.read().decode("utf-8")

@pytest.fixture
def tree_graphml():
    """GraphML for tree structure testing."""
    G = nx.balanced_tree(2, 3)  # Binary tree with depth 3
    output = io.BytesIO()
    nx.write_graphml(G, output)
    output.seek(0)
    return output.read().decode("utf-8")

@pytest.fixture
def directed_graphml():
    """GraphML for directed graph testing."""
    G = nx.DiGraph()
    G.add_edges_from([(1, 2), (2, 3), (3, 4), (4, 1), (1, 3)])
    output = io.BytesIO()
    nx.write_graphml(G, output)
    output.seek(0)
    return output.read().decode("utf-8")

@pytest.fixture
def invalid_graphml():
    """Invalid GraphML content for error testing."""
    return "This is not valid GraphML content"

@pytest.fixture
def empty_graphml():
    """Empty graph GraphML."""
    G = nx.Graph()
    output = io.BytesIO()
    nx.write_graphml(G, output)
    output.seek(0)
    return output.read().decode("utf-8")

@pytest.fixture
def weighted_graphml():
    """GraphML with weighted edges."""
    G = nx.Graph()
    G.add_weighted_edges_from([(1, 2, 0.5), (2, 3, 1.0), (3, 4, 1.5), (4, 1, 2.0)])
    output = io.BytesIO()
    nx.write_graphml(G, output)
    output.seek(0)
    return output.read().decode("utf-8")

@pytest.fixture
def mock_cache():
    """Mock the graph cache for testing."""
    from unittest.mock import MagicMock
    
    cache_mock = MagicMock()
    cache_mock.get.return_value = None
    cache_mock.set.return_value = None
    cache_mock.get_stats.return_value = {
        "total_graphs": 0,
        "cache_hits": 0,
        "cache_misses": 0
    }
    
    with patch('tools.graph_cache.get_cache', return_value=cache_mock):
        yield cache_mock

@pytest.fixture(params=[
    "spring", "circular", "random", "spectral", "shell", 
    "kamada_kawai", "fruchterman_reingold", "planar", "spiral"
])
def layout_type(request):
    """Parametrized fixture for different layout types."""
    return request.param

@pytest.fixture(params=[
    "degree", "betweenness", "closeness", "eigenvector", 
    "pagerank", "clustering", "harmonic"
])
def centrality_type(request):
    """Parametrized fixture for different centrality types."""
    return request.param

@pytest.fixture
def layout_params():
    """Common layout parameters for testing."""
    return {
        "spring": {"k": 1.0, "iterations": 50},
        "circular": {"scale": 1.0},
        "kamada_kawai": {"dist": None, "pos": None},
        "fruchterman_reingold": {"k": None, "iterations": 50}
    }

@pytest.fixture
def centrality_params():
    """Common centrality parameters for testing."""
    return {
        "betweenness": {"normalized": True, "endpoints": False},
        "closeness": {"distance": None, "wf_improved": True},
        "eigenvector": {"max_iter": 100, "tol": 1e-06},
        "pagerank": {"alpha": 0.85, "max_iter": 100}
    }