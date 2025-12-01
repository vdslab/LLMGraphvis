import requests
import json
import sys
import os
import time

BASE_URL = "http://localhost:8000"
USERNAME = "verify_node_aware_user"
PASSWORD = "password123"

def verify_llm_node_awareness():
    session = requests.Session()
    
    # 1. Register
    print("1. Registering...")
    try:
        resp = session.post(f"{BASE_URL}/auth/register", json={"username": USERNAME, "password": PASSWORD})
    except Exception as e:
        print(f"Registration error (might already exist): {e}")

    # 2. Login
    print("2. Logging in...")
    resp = session.post(f"{BASE_URL}/auth/token", data={"username": USERNAME, "password": PASSWORD})
    if resp.status_code != 200:
        print(f"Failed to login: {resp.text}")
        return False
    token = resp.json()["access_token"]
    session.headers.update({"Authorization": f"Bearer {token}"})
        
    # 3. Create Chat
    print("3. Creating Chat...")
    resp = session.post(f"{BASE_URL}/chat", json={"name": "Node Awareness Chat"})
    if resp.status_code != 200:
        print(f"Failed to create chat: {resp.text}")
        return False
    chat_id = resp.json()["id"]
    print(f"   Chat ID: {chat_id}")
    
    # 4. Upload Graph
    print("4. Uploading Graph...")
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
    <edge source="n0" target="n2"/>
    <edge source="n0" target="n3"/>
    <edge source="n0" target="n4"/>
  </graph>
</graphml>"""
    
    files = {"file": ("star_graph.graphml", graphml.encode('utf-8'), "application/xml")}
    resp = session.post(f"{BASE_URL}/chat/{chat_id}/upload", files=files)
    if resp.status_code not in [200, 202]:
        print(f"Failed to upload graph: {resp.status_code} - {resp.text}")
        return False
    
    print("   Upload accepted. Waiting for processing...")
    time.sleep(3) 
            
    # 5. Send Message & Listen to SSE
    print("5. Sending Message: 'Find the most important node by degree and create an ego network for it.'...")
    
    payload = {
        "message": {
            "role": "user", 
            "content": "Find the most important node by degree and create an ego network for it."
        }
    }
    resp = session.post(f"{BASE_URL}/chat/{chat_id}/process", json=payload)
    if resp.status_code not in [200, 202]:
        print(f"Failed to send message: {resp.status_code} - {resp.text}")
        return False
        
    print("6. Listening for events...")
    resp = session.get(f"{BASE_URL}/chat/{chat_id}/stream", stream=True)
    
    get_top_nodes_called = False
    create_ego_network_called = False
    
    start_time = time.time()
    timeout = 60
    
    for line in resp.iter_lines():
        if time.time() - start_time > timeout:
            print("   Timeout waiting for response.")
            break
            
        if line:
            decoded_line = line.decode('utf-8')
            if decoded_line.startswith("data:"):
                data_str = decoded_line[5:].strip()
                try:
                    data = json.loads(data_str)
                    
                    if "tool" in data:
                        tool_name = data["tool"]
                        status = data.get("status")
                        args = data.get("args", {})
                        print(f"   Tool: {tool_name} ({status}) Args: {args}")
                        
                        if tool_name == "get_top_nodes" and status == "completed":
                            get_top_nodes_called = True
                        
                        if tool_name == "create_ego_network" and status == "started":
                            # Check if it picked the right node (n0 has highest degree)
                            center_node = args.get("center_node_id")
                            if center_node == "n0":
                                print("   Verified: create_ego_network called with correct node 'n0'")
                                create_ego_network_called = True
                            else:
                                print(f"   Warning: create_ego_network called with '{center_node}', expected 'n0'")

                    if "role" in data and (data["role"] == "model" or data["role"] == "assistant"):
                        print(f"   Assistant: {data['content']}")
                        break
                        
                except json.JSONDecodeError:
                    pass
    
    if get_top_nodes_called:
        print("SUCCESS: get_top_nodes tool was called.")
    else:
        print("FAILED: get_top_nodes tool was not called.")

    if create_ego_network_called:
        print("SUCCESS: create_ego_network tool was called with correct node.")
    else:
        print("FAILED: create_ego_network tool was not called correctly.")
        
    if get_top_nodes_called and create_ego_network_called:
        return True
    else:
        return False

if __name__ == "__main__":
    if verify_llm_node_awareness():
        print("\nVerification SUCCESS")
        sys.exit(0)
    else:
        print("\nVerification FAILED")
        sys.exit(1)
