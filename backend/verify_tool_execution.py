import asyncio
import json
import os
import sys

# Add backend to sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), "app"))
sys.path.append(os.path.dirname(__file__))

# Set API URL
os.environ["NETWORKX_API_URL"] = "http://localhost:8000"

from app.services.llm import mcp_client

async def main():
    print("--- 1. Testing Tool Discovery ---")
    try:
        tools = await mcp_client.get_tools_as_gemini_functions()
        print(f"Successfully retrieved {len(tools)} tools.")
        tool_names = [t.function_declarations[0].name for t in tools]
        print("Available tools:", tool_names)
        
        if "list_node_attributes" in tool_names:
            print("SUCCESS: 'list_node_attributes' found in tools.")
        else:
            print("FAILURE: 'list_node_attributes' NOT found in tools.")
            
        if "read_resource" in tool_names:
             print("SUCCESS: 'read_resource' found in tools.")
        else:
             print("FAILURE: 'read_resource' NOT found in tools.")

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"FAILED to retrieve tools: {e}")
        return

    print("\n--- 2. Testing Tool Execution (list_node_attributes) ---")
    try:
        # We need a valid network ID. 
        # If the DB is empty, this might fail gracefully or return empty.
        # Let's try network_id=1.
        result = await mcp_client.execute_tool("list_node_attributes", {"network_id": 1})
        print("Execution Result:", result)
    except Exception as e:
        print(f"Execution FAILED: {e}")

    print("\n--- 3. Testing Resource Read (read_resource) ---")
    try:
        result = await mcp_client.execute_tool("read_resource", {"uri": "network://1/attributes/nodes"})
        print("Resource Read Result:", result)
    except Exception as e:
        print(f"Resource Read FAILED: {e}")

if __name__ == "__main__":
    asyncio.run(main())
