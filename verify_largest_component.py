import urllib.request
import json
import time

BASE_URL = "http://localhost:8001/api/v1/networks"

def print_step(msg):
    print(f"\n{'='*50}\n{msg}\n{'='*50}")

def get_disconnected_graphml():
    # A graph with two components:
    # 1. Large component: A-B-C-D
    # 2. Small component: X-Y
    return """<?xml version="1.0" encoding="UTF-8"?>
<graphml xmlns="http://graphml.graphdrawing.org/xmlns"  
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xsi:schemaLocation="http://graphml.graphdrawing.org/xmlns
     http://graphml.graphdrawing.org/xmlns/1.0/graphml.xsd">
  <graph id="G" edgedefault="undirected">
    <node id="A"/>
    <node id="B"/>
    <node id="C"/>
    <node id="D"/>
    <node id="X"/>
    <node id="Y"/>
    <edge source="A" target="B"/>
    <edge source="B" target="C"/>
    <edge source="C" target="D"/>
    <edge source="X" target="Y"/>
  </graph>
</graphml>"""

def verify_largest_component():
    # 1. Initialize Network
    print_step("1. Initializing Network")
    network_id = int(time.time())
    graphml = get_disconnected_graphml()
    
    req = urllib.request.Request(
        f"{BASE_URL}/initialize",
        data=json.dumps({"network_id": network_id, "graphml_data": graphml}).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
        method="POST"
    )
    with urllib.request.urlopen(req) as response:
        result = json.loads(response.read().decode('utf-8'))
        # Ensure we use the ID returned by the API
        network_id = result["network_id"] 
        print(f"Network Initialized: {network_id}")

    # 2. Create Largest Component Subgraph
    print_step("2. Creating Largest Component Subgraph")
    req = urllib.request.Request(
        f"{BASE_URL}/{network_id}/subgraphs/largest-component",
        data=json.dumps({}).encode('utf-8'), # Empty body as per previous check, but POST usually requires length
        headers={'Content-Type': 'application/json'},
        method="POST"
    )
    with urllib.request.urlopen(req) as response:
        subgraph_data = json.loads(response.read().decode('utf-8'))
        # Adjust parsing based on typical response logic (usually returns new network obj/id)
        # subgraph.create_largest_component_subgraph returns the new network ID or object?
        # Let's assume it returns {new_network_id: ...} or similar based on `subgraphs.py` returning logic result.
        # Checking subgraphs.py: returns `subgraph.create_largest_component_subgraph(...)` result.
        # Assuming typical dict response.
        if "new_network_id" in subgraph_data:
             subgraph_id = subgraph_data["new_network_id"]
        elif "id" in subgraph_data: # If it returns the network object directly
             subgraph_id = subgraph_data["id"]
        else:
             subgraph_id = subgraph_data # Fallback if direct ID
             
        print(f"Subgraph ID: {subgraph_id}")

    # 3. Calculate Centrality on Subgraph
    print_step("3. Calculating Subgraph Centrality")
    req = urllib.request.Request(
        f"{BASE_URL}/{subgraph_id}/centrality",
        data=json.dumps({"centrality_type": "degree"}).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
        method="POST"
    )
    urllib.request.urlopen(req)

    # 3.5 Calculate Layout for Parent Network (Required for Visualization)
    print_step("3.5. Calculating Parent Network Layout")
    req = urllib.request.Request(
        f"{BASE_URL}/{network_id}/layout",
        data=json.dumps({"layout_name": "forceatlas2"}).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
        method="POST"
    )
    urllib.request.urlopen(req)

    # 4. Generate Visualization with Focus
    print_step("4. Generating Visualization")
    payload = {
        "layout_name": "forceatlas2",
        "focus_network_id": subgraph_id,
        "context_config": {"opacity": 0.1},
        "focus_config": {
            "node_size_config": {"attribute": "degree_centrality", "min": 10, "max": 50}
        }
    }
    
    req = urllib.request.Request(
        f"{BASE_URL}/{network_id}/visualization",
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
        method="POST"
    )
    
    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read().decode('utf-8'))
        
    nodes = data.get("nodes", [])
    print(f"Received {len(nodes)} nodes")
    
    # Check Node A (in largest component)
    node_a = next((n for n in nodes if n["id"] == "A"), None)
    # Check Node X (NOT in largest component)
    node_x = next((n for n in nodes if n["id"] == "X"), None)
    
    if node_a:
        print(f"Node A Opacity: {node_a.get('opacity')}")
        print(f"Node A Size: {node_a.get('size')}")
    
    if node_x:
        print(f"Node X Opacity: {node_x.get('opacity')}")
        print(f"Node X Size: {node_x.get('size')}")
        
    if node_a and node_a.get("opacity") == 1.0 and node_x and node_x.get("opacity") == 0.1:
        print("SUCCESS: Opacity correct.")
    else:
        print("FAILURE: Opacity incorrect.")

    if node_a and node_a.get("size") > 5:
        print("SUCCESS: Node A size updated from subgraph metric.")
    else:
        print(f"FAILURE: Node A size not updated (Size: {node_a.get('size') if node_a else 'N/A'}).")

if __name__ == "__main__":
    verify_largest_component()
