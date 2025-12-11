import urllib.request
import json
import sys

BASE_URL = "http://localhost:8001/api/v1"

def make_request(endpoint, data):
    url = f"{BASE_URL}/{endpoint}"
    req = urllib.request.Request(url, method="POST")
    req.add_header('Content-Type', 'application/json')
    json_data = json.dumps(data).encode('utf-8')
    try:
        with urllib.request.urlopen(req, data=json_data) as response:
            return 200, json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8')
    except Exception as e:
        return 500, str(e)

def verify_layout_preservation():
    # 1. Initialize a simple network
    graphml = """<?xml version="1.0" encoding="UTF-8"?>
<graphml xmlns="http://graphml.graphdrawing.org/xmlns"  
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xsi:schemaLocation="http://graphml.graphdrawing.org/xmlns
     http://graphml.graphdrawing.org/xmlns/1.0/graphml.xsd">
  <graph id="G" edgedefault="undirected">
    <node id="n0"/>
    <node id="n1"/>
    <node id="n2"/>
    <edge source="n0" target="n1"/>
    <edge source="n1" target="n2"/>
    <edge source="n2" target="n0"/>
  </graph>
</graphml>"""

    print("Initializing network...")
    # Using tools endpoint for initialization as it might handle parsing differently, 
    # but based on logic, let's use the standard flow if possible. 
    # Wait, initialize_network is likely a tool/endpoint. 
    # Let's check verify_layouts.py again. It used "http://localhost:8001/tools/initialize_network".
    # I should use that for setup.
    
    # Updated endpoints based on research
    # BASE_URL is http://localhost:8001/api/v1
    INITIALIZE_URL = f"{BASE_URL}/networks/initialize"
    
    def call_endpoint(url, payload):
        req = urllib.request.Request(url, method="POST")
        req.add_header('Content-Type', 'application/json')
        json_data = json.dumps(payload).encode('utf-8')
        try:
            with urllib.request.urlopen(req, data=json_data) as response:
                return 200, json.loads(response.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode('utf-8')

    print("Initializing network...")
    status, data = call_endpoint(INITIALIZE_URL, {"network_id": 8888, "graphml_data": graphml})
    if status != 200:
        print(f"Failed to initialize: {data}")
        sys.exit(1)
    
    network_id = data["network_id"]
    print(f"Network initialized: {network_id}")

    # 2. Calculate "circular" layout
    print("Calculating circular layout...")
    calc_layout_url = f"{BASE_URL}/networks/{network_id}/layout"
    status, _ = call_endpoint(calc_layout_url, {"layout_name": "circular"})
    if status != 200:
        print("Failed to calculate circular layout")
        sys.exit(1)


    # 3. Visualize with explicit circular layout to set "last_layout_name"
    print("Requesting visualization with layout='circular'...")
    # The endpoint is /api/v1/{network_id}/visualization
    vis_payload_explicit = {
        "layout_name": "circular"
    }
    status, vis_data = make_request(f"networks/{network_id}/visualization", vis_payload_explicit)
    if status != 200:
        print(f"Failed explicit vis: {vis_data}")
        sys.exit(1)
    
    nodes = vis_data["nodes"]
    # Check coords (circular usually puts nodes on unit circle)
    print(f"Nodes (explicit circular): {[ (n['x'], n['y']) for n in nodes]}")
    circular_coords = {n['id']: (n['x'], n['y']) for n in nodes}

    # 4. Update node size WITHOUT specifying layout
    print("\nRequesting visualization update (NO layout specified)...")
    vis_payload_update = {
        # Omit layout_name, triggering default
        "node_size_config": {"fixed_size": 20}
    }
    status, vis_data_update = make_request(f"networks/{network_id}/visualization", vis_payload_update)
    if status != 200:
        print(f"Failed update vis: {vis_data_update}")
        sys.exit(1)
        
    nodes_update = vis_data_update["nodes"]
    print(f"Nodes (update): {[ (n['x'], n['y']) for n in nodes_update]}")
    
    # Compare coordinates
    mismatch = False
    for n in nodes_update:
        nid = n['id']
        if nid in circular_coords:
            orig = circular_coords[nid]
            curr = (n['x'], n['y'])
            # Allow small float diffs, but forceatlas2 vs circular should be huge
            if abs(orig[0] - curr[0]) > 0.001 or abs(orig[1] - curr[1]) > 0.001:
                mismatch = True
                print(f"MISMATCH for {nid}: Was {orig}, Now {curr}")
    
    if mismatch:
        print("\n❌ FAIL: Layout changed unexpectedly!")
    else:
        print("\n✅ SUCCESS: Layout preserved.")

if __name__ == "__main__":
    verify_layout_preservation()
