import urllib.request
import json
import time

BASE_URL = "http://localhost:8000/api/v1"

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
    return """<?xml version="1.0" encoding="UTF-8"?>
<graphml xmlns="http://graphml.graphdrawing.org/xmlns"  
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xsi:schemaLocation="http://graphml.graphdrawing.org/xmlns
     http://graphml.graphdrawing.org/xmlns/1.0/graphml.xsd">
  <graph id="G" edgedefault="undirected">
    <node id="Valjean"/>
    <node id="Cosette"/>
    <edge source="Valjean" target="Cosette"/>
  </graph>
</graphml>"""

def verify_sse_payload():
    # 1. Initialize Network via NetworkXAPI
    print_step("1. Initializing Network")
    network_id = int(time.time())
    graphml = get_simple_graphml()
    
    req = urllib.request.Request(
        "http://localhost:8001/tools/initialize_network",
        data=json.dumps({"network_id": network_id, "graphml_data": graphml}).encode('utf-8'),
        headers={'Content-Type': 'application/json'}
    )
    urllib.request.urlopen(req)

    # 2. Create Ego Network for 'Valjean'
    print_step("2. Creating Ego Network")
    req = urllib.request.Request(
        "http://localhost:8001/tools/create_ego_network",
        data=json.dumps({"source_network_id": network_id, "center_node_id": "Valjean", "radius": 0}).encode('utf-8'),
        headers={'Content-Type': 'application/json'}
    )
    with urllib.request.urlopen(req) as response:
        subgraph_data = json.loads(response.read().decode('utf-8'))
        subgraph_id = subgraph_data["new_network_id"]
        print(f"Subgraph ID: {subgraph_id}")

    # 3. Call generate_visualization with focus_network_id
    print_step("3. Checking Visualization Payload")
    payload = {
        "network_id": network_id,
        "focus_network_id": subgraph_id,
        "context_config": {"opacity": 0.1}
    }
    
    req = urllib.request.Request(
        "http://localhost:8001/tools/generate_visualization",
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'}
    )
    
    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read().decode('utf-8'))
        
    nodes = data.get("nodes", [])
    print(f"Received {len(nodes)} nodes")
    
    valjean = next((n for n in nodes if n["id"] == "Valjean"), None)
    cosette = next((n for n in nodes if n["id"] == "Cosette"), None)
    
    if valjean:
        print(f"Valjean opacity: {valjean.get('opacity')}")
    if cosette:
        print(f"Cosette opacity: {cosette.get('opacity')}")
        
    if valjean and valjean.get("opacity") == 1.0 and cosette and cosette.get("opacity") == 0.1:
        print("SUCCESS: Opacity is correct (Valjean=1.0, Cosette=0.1).")
    else:
        print("FAILURE: Opacity incorrect.")

if __name__ == "__main__":
    verify_sse_payload()
