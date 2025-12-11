import requests
import json
import sys

# Configuration
BACKEND_URL = "http://localhost:8000"
USERNAME = "testuser_verify"
PASSWORD = "testpassword"

def run_verification():
    print("Starting verification...")

    # 1. Register/Login
    print("1. Authenticating...")
    session = requests.Session()
    
    # Register
    try:
        resp = session.post(f"{BACKEND_URL}/auth/register", json={"username": USERNAME, "password": PASSWORD})
        if resp.status_code == 409:
            print("   User already exists, logging in...")
        elif resp.status_code != 200:
            print(f"   Registration failed: {resp.text}")
            return
    except Exception as e:
        print(f"   Connection failed: {e}")
        return

    # Login
    resp = session.post(f"{BACKEND_URL}/auth/token", data={"username": USERNAME, "password": PASSWORD})
    if resp.status_code != 200:
        print(f"   Login failed: {resp.text}")
        return
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("   Authentication successful.")

    # 2. Upload Graph
    print("2. Creating Chat and Uploading Graph...")
    # Create Chat
    chat_resp = requests.post(f"{BACKEND_URL}/chat", json={"name": "Verify Endpoint Chat"}, headers=headers)
    if chat_resp.status_code != 200:
        print(f"   Create chat failed: {chat_resp.text}")
        return
    chat_data = chat_resp.json()
    chat_id = chat_data["id"]
    network_id = chat_data["network_id"]
    print(f"   Chat created: id={chat_id}, network_id={network_id}")
    
    # Upload simple GraphML
    graphml_content = """<?xml version="1.0" encoding="UTF-8"?>
<graphml xmlns="http://graphml.graphdrawing.org/xmlns" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://graphml.graphdrawing.org/xmlns http://graphml.graphdrawing.org/xmlns/1.0/graphml.xsd">
  <key id="d0" for="node" attr.name="label" attr.type="string"/>
  <graph id="G" edgedefault="undirected">
    <node id="n0">
      <data key="d0">Node A</data>
    </node>
    <node id="n1">
      <data key="d0">Node B</data>
    </node>
    <node id="n2">
      <data key="d0">Node C</data>
    </node>
    <edge source="n0" target="n1"/>
  </graph>
</graphml>"""
    
    files = {'file': ('test.graphml', graphml_content, 'application/xml')}
    upload_resp = requests.post(f"{BACKEND_URL}/chat/{chat_id}/upload", files=files, headers=headers)
    if upload_resp.status_code != 202:
        print(f"   Upload failed: {upload_resp.text}")
        return
    print("   Upload accepted. Waiting for processing (5s)...")
    import time
    time.sleep(5) 
    
    # 3. Test New Endpoint
    print("3. Testing component_containing_node endpoint...")
    # We know n0 is connected to n1, but n2 is isolated (depending on edge def). 
    # Actually in my graphml: n0-n1 are connected. n2 is isolated. 
    # So component of n0 should have 2 nodes.
    
    target_node = "n0"
    payload = {"node_id": target_node}
    
    endpoint = f"{BACKEND_URL}/networks/{network_id}/subgraphs/component_containing_node"
    print(f"   POST {endpoint} with node_id={target_node}")
    
    resp = requests.post(endpoint, json=payload, headers=headers)
    
    if resp.status_code == 200:
        result = resp.json()
        print("   Success!")
        print(f"   Result: {json.dumps(result, indent=2)}")
        
        # Verify result structure
        if "network_id" in result and "name" in result:
             print("   Result structure is valid.")
        else:
             print("   Result structure unexpected.")
             
    else:
        print(f"   Failed: {resp.status_code} - {resp.text}")

if __name__ == "__main__":
    run_verification()
