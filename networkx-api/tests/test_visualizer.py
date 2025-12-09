import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Add networkx-api to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.logic.visualizer import generate_visualization_data
from app import models

class TestVisualizer(unittest.TestCase):
    def setUp(self):
        self.db = MagicMock()
        self.network_id = 1
        
        # Mock Nodes
        self.node1 = MagicMock(spec=models.Node)
        self.node1.id = 1
        self.node1.node_id = "n1"
        self.node1.label = "Node 1"
        self.node1.network_id = self.network_id
        
        self.node2 = MagicMock(spec=models.Node)
        self.node2.id = 2
        self.node2.node_id = "n2"
        self.node2.label = "Node 2"
        self.node2.network_id = self.network_id
        
        self.nodes = [self.node1, self.node2]
        
        # Mock Edges
        self.edge1 = MagicMock(spec=models.Edge)
        self.edge1.id = 1
        self.edge1.edge_id = "e1"
        self.edge1.source_node_id = 1
        self.edge1.target_node_id = 2
        self.edge1.network_id = self.network_id
        
        self.edges = [self.edge1]
        
        # Setup DB queries
        # When querying Node, return nodes
        # When querying Edge, return edges
        # We need to mock the query chain: db.query(Model).filter(...).all()
        
        def query_side_effect(model, *args):
            query_mock = MagicMock()
            if model is models.Node:
                query_mock.filter.return_value.all.return_value = self.nodes
                # For _fetch_node_data (NodeAttribute)
                query_mock.filter.return_value.filter.return_value.all.return_value = [] # Attributes query
            elif model is models.Edge:
                query_mock.filter.return_value.all.return_value = self.edges
            elif model is models.NodeAttribute:
                # IMPORTANT: Simulate presence of layout attributes which are now strict requirements
                attrs = []
                for args, kwargs in query_mock.filter.call_args_list:
                    # Logic to catch "in_" calls for attributes
                    pass
                
                # Simply return layout attributes to satisfy strict validation in basic tests
                # In a real mock we'd be more specific, but for now we just need them to exist.
                # The visualizer checks if attr name is in the returned list.
                # We return mocks with attribute_name set.
                a1 = MagicMock(spec=models.NodeAttribute)
                a1.id = 100
                a1.attribute_name = "forceatlas2_x"
                a2 = MagicMock(spec=models.NodeAttribute)
                a2.id = 101
                a2.attribute_name = "forceatlas2_y"
                return_val = [a1, a2]
                query_mock.filter.return_value.all.return_value = return_val
                # Also handle attribute_name.in_ check
                return query_mock
            elif model is models.EdgeAttribute:
                query_mock.filter.return_value.all.return_value = []
            else:
                 query_mock.filter.return_value.all.return_value = []
            
            # Chain mock for joins in _fetch_attribute_values
            # db.query(...).join(...).filter(...).all()
            query_mock.filter.return_value.join.return_value.filter.return_value.all.return_value = []
            query_mock.join.return_value.filter.return_value.all.return_value = []
            
            return query_mock

        self.db.query.side_effect = query_side_effect

    def test_basic_generation(self):
        """Test basic generation without config"""
        result = generate_visualization_data(self.network_id, self.db)
        
        self.assertIn("nodes", result)
        self.assertIn("links", result)
        self.assertEqual(len(result["nodes"]), 2)
        self.assertEqual(len(result["links"]), 1)
        
        n1 = next(n for n in result["nodes"] if n["id"] == "n1")
        self.assertEqual(n1["label"], "Node 1")
        self.assertEqual(n1["color"], "#1f77b4") # Default color logic check
        self.assertEqual(n1["size"], 10) # Default size logic check (utils.calculate_smart_node_size returns dict, usually min=10)

    @patch('app.logic.style_service.StyleService.get_val')
    def test_layout_coordinates(self, mock_get_val):
        """Test layout coordinates are applied"""
        # Mock get_val to return specific coordinates for layout keys
        def get_val_side_effect(entity_id, attr_name, attr_map, values):
            if attr_name == "forceatlas2_x":
                return 100.0 if entity_id == 1 else 200.0
            if attr_name == "forceatlas2_y":
                return 50.0 if entity_id == 1 else 60.0
            return None
        
        mock_get_val.side_effect = get_val_side_effect
        
        result = generate_visualization_data(self.network_id, self.db, layout_name="forceatlas2")
        
        n1 = next(n for n in result["nodes"] if n["id"] == "n1")
        self.assertEqual(n1["x"], 100.0)
        self.assertEqual(n1["y"], 50.0)

        if "degree_centrality" in str(getattr(cm.exception, "message", str(cm.exception))):
             # Success
             pass
        else:
             # It might fail on layout attributes if my setup is wrong, but that's also a ValueError.
             # Ideally we want to ensure it detected the specific missing attribute.
             pass
            
            
    def test_missing_attribute_raises_error(self):
        """Test that missing required attributes raise ValueError"""
        # ... validation logic ...
        node_size_config = {"attribute": "degree_centrality"}
        
        # We need to explicitly clear side_effect or ensure it returns layout but NOT degree_centrality
        # The default side_effect (modified above) returns forceatlas2_x/y.
        # So degree_centrality will be missing.
        
        with self.assertRaises(ValueError) as cm:
            generate_visualization_data(
                self.network_id, 
                self.db, 
                node_size_config=node_size_config
            )
        
        self.assertIn("Missing required attributes", str(cm.exception))
        self.assertIn("degree_centrality", str(cm.exception))

if __name__ == "__main__":
    unittest.main()
