import sys
import os
import asyncio
from unittest.mock import AsyncMock, patch

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

async def test_context_summary():
    # Mock data
    mock_structure = {"node_count": 100, "edge_count": 200}
    mock_attributes = {
        "attributes": [
            {"name": "department", "data_type": "string"},
            {"name": "score", "data_type": "float"}
        ]
    }

    # Patch mcp_client.get_resource
    with patch('app.services.llm.mcp_client.get_resource', new_callable=AsyncMock) as mock_get:
        def side_effect(uri):
            if "structure" in uri:
                return mock_structure
            if "attributes/nodes" in uri:
                return mock_attributes
            return {}
        
        mock_get.side_effect = side_effect
        
        # Import the function (needs app context or loose import)
        # We might need to mock other imports in service.py if they side-effect on import
        # simple import should work if dependencies are installed
        try:
             from app.services.llm.service import _build_context_summary
        except ImportError as e:
            print(f"ImportError: {e}")
            return

        print("--- Testing Context Summary Generation ---")
        summary = await _build_context_summary(1)
        
        print("\nGenerated Summary:")
        print(summary)
        
        # assertion-like checks
        assert "Network ID: 1" in summary
        assert "100 Nodes" in summary
        assert "department (string)" in summary
        assert "score (float)" in summary
        print("\n[SUCCESS] Summary contains all expected fields.")

if __name__ == "__main__":
    asyncio.run(test_context_summary())
