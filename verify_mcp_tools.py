
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.sse import sse_client
import os

# Configuration
# NetworkX API is exposed on logic port 8001 in docker-compose, so we can hit it locally at localhost:8001
MCP_SERVER_URL = "http://localhost:8001/mcp/sse"

GRAPHML_DATA = """<?xml version="1.0" encoding="UTF-8"?>
<graphml xmlns="http://graphml.graphdrawing.org/xmlns">
    <key id="d0" for="node" attr.name="color" attr.type="string"/>
    <graph id="G" edgedefault="undirected">
        <node id="n0">
            <data key="d0">blue</data>
        </node>
        <node id="n1">
            <data key="d0">red</data>
        </node>
        <edge source="n0" target="n1"/>
    </graph>
</graphml>
"""

async def verify_mcp():
    print(f"Connecting to MCP Server at {MCP_SERVER_URL}...")
    
    try:
        async with sse_client(MCP_SERVER_URL) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                
                # 1. List Tools
                print("\n--- Listing Tools ---")
                tools_result = await session.list_tools()
                tool_names = [t.name for t in tools_result.tools]
                print(f"Available tools: {tool_names}")
                
                if "initialize_network" not in tool_names:
                    print("ERROR: initialize_network tool not found!")
                    return

                # 2. Call initialize_network
                print("\n--- Calling initialize_network ---")
                init_args = {
                    "network_id": 999, # Test ID
                    "graphml_data": GRAPHML_DATA
                }
                result = await session.call_tool("initialize_network", init_args)
                if result.isError:
                    print(f"ERROR: initialize_network failed: {result.content}")
                    return
                print("initialize_network success!")
                # Parse result to see what we got (it returns text usually)
                print(f"Result content: {result.content}")
                
                # 3. Call generate_visualization
                print("\n--- Calling generate_visualization ---")
                vis_args = {
                    "network_id": 999,
                    "layout_name": "forceatlas2" # Test default layout
                }
                vis_result = await session.call_tool("generate_visualization", vis_args)
                if vis_result.isError:
                     print(f"ERROR: generate_visualization failed: {vis_result.content}")
                     return
                print("generate_visualization success!")
                print(f"Result content preview: {str(vis_result.content)[:200]}...")

    except Exception as e:
        print(f"\nCRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(verify_mcp())
