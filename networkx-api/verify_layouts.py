import urllib.request
import json
import sys

BASE_URL = "http://localhost:8001/tools"

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

def verify_layouts():
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
    <node id="n3"/>
    <node id="n4"/>
    <edge source="n0" target="n1"/>
    <edge source="n1" target="n2"/>
    <edge source="n2" target="n3"/>
    <edge source="n3" target="n4"/>
    <edge source="n4" target="n0"/>
  </graph>
</graphml>"""

    print("Initializing network...")
    status, data = make_request("initialize_network", {"network_id": 9999, "graphml_data": graphml})
    
    if status != 200:
        print(f"Failed to initialize network: {data}")
        sys.exit(1)
    
    network_id = data["network_id"]
    print(f"Network initialized with ID: {network_id}")

    layouts_to_test = [
        "spring", 
        "fruchterman_reingold", 
        "forceatlas2", 
        "kamada_kawai", 
        "spiral"
    ]

    for layout in layouts_to_test:
        print(f"\nTesting layout: {layout}...")
        
        # Calculate layout
        status, calc_resp = make_request("calculate_layout", {"network_id": network_id, "layout_name": layout})
        if status != 200:
            print(f"❌ Failed to calculate layout {layout}: {calc_resp}")
            continue
            
        # Get visualization
        status, vis_data = make_request("generate_visualization", {"network_id": network_id, "layout_name": layout})
        if status != 200:
            print(f"❌ Failed to generate visualization for {layout}: {vis_data}")
            continue
            
        nodes = vis_data.get("nodes", [])
        
        if not nodes:
            print(f"❌ No nodes returned for {layout}")
            continue
            
        valid_coords = True
        for node in nodes[:3]: 
            if "x" not in node or "y" not in node:
                valid_coords = False
                break
                
        if valid_coords:
            print(f"✅ Layout {layout} verification successful. Sample node: {nodes[0]['x']}, {nodes[0]['y']}")
        else:
            print(f"❌ Layout {layout} returned invalid coordinates.")

if __name__ == "__main__":
    verify_layouts()
