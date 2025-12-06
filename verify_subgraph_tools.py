
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
        urllib.request.urlopen(req)
        print("Network initialized.")
    except Exception as e:
        print(f"Failed to initialize: {e}")
        sys.exit(1)

    # 2. Trigger Duplicate Error (Reproduction)
    print_step("2. Triggering Duplicate Error (Should fail if not fixed)")
    try:
        req = urllib.request.Request(
            f"{BASE_URL}/initialize_network",
            data=json.dumps({"network_id": net_id, "graphml_data": graphml}).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )
        urllib.request.urlopen(req)
        print("Warning: Duplicate initialization succeeded (unexpected if not fixed).")
    except urllib.error.HTTPError as e:
        print(f"Caught expected error (if not fixed): {e}")

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
