
import sys
import os
import requests
import json
import time

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

API_URL = "http://localhost:8000/api/v1"
NX_API_URL = "http://localhost:8001/tools"

def verify_reuse():
    print("Starting Subgraph Reuse Verification...")

    # 1. Initialize a Network
    graphml = """<?xml version="1.0" encoding="UTF-8"?>
<graphml xmlns="http://graphml.graphdrawing.org/xmlns"  
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xsi:schemaLocation="http://graphml.graphdrawing.org/xmlns
     http://graphml.graphdrawing.org/xmlns/1.0/graphml.xsd">
  <graph id="G" edgedefault="undirected">
    <node id="A"/>
    <node id="B"/>
    <node id="C"/>
    <node id="D"/>
    <edge source="A" target="B"/>
    <edge source="B" target="C"/>
    <edge source="C" target="D"/>
    <edge source="D" target="A"/>
    <edge source="A" target="C"/>
  </graph>
</graphml>"""

    print("Initializing network...")
    # Initialize implementation is in networkx-api, but often called via backend. 
    # Let's call networkx-api tool directly for simplicity as per tools.py
    
    network_id = int(time.time()) # Randomish ID
    
    response = requests.post(f"{NX_API_URL}/initialize_network", json={
        "network_id": network_id,
        "graphml_data": graphml
    })
    
    if response.status_code != 200:
        print(f"Failed to initialize: {response.text}")
        return

    data = response.json()
    actual_network_id = data['network_id']
    print(f"Network initialized ID: {actual_network_id}")

    # 2. Create Ego Network (First Time)
    print("\nCreating Ego Network for Node 'A'...")
    ego_resp1 = requests.post(f"{NX_API_URL}/create_ego_network", json={
        "source_network_id": actual_network_id,
        "center_node_id": "A",
        "radius": 1
    })
    
    if ego_resp1.status_code != 200:
        print(f"Failed create ego 1: {ego_resp1.text}")
        return
        
    ego1 = ego_resp1.json()
    print(f"Ego 1: ID={ego1.get('new_network_id')}, Name='{ego1.get('name')}'")

    # 3. Create Ego Network (Second Time - Should Reuse)
    print("Creating Ego Network for 'A' again (Expect Reuse)...")
    ego_resp2 = requests.post(f"{NX_API_URL}/create_ego_network", json={
        "source_network_id": actual_network_id,
        "center_node_id": "A",
        "radius": 1
    })
    
    ego2 = ego_resp2.json()
    print(f"Ego 2: ID={ego2.get('new_network_id')}, Name='{ego2.get('name')}'")
    
    if ego1['new_network_id'] == ego2['new_network_id']:
        print("PASS: Ego Network ID reused.")
    else:
        print("FAIL: Ego Network ID NOT reused.")

    # 4. Create Ad-hoc Subgraph (First Time)
    target_nodes = ["A", "C"]
    print(f"\nCreating Ad-hoc Subgraph for {target_nodes}...")
    adhoc_resp1 = requests.post(f"{NX_API_URL}/create_subgraph_from_nodes", json={
        "source_network_id": actual_network_id,
        "node_ids": target_nodes
    })
    
    adhoc1 = adhoc_resp1.json()
    print(f"Adhoc 1: ID={adhoc1.get('new_network_id')}, Name='{adhoc1.get('name')}'")

    # 5. Create Ad-hoc Subgraph (Second Time - Should Reuse)
    print(f"Creating Ad-hoc Subgraph for {target_nodes} again...")
    adhoc_resp2 = requests.post(f"{NX_API_URL}/create_subgraph_from_nodes", json={
        "source_network_id": actual_network_id,
        "node_ids": target_nodes
    })
    
    adhoc2 = adhoc_resp2.json()
    print(f"Adhoc 2: ID={adhoc2.get('new_network_id')}, Name='{adhoc2.get('name')}'")
    
    if adhoc1['new_network_id'] == adhoc2['new_network_id']:
        print("PASS: Ad-hoc Subgraph ID reused.")
    else:
        print("FAIL: Ad-hoc Subgraph ID NOT reused.")
        
    # 6. Verify Naming Convention
    name1 = adhoc1.get('name')
    if "Subgraph (A,C)" in name1 or "Subgraph (C,A)" in name1: # check sorted
         print(f"PASS: Ad-hoc naming correct: {name1}")
    else:
         print(f"FAIL: Ad-hoc naming unexpected: {name1}")

if __name__ == "__main__":
    verify_reuse()
