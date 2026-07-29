import asyncio
import os
import sys
from unittest.mock import AsyncMock, patch

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))


async def test_context_summary():
    # Mock data
    mock_structure = {"node_count": 100, "edge_count": 200}
    mock_attributes = {
        "attributes": [
            {"name": "department", "data_type": "string"},
            {"name": "score", "data_type": "float"},
        ]
    }

    # Patch mcp_client.get_resource
    # Patch mcp_client.session_scope and get_resource
    # We need to mock session_scope because build_context_summary uses it
    from app.services.llm import context

    # Mock context manager for session_scope
    mock_session = AsyncMock()
    mock_session_cm = AsyncMock()
    mock_session_cm.__aenter__.return_value = mock_session
    mock_session_cm.__aexit__.return_value = None

    with patch("app.services.llm.mcp_client.session_scope", return_value=mock_session_cm), \
         patch("app.services.llm.mcp_client.get_resource", new_callable=AsyncMock) as mock_get:

        def side_effect(uri, session=None):
            if "structure" in uri:
                return mock_structure
            if "attributes/nodes" in uri:
                return mock_attributes
            return {}

        mock_get.side_effect = side_effect

        print("--- Testing Context Summary Generation (Refactored) ---")
        summary = await context.build_context_summary(1)

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
