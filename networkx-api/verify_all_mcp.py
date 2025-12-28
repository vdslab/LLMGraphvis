import asyncio
import json
import os
import sys

# Add backend directory to path so 'app' module can be found
sys.path.append(os.path.dirname(__file__))

from mcp.server.fastmcp import FastMCP
# Use try-except to handle potential import structure differences
try:
    from app.mcp_server import mcp
    from app.core import database
    from common import models
except ImportError:
    # If running from parent dir
    from backend.app.mcp_server import mcp
    from backend.app.core import database
    from common import models

# Mock DB Session
def get_db():
    return database.SessionLocal()

async def verify_mcp_tools():
    print("=== Verifying MCP Tools ===")
    tools = await mcp.list_tools()
    tool_names = [t.name for t in tools]
    print(f"Found {len(tool_names)} tools: {tool_names}")
    
    expected_tools = [
        "initialize_network", 
        "calculate_centrality", "calculate_community", "calculate_layout",
        "generate_visualization", "create_ego_network", 
        "create_subgraph_from_nodes", "create_path_subgraph",
        "create_k_core_subgraph", "create_largest_component_subgraph",
        "search_nodes",
        "get_node_details", "create_subgraph_by_filter",
        "list_node_attributes", "list_edge_attributes", 
        "get_network_structure", "get_top_nodes"
    ]
    
    missing = [t for t in expected_tools if t not in tool_names]
    if missing:
        print(f"❌ FAIL: Missing tools: {missing}")
    else:
        print("✅ PASS: All expected tools registered.")

async def verify_mcp_resources():
    print("\n=== Verifying MCP Resources ===")
    resources = await mcp.list_resources()
    resource_uris = [r.uri for r in resources]
    print(f"Found {len(resource_uris)} resource templates: {resource_uris}")
    
    # We can't easily check all templates because list_resources() in FastMCP might return instantiated ones or templates depending on implementation.
    # But let's check basic availability.
    pass

async def verify_mcp_prompts():
    print("\n=== Verifying MCP Prompts ===")
    prompts = await mcp.list_prompts()
    prompt_names = [p.name for p in prompts]
    print(f"Found {len(prompt_names)} prompts: {prompt_names}")
    
    expected_prompts = [
        "analyze-structure", "recommend-visualization", 
        "investigate-attributes", "find-important-nodes"
    ]
    
    missing = [p for p in expected_prompts if p not in prompt_names]
    if missing:
        print(f"❌ FAIL: Missing prompts: {missing}")
    else:
        print("✅ PASS: All expected prompts registered.")

async def test_tool_execution():
    print("\n=== Testing Tool Execution (Dry Run) ===")
    # Create a dummy network for testing if needed, or check mostly read-only tools
    db = get_db()
    try:
        # Create a test network
        test_net = models.Network(name="Verification Test Network")
        db.add(test_net)
        db.commit()
        db.refresh(test_net)
        net_id = test_net.id
        print(f"Created test network ID: {net_id}")

        # Test get_network_structure
        print(f"Testing get_network_structure({net_id})...")
        res = await mcp.call_tool("get_network_structure", {"network_id": net_id})
        print(f"Result: {res}")
        
        # Test list_node_attributes (renamed from get_node_attributes)
        print(f"Testing list_node_attributes({net_id})...")
        res = await mcp.call_tool("list_node_attributes", {"network_id": net_id})
        print(f"Result: {res}")
        
        # Test update_network_metadata (removed or missing, skipping)
        # print(f"Testing update_network_metadata({net_id})...")
        # res = await mcp.call_tool("update_network_metadata", {"network_id": net_id, "description": "Verified"})
        # print(f"Result: {res}")

        # Clean up
        db.delete(test_net)
        db.commit()
        print("✅ PASS: Basic tool execution successful.")

    except Exception as e:
        print(f"❌ FAIL: Tool execution error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(verify_mcp_tools())
    asyncio.run(verify_mcp_prompts())
    asyncio.run(test_tool_execution())
