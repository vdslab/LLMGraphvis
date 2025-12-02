import httpx
import asyncio
import json
import os

# Configuration
API_URL = "http://localhost:8000"
USERNAME = "testuser"
PASSWORD = "testpassword"

async def verify_ranking_and_overlay():
    async with httpx.AsyncClient(timeout=60.0) as client:
        # 1. Login
        print("1. Logging in...")
        response = await client.post(f"{API_URL}/api/v1/auth/token", data={"username": USERNAME, "password": PASSWORD})
        if response.status_code != 200:
            # Register if login fails
            print("   Login failed, registering...")
            await client.post(f"{API_URL}/api/v1/auth/register", json={"username": USERNAME, "password": PASSWORD})
            response = await client.post(f"{API_URL}/api/v1/auth/token", data={"username": USERNAME, "password": PASSWORD})
        
        assert response.status_code == 200
        token = response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        print("   Login successful.")

        # 2. Initialize Network (using a simple graph)
        print("\n2. Initializing Network...")
        graphml = """<?xml version="1.0" encoding="UTF-8"?>
<graphml xmlns="http://graphml.graphdrawing.org/xmlns" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://graphml.graphdrawing.org/xmlns http://graphml.graphdrawing.org/xmlns/1.0/graphml.xsd">
  <graph id="G" edgedefault="undirected">
    <node id="n0"/>
    <node id="n1"/>
    <node id="n2"/>
    <node id="n3"/>
    <node id="n4"/>
    <node id="n5"/>
    <edge source="n0" target="n1"/>
    <edge source="n0" target="n2"/>
    <edge source="n0" target="n3"/>
    <edge source="n0" target="n4"/>
    <edge source="n4" target="n5"/>
  </graph>
</graphml>"""
        
        # Create chat first
        chat_res = await client.post(f"{API_URL}/api/v1/chat", json={"name": "Ranking Test"}, headers=headers)
        chat_id = chat_res.json()["id"]
        network_id = chat_res.json()["network_id"]

        # Upload file
        files = {"file": ("test.graphml", graphml, "application/xml")}
        upload_res = await client.post(f"{API_URL}/api/v1/chat/{chat_id}/upload", files=files, headers=headers)
        assert upload_res.status_code == 202
        print("   Network initialized.")
        
        # Wait for async processing
        await asyncio.sleep(2)

        # 3. Calculate Centrality
        print("\n3. Calculating Degree Centrality...")
        calc_res = await client.post(f"{API_URL}/api/v1/tools/calculate_centrality", json={"network_id": network_id, "centrality_type": "degree"}, headers=headers)
        assert calc_res.status_code == 200
        print("   Centrality calculated.")

        # 4. Verify RANKING Coloring
        print("\n4. Verifying RANKING Coloring...")
        vis_config_ranking = {
            "network_id": network_id,
            "layout_name": "spring",
            "node_color_config": {
                "attribute": "degree_centrality",
                "scale_type": "RANKING",
                "ranking_rules": [
                    { "top": 1, "color": "red" },   # n0 should be red (highest degree)
                    { "top": 4, "color": "blue" }   # others blue
                ],
                "default_color": "gray"
            }
        }
        vis_res = await client.post(f"{API_URL}/api/v1/tools/generate_visualization", json=vis_config_ranking, headers=headers)
        assert vis_res.status_code == 200
        vis_data = vis_res.json()
        
        # Check colors
        nodes = vis_data["nodes"]
        n0 = next(n for n in nodes if n["id"] == "n0")
        others = [n for n in nodes if n["id"] != "n0"]
        
        print(f"   n0 color: {n0['color']}")
        if n0["color"] == "red":
            print("   SUCCESS: Top node is red.")
        else:
            print(f"   FAILURE: Top node is {n0['color']}, expected red.")

        blue_count = sum(1 for n in others if n["color"] == "blue")
        print(f"   Blue nodes count: {blue_count}")
        if blue_count == 4:
             print("   SUCCESS: Other nodes are blue.")
        else:
             print("   FAILURE: Expected 4 blue nodes.")

        # 5. Verify Combined Ranking + Overlay
        print("\n5. Verifying Combined Ranking + Overlay...")
        # Create a subgraph first (e.g., ego network of n0)
        ego_res = await client.post(f"{API_URL}/api/v1/tools/create_ego_network", json={"source_network_id": network_id, "center_node_id": "n0", "radius": 1}, headers=headers)
        subgraph_id = ego_res.json()["new_network_id"]
        
        vis_config_combined = {
            "network_id": network_id,
            "layout_name": "spring",
            "overlay_network_id": subgraph_id,
            "node_color_config": {
                "attribute": "degree_centrality",
                "scale_type": "RANKING",
                "ranking_rules": [
                    { "top": 1, "color": "red" } # Top 1 (n0) should be RED
                ],
                "default_color": "gray" # This shouldn't matter inside overlay if highlight_color works
            },
            "overlay_config": {
                "highlight_color": "blue", # Other overlay nodes should be BLUE
                "dimmed_color": "black"    # Outside nodes should be BLACK
            }
        }
        
        vis_combined_res = await client.post(f"{API_URL}/api/v1/tools/generate_visualization", json=vis_config_combined, headers=headers)
        assert vis_combined_res.status_code == 200
        vis_data = vis_combined_res.json()
        
        nodes = vis_data["nodes"]
        n0 = next(n for n in nodes if n["id"] == "n0")
        neighbors = [n for n in nodes if n["id"] in ["n1", "n2", "n3", "n4"]]
        # In this graph, n0 is connected to n1,n2,n3,n4. So all are in ego network.
        # Wait, I need a node OUTSIDE the ego network to test dimmed_color.
        # The current graph is a star graph centered at n0. All nodes are dist 1.
        # So all nodes are in the ego network.
        # I should add a node n5 connected to n4 but not n0.
        
        print(f"   n0 color: {n0['color']}")
        if n0["color"] == "red":
            print("   SUCCESS: Top node is red (Ranking Rule).")
        else:
            print(f"   FAILURE: Top node is {n0['color']}, expected red.")

        blue_count = sum(1 for n in neighbors if n["color"] == "blue")
        print(f"   Blue nodes count: {blue_count}")
        if blue_count == 4:
             print("   SUCCESS: Neighbors are blue (Overlay Highlight).")
        else:
             print(f"   FAILURE: Expected 4 blue nodes, got {blue_count}.")
             for n in neighbors:
                 print(f"     {n['id']}: {n['color']}")

        n5 = next(n for n in nodes if n["id"] == "n5")
        print(f"   n5 color: {n5['color']}")
        if n5["color"] == "black":
             print("   SUCCESS: Outside node is black (Overlay Dimmed).")
        else:
             print(f"   FAILURE: Outside node is {n5['color']}, expected black.")

        # 6. Verify Custom Node Colors (Direct Override)
        print("\n6. Verify Custom Node Colors...")
        vis_config_custom = {
            "network_id": network_id,
            "layout_name": "spring",
            "custom_node_colors": [
                {"node_id": "n0", "color": "purple"},
                {"node_id": "n1", "color": "orange"}
            ],
            # Fallback for others
            "node_color_config": {
                "default_color": "gray"
            }
        }
        vis_custom_res = await client.post(f"{API_URL}/api/v1/tools/generate_visualization", json=vis_config_custom, headers=headers)
        assert vis_custom_res.status_code == 200
        vis_custom_data = vis_custom_res.json()
        
        nodes_c = vis_custom_data["nodes"]
        n0_c = next(n for n in nodes_c if n["id"] == "n0")
        n1_c = next(n for n in nodes_c if n["id"] == "n1")
        n2_c = next(n for n in nodes_c if n["id"] == "n2")
        
        print(f"   n0 color: {n0_c['color']}")
        if n0_c["color"] == "purple":
             print("   SUCCESS: n0 is purple (Custom).")
        else:
             print(f"   FAILURE: n0 is {n0_c['color']}, expected purple.")

        print(f"   n1 color: {n1_c['color']}")
        if n1_c["color"] == "orange":
             print("   SUCCESS: n1 is orange (Custom).")
        else:
             print(f"   FAILURE: n1 is {n1_c['color']}, expected orange.")
             
        print(f"   n2 color: {n2_c['color']}")
        if n2_c["color"] == "gray":
             print("   SUCCESS: n2 is gray (Default).")
        else:
             print(f"   FAILURE: n2 is {n2_c['color']}, expected gray.")

if __name__ == "__main__":
    asyncio.run(verify_ranking_and_overlay())
