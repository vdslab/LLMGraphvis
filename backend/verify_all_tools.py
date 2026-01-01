import asyncio
import json
import os
import sys

# Add backend and root to sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), "app"))
sys.path.append(os.path.dirname(__file__))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Set API URL
os.environ["NETWORKX_API_URL"] = "http://localhost:8001"

from app.services.llm import mcp_client

GRAPHML_CONTENT = """<?xml version="1.0" encoding="UTF-8"?>
<graphml xmlns="http://graphml.graphdrawing.org/xmlns" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://graphml.graphdrawing.org/xmlns http://graphml.graphdrawing.org/xmlns/1.0/graphml.xsd">
  <key id="d0" for="node" attr.name="color" attr.type="string">
    <default>yellow</default>
  </key>
  <graph id="G" edgedefault="undirected">
    <node id="n0">
        <data key="d0">green</data>
    </node>
    <node id="n1"/>
    <node id="n2"/>
    <edge source="n0" target="n1"/>
    <edge source="n1" target="n2"/>
  </graph>
</graphml>"""

async def test_tool(tool_name, args, expected_keys=None):
    print(f"\n--- Testing {tool_name} ---")
    try:
        result = await mcp_client.execute_tool(tool_name, args)
        print(f"Result: {json.dumps(result, indent=2)[:200]}...") # Truncate output
        
        if expected_keys:
            if isinstance(result, dict):
                 missing = [k for k in expected_keys if k not in result]
                 if missing:
                     print(f"FAILURE: Missing keys {missing} in result.")
                     return False
            elif isinstance(result, str):
                 # Some tools return string (e.g. update_network_metadata)
                 pass
        
        print("SUCCESS")
        return result
    except Exception as e:
        print(f"FAILURE: {e}")
        return None

async def main():
    print("=== STARTING ALL TOOLS VERIFICATION ===")
    
    # 1. Discovery
    print("\n--- 1. Discovery ---")
    tools = await mcp_client.get_tools_as_gemini_functions()
    tool_names = [t.function_declarations[0].name for t in tools]
    print(f"Found {len(tools)} tools: {tool_names}")

    # 2. Initialization
    network_id = 9999
    print(f"\n--- 2. Initialization (network_id={network_id}) ---")
    init_result = await test_tool("initialize_network", 
                                  {"network_id": network_id, "graphml_data": GRAPHML_CONTENT},
                                  expected_keys=["network_id", "network"])
    
    if not init_result:
        print("CRITICAL: Initialization failed. Aborting remaining tests.")
        return

    actual_network_id = init_result["network_id"]
    print(f"Using Network ID: {actual_network_id}")

    # 3. Retrieval Tools
    await test_tool("get_network_structure", {"network_id": actual_network_id})
    await test_tool("list_node_attributes", {"network_id": actual_network_id})
    await test_tool("list_edge_attributes", {"network_id": actual_network_id})
    await test_tool("get_node_details", {"network_id": actual_network_id, "node_id": "n0"}) # Check if n0 exists
    await test_tool("search_nodes", {"network_id": actual_network_id, "query": "n0"})
    await test_tool("get_top_nodes", {"network_id": actual_network_id, "metric": "degree", "limit": 2})

    # 4. Computation Tools
    await test_tool("calculate_centrality", {"network_id": actual_network_id, "centrality_type": "degree"})
    await test_tool("calculate_layout", {"network_id": actual_network_id, "layout_name": "spring"})

    # 5. Editing Tools
    await test_tool("update_node_label", {"network_id": actual_network_id, "node_id": "n0", "new_label": "Node Zero"})
    await test_tool("update_network_metadata", {"network_id": actual_network_id, "name": "Test Network Updated"})

    # 6. Visualization Tools
    await test_tool("generate_visualization", {"network_id": actual_network_id})
    await test_tool("update_node_color", {"network_id": actual_network_id, "attribute": "degree_centrality", "scale_type": "linear"}) 
    await test_tool("update_node_size", {"network_id": actual_network_id, "attribute": "degree_centrality"})
    
    # 7. Subgraph Tools (Basic check)
    await test_tool("create_subgraph_from_nodes", {"network_id": actual_network_id, "node_ids": ["n0", "n1"]})

    print("\n=== VERIFICATION COMPLETE ===")

if __name__ == "__main__":
    asyncio.run(main())
