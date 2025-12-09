
import sys
import os
import unittest
from unittest.mock import MagicMock, patch

# Add networkx-api to path
sys.path.insert(0, os.path.join(os.getcwd(), "networkx-api"))
print(f"DEBUG: sys.path[0] = {sys.path[0]}")

# Mock 'mcp' and submodules BEFORE importing app.mcp_server
mcp_mock = MagicMock()
sys.modules["mcp"] = mcp_mock
sys.modules["mcp.server"] = MagicMock()
sys.modules["mcp.server.fastmcp"] = MagicMock()

# Setup FastMCP mock to return a decorator that returns the function as is (or partially wrapped)
# logic: @mcp.tool() -> decorator -> receives func -> returns func (or wrapper)
# We want to be able to call the function.
def tool_decorator():
    def decorator(func):
        return func
    return decorator

# FastMCP instance mock
fast_mcp_instance = MagicMock()
fast_mcp_instance.tool.side_effect = tool_decorator
sys.modules["mcp.server.fastmcp"].FastMCP.return_value = fast_mcp_instance

# Now we can import the module under test
# We also need to mock app.core.database because it's imported at top level
with patch("app.core.database.SessionLocal") as mock_session_local:
    from app import mcp_server

class TestMCPErrorHandling(unittest.TestCase):
    
    @patch("app.mcp_server.get_db_session")
    @patch("app.mcp_server.visualizer.generate_visualization_data")
    def test_generate_visualization_error(self, mock_gen_vis, mock_get_db):
        print("Testing generate_visualization_error...")
        # Setup
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        
        # Simulate an error in the logic layer
        mock_gen_vis.side_effect = ValueError("Missing required attribute 'size'")
        
        # Execute
        result = mcp_server.generate_visualization(network_id=999)
        
        # Verify
        print(f"Result: {result}")
        self.assertTrue(isinstance(result, str))
        self.assertTrue(result.startswith("Error:"))
        self.assertIn("Missing required attribute 'size'", result)

    @patch("app.mcp_server.get_db_session")
    @patch("app.mcp_server.importer.parse_and_save_graphml")
    def test_initialize_network_error(self, mock_parse, mock_get_db):
        print("Testing initialize_network_error...")
        mock_db = MagicMock()
        mock_get_db.return_value = mock_db
        
        mock_parse.side_effect = Exception("Invalid GraphML")
        
        result = mcp_server.initialize_network(network_id=1, graphml_data="bad data")
        
        print(f"Result: {result}")
        self.assertTrue(isinstance(result, str))
        self.assertTrue(result.startswith("Error:"))
        self.assertIn("Invalid GraphML", result)

if __name__ == "__main__":
    unittest.main()
