import urllib.request
import json
import sys

BASE_URL = "http://localhost:8001/api/v1"

def make_request(endpoint, method="GET", data=None):
    url = f"{BASE_URL}/{endpoint}"
    req = urllib.request.Request(url, method=method)
    req.add_header('Content-Type', 'application/json')
    if data:
        json_data = json.dumps(data).encode('utf-8')
    else:
        json_data = None
        
    try:
        with urllib.request.urlopen(req, data=json_data) as response:
            return 200, json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8')
    except Exception as e:
        return 500, str(e)

def verify_metadata():
    # 1. Initialize
    graphml = """<?xml version="1.0" encoding="UTF-8"?>
<graphml xmlns="http://graphml.graphdrawing.org/xmlns"><graph id="G"><node id="n0"/></graph></graphml>"""

    print("Initializing network...")
    status, data = make_request("networks/initialize", "POST", {"network_id": 7777, "graphml_data": graphml})
    if status != 200:
        print(f"Failed to initialize: {data}")
        sys.exit(1)
    
    network_id = data["network_id"]
    
    # 2. Set layout to circle
    print("Calculating circle layout to set state...")
    make_request(f"networks/{network_id}/layout", "POST", {"layout_name": "circle"})
    
    # 3. Generate visualization (this commits the state to DB)
    print("Generating visualization to commit state...")
    make_request(f"networks/{network_id}/visualization", "POST", {"layout_name": "circle"})
    
    # 4. Check metadata
    print("Checking metadata for last_layout_name...")
    status, meta = make_request(f"networks/{network_id}/metadata", "GET")
    
    if status != 200:
         print(f"Failed to get metadata: {meta}")
         sys.exit(1)
         
    print(f"Metadata: {meta}")
    
    if meta.get("last_layout_name") == "circle":
        print("✅ SUCCESS: last_layout_name is 'circle'")
    else:
        print(f"❌ FAIL: last_layout_name is {meta.get('last_layout_name')}")

if __name__ == "__main__":
    verify_metadata()
