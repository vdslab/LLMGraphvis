import requests
import json
import sys
import os
import time

BASE_URL = "http://localhost:8000"
USERNAME = "verify_top_nodes_user"
PASSWORD = "password123"

def verify_top_nodes_subgraph():
    session = requests.Session()
    
    # 1. Register/Login
    try:
        session.post(f"{BASE_URL}/auth/register", json={"username": USERNAME, "password": PASSWORD})
    except:
        pass

    resp = session.post(f"{BASE_URL}/auth/token", data={"username": USERNAME, "password": PASSWORD})
    if resp.status_code != 200:
        print(f"Failed to login: {resp.text}")
        return False
    token = resp.json()["access_token"]
    session.headers.update({"Authorization": f"Bearer {token}"})
        
    # 2. Create Chat
    resp = session.post(f"{BASE_URL}/chat", json={"name": "Top Nodes Chat"})
    chat_id = resp.json()["id"]
    print(f"Chat ID: {chat_id}")
    
    # 3. Upload Graph (Star Graph)
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
    <edge source="n0" target="n1"/>
    <edge source="n0" target="n2"/>
    <edge source="n0" target="n3"/>
  </graph>
</graphml>"""
    
    files = {"file": ("star.graphml", graphml.encode('utf-8'), "application/xml")}
    resp = session.post(f"{BASE_URL}/chat/{chat_id}/upload", files=files)
    if resp.status_code not in [200, 202]:
        print(f"Failed to upload: {resp.text}")
        return False
    time.sleep(2)
    
    # 4. Send Message: "Create a subgraph for the top 2 nodes by degree"
    print("Sending Message: 'Create a subgraph for the top 2 nodes by degree'...")
    payload = {
        "message": {
            "role": "user", 
            "content": "Create a subgraph for the top 2 nodes by degree"
        }
    }
    resp = session.post(f"{BASE_URL}/chat/{chat_id}/process", json=payload)
    
    print("Listening for events...")
    resp = session.get(f"{BASE_URL}/chat/{chat_id}/stream", stream=True)
    
    get_top_nodes_called = False
    create_subgraph_called = False
    visualize_called = False
    
    start_time = time.time()
    timeout = 60
    
    for line in resp.iter_lines():
        if time.time() - start_time > timeout:
            print("Timeout")
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
                        print(f"Tool: {tool_name} ({status}) Args: {args}")
                        
                        if tool_name == "get_top_nodes" and status == "completed":
                            get_top_nodes_called = True
                        
                        if tool_name == "create_subgraph_from_nodes" and status == "started":
                            node_ids = args.get("node_ids", [])
                            # n0 has degree 3, others have 1. Top 2 should be n0 and one of n1,n2,n3.
                            if "n0" in node_ids and len(node_ids) == 2:
                                print(f"Verified: create_subgraph_from_nodes called with correct nodes {node_ids}")
                                create_subgraph_called = True
                            else:
                                print(f"Warning: create_subgraph_from_nodes called with {node_ids}")

                        if tool_name == "generate_visualization" and status == "completed":
                            visualize_called = True

                    if "role" in data and (data["role"] == "model" or data["role"] == "assistant"):
                        print(f"Assistant: {data['content']}")
                        break
                        
                except json.JSONDecodeError:
                    pass
    
    if get_top_nodes_called and create_subgraph_called and visualize_called:
        return True
    else:
        return False

if __name__ == "__main__":
    if verify_top_nodes_subgraph():
        print("\nVerification SUCCESS")
        sys.exit(0)
    else:
        print("\nVerification FAILED")
        sys.exit(1)
