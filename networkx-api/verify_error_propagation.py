import sys
from unittest.mock import patch

# Add project root to path
sys.path.append("/Users/takuma/develop/vdslab/master/GraphVisAgent/networkx-api")

# Mock database and models to avoid actual DB connection issues during simple logic test
from app.mcp_server import generate_visualization

# We want to test that if visualizer raises ValueError, generate_visualization returns it as "Error: ..."


def test_error_propagation():
    # Mock visualizer.generate_visualization_data to raise ValueError
    with patch("app.logic.visualizer.generate_visualization_data") as mock_vis:
        error_msg = "Missing required attributes for visualization: Node attribute 'forceatlas2_x'. Please calculate them first."
        mock_vis.side_effect = ValueError(error_msg)

        # Call the tool function (we need to mock Config objects as they are Pydantic models in the actual code,
        # but in the python file they are typed as Optional classes.
        # In the actual execution, FastMCP passes them.
        # But wait, mcp_server.py imports them.

        # Let's just mock the arguments to be None for simplicity,
        # triggering the logic that calls visualizer

        result = generate_visualization(network_id=1, layout_name="forceatlas2")

        print(f"Result: {result}")

        expected = f"Error: {error_msg}"
        if result == expected:
            print("SUCCESS: Error propagated correctly.")
        else:
            print(f"FAILURE: Expected '{expected}', got '{result}'")


if __name__ == "__main__":
    test_error_propagation()
