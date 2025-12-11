
import urllib.request
import json
import time
import sys

BASE_URL = "http://localhost:8001/api/v1/networks"

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
            f"{BASE_URL}/initialize",
            data=json.dumps({"network_id": net_id, "graphml_data": graphml}).encode('utf-8'),
            headers={'Content-Type': 'application/json'},
            method='POST'
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

    # 3. Create Subgraph (Largest Component)
    print_step("3. Creating Subgraph (Largest Component)")
    try:
        req = urllib.request.Request(
            f"{BASE_URL}/{net_id}/subgraphs/largest-component",
            data=json.dumps({}).encode('utf-8'),
            headers={'Content-Type': 'application/json'},
            method='POST'
        )
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            sub_id = data['new_network_id']
            print(f"Subgraph ID: {sub_id}")
            
    except urllib.error.HTTPError as e:
        print(f"FAILURE: Request failed: {e}")
        # print error body
        print(e.read().decode())
        sys.exit(1)

    print("Success: Subgraph created.")

if __name__ == "__main__":
    verify_tools()
