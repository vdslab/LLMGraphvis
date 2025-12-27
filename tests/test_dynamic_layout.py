
import unittest
from unittest.mock import MagicMock, patch
import networkx as nx
from common import models
from app.logic import layout
import math

class TestDynamicLayout(unittest.TestCase):
    def setUp(self):
        self.db = MagicMock()
        self.db.query.return_value.filter.return_value.all.return_value = [] # Mock node query

    @patch('app.logic.utils.graph_builder.build_graph_from_db')
    @patch('networkx.spring_layout')
    @patch('networkx.forceatlas2_layout')
    def test_spring_layout_params(self, mock_fa2, mock_spring, mock_build_graph):
        # 1. SMALL GRAPH (50 nodes)
        G_small = nx.path_graph(50)
        mock_build_graph.return_value = G_small
        
        layout.calculate_layout(1, "spring", self.db)
        
        args, kwargs = mock_spring.call_args
        self.assertEqual(kwargs['iterations'], 1000)
        self.assertEqual(kwargs['threshold'], 1e-6)
        
        # 2. MEDIUM GRAPH (1000 nodes)
        mock_spring.reset_mock()
        G_med = nx.path_graph(1000)
        mock_build_graph.return_value = G_med
        
        layout.calculate_layout(2, "spring", self.db)
        
        args, kwargs = mock_spring.call_args
        self.assertEqual(kwargs['iterations'], 500)
        self.assertEqual(kwargs['threshold'], 1e-5)
        
        # 3. LARGE GRAPH (2500 nodes)
        mock_spring.reset_mock()
        G_large = nx.path_graph(2500)
        mock_build_graph.return_value = G_large
        
        layout.calculate_layout(3, "spring", self.db)
        
        args, kwargs = mock_spring.call_args
        self.assertEqual(kwargs['iterations'], 200)
        self.assertEqual(kwargs['threshold'], 1e-4)

    @patch('app.logic.utils.graph_builder.build_graph_from_db')
    @patch('networkx.forceatlas2_layout')
    def test_forceatlas2_params(self, mock_fa2, mock_build_graph):
        # 1. SMALL GRAPH (50 nodes)
        G_small = nx.path_graph(50)
        mock_build_graph.return_value = G_small
        
        layout.calculate_layout(1, "forceatlas2", self.db)
        
        args, kwargs = mock_fa2.call_args
        self.assertEqual(kwargs['max_iter'], 2000)
        self.assertEqual(kwargs['gravity'], 0.03)
        
        # 2. MEDIUM GRAPH (1000 nodes)
        mock_fa2.reset_mock()
        G_med = nx.path_graph(1000)
        mock_build_graph.return_value = G_med
        
        layout.calculate_layout(2, "forceatlas2", self.db)
        
        args, kwargs = mock_fa2.call_args
        self.assertEqual(kwargs['max_iter'], 1000)

        # 3. LARGE GRAPH (2500 nodes)
        mock_fa2.reset_mock()
        G_large = nx.path_graph(2500)
        mock_build_graph.return_value = G_large
        
        layout.calculate_layout(3, "forceatlas2", self.db)
        
        args, kwargs = mock_fa2.call_args
        self.assertEqual(kwargs['max_iter'], 500)

if __name__ == '__main__':
    unittest.main()
