import asyncio
import httpx
import json

# Direct URL to NetworkXAPI (bypassing Backend)
API_URL = "http://localhost:8001"

async def debug_direct():
    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. Initialize Network (Simple Star Graph)
        print("1. Initializing Network...")
        graph_data = """<?xml version="1.0" encoding="UTF-8"?>
<graphml xmlns="http://graphml.graphdrawing.org/xmlns" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://graphml.graphdrawing.org/xmlns http://graphml.graphdrawing.org/xmlns/1.0/graphml.xsd">
  <graph id="G" edgedefault="undirected">
    <node id="n0"/>
    <node id="n1"/>
    <node id="n2"/>
    <edge source="n0" target="n1"/>
    <edge source="n0" target="n2"/>
  </graph>
</graphml>"""
        
        init_res = await client.post(f"{API_URL}/tools/initialize_network", json={"network_id": 8888, "graphml_data": graph_data})
        if init_res.status_code != 200:
             print(f"Init failed: {init_res.text}")
             return
        print("   Network Initialized (ID: 8888)")

        # 2. Generate Visualization with Custom Colors
        print("2. Generating Visualization (Direct)...")
        vis_config = {
            "network_id": 8888,
            "layout_name": "spring",
            # Custom Color: n0 -> Blue
            "custom_node_colors": [
                { "node_id": "n0", "color": "blue" }
            ],
            # Default for others
            "node_color_config": {
                "default_color": "gray"
            }
        }

        vis_res = await client.post(f"{API_URL}/tools/generate_visualization", json=vis_config)
        if vis_res.status_code != 200:
            print(f"Vis failed: {vis_res.text}")
            return
        
        vis_data = vis_res.json()
        nodes = vis_data["nodes"]
        
        n0 = next(n for n in nodes if n["id"] == "n0")
        print(f"   n0 color: {n0['color']}")
        
        if n0["color"] == "blue":
            print("   SUCCESS: n0 is Blue (Custom Color applied).")
        else:
            print(f"   FAILURE: n0 is {n0['color']}, expected blue.")

if __name__ == "__main__":
    asyncio.run(debug_direct())
