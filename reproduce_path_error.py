import requests
import json
import sys
import os
import time

BASE_URL = "http://localhost:8000"
USERNAME = "reproduce_path_user"
PASSWORD = "password123"

def reproduce_path_error():
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
    resp = session.post(f"{BASE_URL}/chat", json={"name": "Path Error Chat"})
    chat_id = resp.json()["id"]
    network_id = resp.json()["network_id"]
    print(f"Chat ID: {chat_id}, Network ID: {network_id}")
    
    # 3. Upload Graph (Nodes "0" and "33")
    graphml = """<?xml version="1.0" encoding="UTF-8"?>
<graphml xmlns="http://graphml.graphdrawing.org/xmlns"  
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xsi:schemaLocation="http://graphml.graphdrawing.org/xmlns
     http://graphml.graphdrawing.org/xmlns/1.0/graphml.xsd">
  <graph id="G" edgedefault="undirected">
    <node id="0"/>
    <node id="33"/>
    <edge source="0" target="33"/>
  </graph>
</graphml>"""
    
    files = {"file": ("test_path.graphml", graphml.encode('utf-8'), "application/xml")}
    resp = session.post(f"{BASE_URL}/chat/{chat_id}/upload", files=files)
    if resp.status_code not in [200, 202]:
        print(f"Failed to upload: {resp.text}")
        return False
    time.sleep(2)
    
    # 4. Call create_path_subgraph with "node 33" (Mismatch)
    print("Attempting create_path_subgraph with 'node 33' (expected failure if strict)...")
    payload = {
        "source_network_id": network_id,
        "source_node_id": "node 33",
        "target_node_id": "0" # "0" might match if ID is "0"
    }
    
    # We call the NetworkXAPI endpoint directly via backend proxy or just assume the tool call structure
    # The backend exposes /networks/{id}/subgraphs/path
    
    resp = session.post(
        f"{BASE_URL}/networks/{network_id}/subgraphs/path",
        json=payload
    )
    
    print(f"Response Status: {resp.status_code}")
    print(f"Response Text: {resp.text}")
    
    if resp.status_code == 500:
        print("Reproduced 500 Internal Server Error")
        return True
    elif resp.status_code == 400 or resp.status_code == 404:
        print("Got 4xx error (handled gracefully?)")
        return False
    else:
        print("Unexpected success or other error")
        return False

if __name__ == "__main__":
    if reproduce_path_error():
        sys.exit(0)
    else:
        sys.exit(1)
