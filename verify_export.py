import urllib.request
import urllib.parse
import json
import time

BASE_URL = "http://localhost:8000"
NX_API_URL = "http://localhost:8001"

def test_export():
    print("Testing Export functionality...")
    
    # 1. Initialize Network with Data via NetworkXAPI
    graphml_data = """<?xml version="1.0" encoding="UTF-8"?>
<graphml xmlns="http://graphml.graphdrawing.org/xmlns">
    <graph id="G" edgedefault="undirected">
        <node id="n0">
            <data key="label">Node 0</data>
            <data key="weight">1.5</data>
        </node>
        <node id="n1">
            <data key="label">Node 1</data>
            <data key="weight">2.0</data>
        </node>
        <edge id="e0" source="n0" target="n1">
            <data key="weight">0.5</data>
        </edge>
    </graph>
</graphml>
"""
    
    # This ID must be unique
    net_id = 9999
    
    # Initialize
    print(f"Initializing Network {net_id}...")
    url = f"{NX_API_URL}/tools/initialize_network"
    payload = json.dumps({"network_id": net_id, "graphml_data": graphml_data}).encode('utf-8')
    req = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json'}, method='POST')
    
    try:
        with urllib.request.urlopen(req) as f:
            resp_json = json.loads(f.read().decode('utf-8'))
            final_id = resp_json['network_id']
            print(f"Network Initialized. ID: {final_id}")
            
            # Export
            print(f"Exporting Network {final_id}...")
            export_url = f"{NX_API_URL}/tools/export_network?network_id={final_id}"
            with urllib.request.urlopen(export_url) as f_export:
                content = f_export.read().decode('utf-8')
                print("Export successful!")
                print("Content Preview:")
                print(content[:200])
                
                if "Node 0" in content and "Node 1" in content:
                        print("SUCCESS: Nodes found in export.")
                else:
                        print("FAILURE: Nodes missing in export.")

    except urllib.error.URLError as e:
        print(f"Request failed: {e}")
        if hasattr(e, 'read'):
            print(e.read().decode('utf-8'))
