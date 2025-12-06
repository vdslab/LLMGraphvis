import urllib.request
import json
import time

BASE_URL = "http://localhost:8001/tools"

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
        f"{BASE_URL}/initialize_network",
        data=json.dumps({"network_id": network_id, "graphml_data": graphml}).encode('utf-8'),
        headers={'Content-Type': 'application/json'}
    )
    urllib.request.urlopen(req)

    # 2. Create Largest Component Subgraph
    print_step("2. Creating Largest Component Subgraph")
    req = urllib.request.Request(
        f"{BASE_URL}/create_largest_component_subgraph",
        data=json.dumps({"source_network_id": network_id}).encode('utf-8'),
        headers={'Content-Type': 'application/json'}
    )
    with urllib.request.urlopen(req) as response:
        subgraph_data = json.loads(response.read().decode('utf-8'))
        subgraph_id = subgraph_data["new_network_id"]
        print(f"Subgraph ID: {subgraph_id}")

    # 3. Calculate Centrality on Subgraph (e.g., Degree)
    # In the subgraph (A-B-C-D), B and C have degree 2, A and D have degree 1.
    # In the global graph, it's the same, so let's use a metric that might differ or just check if values exist.
    print_step("3. Calculating Subgraph Centrality")
    req = urllib.request.Request(
        f"{BASE_URL}/calculate_centrality",
        data=json.dumps({"network_id": subgraph_id, "centrality_type": "degree"}).encode('utf-8'),
        headers={'Content-Type': 'application/json'}
    )
    urllib.request.urlopen(req)

    # 4. Generate Visualization with Focus
    print_step("4. Generating Visualization")
    payload = {
        "network_id": network_id,
        "focus_network_id": subgraph_id,
        "context_config": {"opacity": 0.1},
        "focus_config": {
            "node_size_config": {"attribute": "degree_centrality", "min": 10, "max": 50}
        }
    }
    
    req = urllib.request.Request(
        f"{BASE_URL}/generate_visualization",
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'}
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
        # Node A should have size > 5 (default) because it has centrality in subgraph
    
    if node_x:
        print(f"Node X Opacity: {node_x.get('opacity')}")
        print(f"Node X Size: {node_x.get('size')}")
        # Node X should have default size (5) because it's not in focus
        
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
