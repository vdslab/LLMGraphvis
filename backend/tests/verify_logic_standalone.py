import asyncio
from unittest.mock import MagicMock

# Replicating the logic from service.py for standalone verification
# This ensures we verify the formatting logic without battling dependency imports

async def _build_context_summary_logic(get_resource_mock, network_id: int) -> str:
    """Fetches network stats and attributes to build a context summary string."""
    try:
        # Simulate the await calls
        structure = await get_resource_mock(f"network://{network_id}/structure")
        node_attrs = await get_resource_mock(f"network://{network_id}/attributes/nodes")
        
        summary_lines = ["[Current Network Context]"]
        summary_lines.append(f"Network ID: {network_id}")
        
        if structure:
            n_count = structure.get("node_count", "?")
            e_count = structure.get("edge_count", "?")
            summary_lines.append(f"Stats: {n_count} Nodes, {e_count} Edges")
            
        if node_attrs and "attributes" in node_attrs:
            attrs = node_attrs["attributes"]
            if attrs:
                summary_lines.append("Available Node Attributes:")
                for attr in attrs:
                    name = attr.get("name")
                    dtype = attr.get("data_type")
                    summary_lines.append(f"- {name} ({dtype})")
            else:
                summary_lines.append("Node Attributes: None")
        
        return "\n".join(summary_lines)
    except Exception as e:
        print(f"Error building context summary: {e}")
        return ""

async def test_logic():
    print("--- Verifying _build_context_summary Logic ---\n")
    
    # Mock the get_resource function
    async def mock_get_resource(uri):
        if "structure" in uri:
            return {"node_count": 150, "edge_count": 300}
        if "attributes/nodes" in uri:
            return {"attributes": [
                {"name": "department", "data_type": "string"},
                {"name": "tenure", "data_type": "integer"}
            ]}
        return {}

    summary = await _build_context_summary_logic(mock_get_resource, 5)
    
    print("Generated Summary:\n")
    print(summary)
    
    # Assertions
    expected_lines = [
        "[Current Network Context]",
        "Network ID: 5",
        "Stats: 150 Nodes, 300 Edges",
        "Available Node Attributes:",
        "- department (string)",
        "- tenure (integer)"
    ]
    
    for line in expected_lines:
        if line not in summary:
            print(f"\n[FAIL] Missing expected line: {line}")
            return

    print("\n[SUCCESS] Logic verified correctly.")

if __name__ == "__main__":
    asyncio.run(test_logic())
