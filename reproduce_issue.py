import asyncio
import httpx
import os
from dotenv import load_dotenv

load_dotenv()

API_URL = os.getenv("VITE_API_URL", "http://localhost:8000")
USERNAME = os.getenv("AUTH_USERNAME", "admin")
PASSWORD = os.getenv("AUTH_PASSWORD", "admin")

async def reproduce_issue():
    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. Login
        print("1. Logging in...")
        auth_res = await client.post(f"{API_URL}/api/v1/auth/token", data={"username": USERNAME, "password": PASSWORD})
        if auth_res.status_code != 200:
            print(f"Login failed: {auth_res.text}")
            return
        token = auth_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 2. Initialize Network (Les Miserables)
        print("2. Initializing Network...")
        with open("backend/app/data/miserables.json", "r") as f:
            graph_data = f.read()
        
        init_res = await client.post(f"{API_URL}/api/v1/tools/initialize_network", json={"network_id": 9999, "graphml_data": graph_data}, headers=headers)
        if init_res.status_code != 200:
             print(f"Init failed: {init_res.text}")
             return
        network_id = init_res.json()["network_id"]
        print(f"   Network ID: {network_id}")

        # 3. Calculate Centrality
        print("3. Calculating Centrality...")
        await client.post(f"{API_URL}/api/v1/tools/calculate_centrality", json={"network_id": network_id, "centrality_type": "degree"}, headers=headers)

        # 4. Get Top Node
        print("4. Getting Top Node...")
        top_res = await client.post(f"{API_URL}/api/v1/tools/get_top_nodes", json={"network_id": network_id, "metric": "degree_centrality", "k": 1}, headers=headers)
        top_node = top_res.json()[0]
        top_node_id = top_node["node_id"] # e.g. "Valjean"
        print(f"   Top Node: {top_node_id}")

        # 5. Create Ego Network (2 hops)
        print("5. Creating Ego Network...")
        ego_res = await client.post(f"{API_URL}/api/v1/tools/create_ego_network", json={"source_network_id": network_id, "center_node_id": top_node_id, "radius": 2}, headers=headers)
        subgraph_id = ego_res.json()["new_network_id"]
        print(f"   Subgraph ID: {subgraph_id}")

        # 6. Generate Visualization with Composite Rules
        print("6. Generating Visualization...")
        vis_config = {
            "network_id": network_id,
            "layout_name": "spring",
            "overlay_network_id": subgraph_id,
            "node_size_config": {
                "attribute": "degree_centrality",
                "min": 10,
                "max": 30
            },
            "overlay_config": {
                "highlight_color": "#87CEEB", # Light Blue
                "dimmed_color": "#D3D3D3"     # Gray
            },
            "custom_node_colors": [
                { "node_id": top_node_id, "color": "blue" } # Top Node Blue
            ]
        }

        vis_res = await client.post(f"{API_URL}/api/v1/tools/generate_visualization", json=vis_config, headers=headers)
        if vis_res.status_code != 200:
            print(f"Vis failed: {vis_res.text}")
            return
        
        vis_data = vis_res.json()
        nodes = vis_data["nodes"]
        
        # Check Top Node Color
        target_node = next(n for n in nodes if n["id"] == top_node_id)
        print(f"   Top Node ({top_node_id}) Color: {target_node['color']}")
        
        if target_node["color"] == "blue":
            print("   SUCCESS: Top Node is Blue.")
        else:
            print(f"   FAILURE: Top Node is {target_node['color']}, expected blue.")

        # Check Neighbors (should be Light Blue)
        # We need to know which nodes are in subgraph but not top node.
        # Let's just check if we have Light Blue nodes.
        light_blue_nodes = [n for n in nodes if n["color"] == "#87CEEB"]
        print(f"   Light Blue Nodes Count: {len(light_blue_nodes)}")
        
        if len(light_blue_nodes) > 0:
             print("   SUCCESS: Found Light Blue nodes (Overlay).")
        else:
             print("   FAILURE: No Light Blue nodes found.")

        # Check Dimmed (should be Gray)
        gray_nodes = [n for n in nodes if n["color"] == "#D3D3D3"]
        print(f"   Gray Nodes Count: {len(gray_nodes)}")
        
        if len(gray_nodes) > 0:
             print("   SUCCESS: Found Gray nodes (Dimmed).")
        else:
             print("   FAILURE: No Gray nodes found.")

if __name__ == "__main__":
    asyncio.run(reproduce_issue())
