
import urllib.request
import json
import time
import sys

BASE_URL = "http://localhost:8001/tools"

def print_step(msg):
    print(f"\n{'='*50}\n{msg}\n{'='*50}")

def verify_tools():
    # 1. Initialize Main Network
    print_step("1. Initializing Main Network")
    net_id = int(time.time())
    graphml = """<?xml version="1.0" encoding="UTF-8"?>
<graphml xmlns="http://graphml.graphdrawing.org/xmlns">
  <graph id="G" edgedefault="undirected">
    <node id="A"/>
    <node id="B"/>
    <edge source="A" target="B"/>
  </graph>
</graphml>"""
    
    try:
        req = urllib.request.Request(
            f"{BASE_URL}/initialize_network",
            data=json.dumps({"network_id": net_id, "graphml_data": graphml}).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            print(f"Status: {data.get('status', 'success')}")
            # Check if network_id is returned
            if 'network_id' in data:
                print(f"Returned Network ID: {data['network_id']}")
        print("Network initialized.")
    except Exception as e:
        print(f"Failed to initialize: {e}")
        sys.exit(1)

    print_step("2. Triggering Duplicate (Should succeed with NEW ID)")
    try:
        req = urllib.request.Request(
            f"{BASE_URL}/initialize_network",
            data=json.dumps({"network_id": net_id, "graphml_data": graphml}).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            print(f"Status: {data.get('status', 'success')}")
            if 'network_id' in data:
                new_id = data['network_id']
                print(f"Returned Network ID: {new_id}")
                if new_id != net_id:
                    print(f"SUCCESS: Network ID changed from {net_id} to {new_id}")
                else:
                    print(f"FAILURE: Network ID did NOT change (remained {net_id})")
            else:
                print("FAILURE: No network_id returned")

    except urllib.error.HTTPError as e:
        print(f"FAILURE: Request failed: {e}")

    # 3. Create Subgraph
    print_step("3. Creating Subgraph")
    req = urllib.request.Request(
        f"{BASE_URL}/create_largest_component_subgraph",
        data=json.dumps({"source_network_id": net_id}).encode('utf-8'),
        headers={'Content-Type': 'application/json'}
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode('utf-8'))
        sub_id = data['new_network_id']
        print(f"Subgraph ID: {sub_id}")

    # 4. Test Tool Execution on Subgraph (via network_id param)
    # NOTE: This tests the *backend endpoint*, not the LLM tool definition directly.
    # The backend endpoint ALREADY accepts network_id in the body.
    # The issue is the LLM tool definition not exposing it.
    print_step("4. Testing Backend Support for Subgraph Operations")
    
    try:
        # Centrality on Subgraph
        req = urllib.request.Request(
            f"{BASE_URL}/calculate_centrality",
            data=json.dumps({"network_id": sub_id, "centrality_type": "degree"}).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )
        urllib.request.urlopen(req)
        print("Success: Backend supports centrality on subgraph.")
    except Exception as e:
        print(f"Failure: {e}")

if __name__ == "__main__":
    verify_tools()
