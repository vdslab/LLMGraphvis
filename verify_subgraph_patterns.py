import urllib.request
import json
import time

BASE_URL = "http://localhost:8001/tools"

def print_step(msg):
    print(f"\n{'='*50}\n{msg}\n{'='*50}")

def post_json(url, data):
    req = urllib.request.Request(
        url, 
        data=json.dumps(data).encode('utf-8'), 
        headers={'Content-Type': 'application/json'}
    )
    try:
        with urllib.request.urlopen(req) as response:
            return response.status, json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8')
    except Exception as e:
        return 500, str(e)

def get_simple_graphml():
    # A simple graph with a central node 'Valjean' and a few connected nodes
    return """<?xml version="1.0" encoding="UTF-8"?>
<graphml xmlns="http://graphml.graphdrawing.org/xmlns"  
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xsi:schemaLocation="http://graphml.graphdrawing.org/xmlns
     http://graphml.graphdrawing.org/xmlns/1.0/graphml.xsd">
  <graph id="G" edgedefault="undirected">
    <node id="Valjean"/>
    <node id="Cosette"/>
    <node id="Marius"/>
    <node id="Javert"/>
    <node id="Fantine"/>
    <node id="Thenardier"/>
    <edge source="Valjean" target="Cosette"/>
    <edge source="Valjean" target="Marius"/>
    <edge source="Valjean" target="Javert"/>
    <edge source="Valjean" target="Fantine"/>
    <edge source="Cosette" target="Marius"/>
    <edge source="Javert" target="Thenardier"/>
  </graph>
</graphml>"""

def test_subgraph_patterns():
    # 1. Initialize Network
    print_step("1. Initializing Simple Network")
    graphml_data = get_simple_graphml()
    
    # Use a unique ID to avoid conflicts
    network_id = int(time.time())
    
    status, response = post_json(f"{BASE_URL}/initialize_network", {
        "network_id": network_id,
        "graphml_data": graphml_data
    })
    print(f"Initialize Response: {status}")
    if status != 200:
        print(response)
        return

    # Calculate Global Centrality (Degree)
    print_step("2. Calculating Global Degree Centrality")
    post_json(f"{BASE_URL}/calculate_centrality", {
        "network_id": network_id,
        "centrality_type": "degree"
    })

    # 2. Create Subgraph (Ego Network of 'Valjean')
    print_step("3. Creating Ego Network for 'Valjean'")
    status, response = post_json(f"{BASE_URL}/create_ego_network", {
        "source_network_id": network_id,
        "center_node_id": "Valjean",
        "radius": 1
    })
    print(f"Create Subgraph Response: {status}")
    if status != 200:
        print(response)
        return
        
    subgraph_data = response
    subgraph_id = subgraph_data["new_network_id"]
    print(f"Subgraph ID: {subgraph_id}")

    # Calculate Subgraph Centrality (Betweenness) - DIFFERENT from Global
    print_step("4. Calculating Subgraph Betweenness Centrality")
    post_json(f"{BASE_URL}/calculate_centrality", {
        "network_id": subgraph_id,
        "centrality_type": "betweenness"
    })

    # --- Test Pattern 1: Global Focus ---
    print_step("5. Testing Pattern 1: Global Focus (Highlight Only)")
    # Goal: Show whole graph, highlight subgraph. Size by GLOBAL degree.
    payload_p1 = {
        "network_id": network_id,
        "focus_network_id": subgraph_id,
        "node_size_config": {"attribute": "degree_centrality", "min": 5, "max": 15},
        "context_config": {"opacity": 0.1, "color": "#cccccc"}
    }
    status, response = post_json(f"{BASE_URL}/generate_visualization", payload_p1)
    print(f"Pattern 1 Response: {status}")
    if status == 200:
        data = response
        nodes = data["nodes"]
        # Check if Valjean is highlighted (opacity 1.0) and others are dimmed (0.1)
        valjean = next((n for n in nodes if n["id"] == "Valjean"), None)
        other = next((n for n in nodes if n["opacity"] == 0.1), None)
        
        print(f"Valjean Opacity: {valjean['opacity'] if valjean else 'Not Found'}")
        print(f"Context Node Opacity: {other['opacity'] if other else 'Not Found'}")
        
        if valjean and valjean['opacity'] == 1.0 and other and other['opacity'] == 0.1:
            print("SUCCESS: Pattern 1 verified.")
        else:
            print("FAILURE: Pattern 1 opacity check failed.")

    # --- Test Pattern 2: Contextual Subgraph ---
    print_step("6. Testing Pattern 2: Contextual Subgraph (Focus + Context)")
    # Goal: Show whole graph, highlight subgraph. Size subgraph nodes by SUBGRAPH betweenness.
    payload_p2 = {
        "network_id": network_id,
        "focus_network_id": subgraph_id,
        "context_config": {"opacity": 0.1},
        "focus_config": {
            "node_size_config": {"attribute": "betweenness_centrality", "min": 10, "max": 30},
            "node_color_config": {"static_color": "#FF0000"}
        }
    }
    status, response = post_json(f"{BASE_URL}/generate_visualization", payload_p2)
    print(f"Pattern 2 Response: {status}")
    if status == 200:
        data = response
        nodes = data["nodes"]
        valjean = next((n for n in nodes if n["id"] == "Valjean"), None)
        
        # Check color override
        print(f"Valjean Color: {valjean['color'] if valjean else 'Not Found'}")
        
        # Check size (should be calculated from betweenness, likely larger than min default)
        print(f"Valjean Size: {valjean['size'] if valjean else 'Not Found'}")
        
        if valjean and valjean['color'] == "#FF0000":
             print("SUCCESS: Pattern 2 verified (Color Override).")
        else:
             print("FAILURE: Pattern 2 color check failed.")

    # --- Test Pattern 3: Isolated Subgraph ---
    print_step("7. Testing Pattern 3: Isolated Subgraph")
    # Goal: Show only subgraph.
    # First calculate layout for subgraph
    post_json(f"{BASE_URL}/calculate_layout", {"network_id": subgraph_id, "layout_name": "circular"})
    
    payload_p3 = {
        "network_id": subgraph_id,
        "layout_name": "circular",
        "node_size_config": {"attribute": "betweenness_centrality", "min": 5, "max": 20}
    }
    status, response = post_json(f"{BASE_URL}/generate_visualization", payload_p3)
    print(f"Pattern 3 Response: {status}")
    if status == 200:
        data = response
        nodes = data["nodes"]
        print(f"Total Nodes in Visualization: {len(nodes)}")
        
        # Should be fewer than total network (77 nodes in Les Mis)
        if 0 < len(nodes) < 77:
             print("SUCCESS: Pattern 3 verified (Subset of nodes).")
        else:
             print(f"FAILURE: Pattern 3 node count unexpected: {len(nodes)}")

if __name__ == "__main__":
    test_subgraph_patterns()
