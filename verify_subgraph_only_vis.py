import requests
import json
import sys
import os
import time

BASE_URL = "http://localhost:8000"
USERNAME = "verify_subgraph_vis_user"
PASSWORD = "password123"

def verify_subgraph_visualization():
    session = requests.Session()
    
    # 1. Register
    print("1. Registering...")
    resp = session.post(f"{BASE_URL}/auth/register", json={"username": USERNAME, "password": PASSWORD})
    if resp.status_code not in [200, 409]:
        print(f"Failed to register: {resp.text}")
        return False
        
    # 2. Login
    print("2. Logging in...")
    resp = session.post(f"{BASE_URL}/auth/token", data={"username": USERNAME, "password": PASSWORD})
    if resp.status_code != 200:
        print(f"Failed to login: {resp.text}")
        return False
        
    # 3. Create Chat
    print("3. Creating Chat...")
    resp = session.post(f"{BASE_URL}/chat", json={"name": "Subgraph Vis Chat"})
    if resp.status_code != 200:
        print(f"Failed to create chat: {resp.text}")
        return False
    chat_id = resp.json()["id"]
    print(f"   Chat ID: {chat_id}")
    
    # 4. Upload Graph
    print("4. Uploading Graph...")
    if not os.path.exists("sample_data/karate_club.graphml"):
        print("Error: sample_data/karate_club.graphml not found")
        return False
        
    with open("sample_data/karate_club.graphml", "rb") as f:
        files = {"file": ("karate_club.graphml", f, "application/xml")}
        resp = session.post(f"{BASE_URL}/chat/{chat_id}/upload", files=files)
        if resp.status_code not in [200, 202]:
            print(f"Failed to upload graph: {resp.status_code} - {resp.text}")
            return False
    
    print("   Upload accepted. Waiting for processing...")
    time.sleep(3) # Wait for background task
            
    # 5. Step 1: Create Ego Network
    print("5. Step 1: Sending Message: 'Node 1のEgo Networkを作成してください'...")
    
    payload = {
        "message": {
            "role": "user", 
            "content": "Node 1のEgo Networkを作成してください"
        }
    }
    resp = session.post(f"{BASE_URL}/chat/{chat_id}/process", json=payload)
    if resp.status_code not in [200, 202]:
        print(f"Failed to send message: {resp.status_code} - {resp.text}")
        return False
        
    print("6. Listening for subgraph creation...")
    # Manual SSE parsing
    resp = session.get(f"{BASE_URL}/chat/{chat_id}/stream", stream=True)
    
    subgraph_id = None
    
    start_time = time.time()
    timeout = 60 
    
    for line in resp.iter_lines():
        if time.time() - start_time > timeout:
            print("   Timeout waiting for subgraph creation.")
            break
            
        if line:
            decoded_line = line.decode('utf-8')
            if decoded_line.startswith("data:"):
                data_str = decoded_line[5:].strip()
                print(f"DEBUG: {data_str}")
                try:
                    data = json.loads(data_str)
                    
                    if "tool" in data:
                        tool_name = data["tool"]
                        status = data.get("status")
                        result = data.get("result")
                        
                        if tool_name == "create_ego_network" and status == "completed":
                            if result and isinstance(result, dict) and "subgraph_id" in result:
                                subgraph_id = result["subgraph_id"]
                                print(f"   Subgraph Created: ID={subgraph_id}")
                                break 
                        
                        if tool_name == "generate_visualization" and status == "started":
                            args = data.get("args", {})
                            if "focus_network_id" in args:
                                subgraph_id = args["focus_network_id"]
                                print(f"   Found subgraph_id in generate_visualization args: {subgraph_id}")
                                break

                                
                    if "role" in data and data["role"] == "model":
                        # If model responds without tool, we might have missed it or it failed
                        pass
                        
                except json.JSONDecodeError:
                    pass
    
    if not subgraph_id:
        print("FAILED: Could not get subgraph_id.")
        return False
        
    # 7. Step 2: Visualize Subgraph Only
    print(f"7. Step 2: Sending Message: 'Network ID {subgraph_id} を、メインのネットワークとして（focusではなく）表示してください。'...")
    
    payload = {
        "message": {
            "role": "user", 
            "content": f"Network ID {subgraph_id} を、メインのネットワークとして（focusではなく）表示してください。"
        }
    }
    resp = session.post(f"{BASE_URL}/chat/{chat_id}/process", json=payload)
    if resp.status_code not in [200, 202]:
        print(f"Failed to send message: {resp.status_code} - {resp.text}")
        return False
        
    print("8. Listening for visualization...")
    resp = session.get(f"{BASE_URL}/chat/{chat_id}/stream", stream=True)
    
    visualization_generated = False
    
    start_time = time.time()
    
    for line in resp.iter_lines():
        if time.time() - start_time > timeout:
            print("   Timeout waiting for visualization.")
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
                        print(f"   Tool: {tool_name} ({status})")
                        
                        if tool_name == "generate_visualization" and status == "started":
                            args = data.get("args", {})
                            if str(args.get("network_id")) == str(subgraph_id):
                                visualization_generated = True
                                print(f"   Visualization Generated for Network ID {subgraph_id} (Standalone)")
                            else:
                                print(f"   Visualization Generated but network_id={args.get('network_id')} (Expected {subgraph_id})")
                            
                    if "nodes" in data:
                        nodes = data["nodes"]
                        print(f"   Render Update: {len(nodes)} nodes")
                        
                    if "role" in data and data["role"] == "model":
                        print(f"   Assistant: {data['content']}")
                        print("   Assistant response received. Stopping.")
                        break
                        
                except json.JSONDecodeError:
                    pass

    if visualization_generated:
        print("SUCCESS: Subgraph visualization generated.")
        return True
    else:
        print("FAILED: Visualization not generated.")
        return False

if __name__ == "__main__":
    if verify_subgraph_visualization():
        print("\nVerification SUCCESS")
        sys.exit(0)
    else:
        print("\nVerification FAILED")
        sys.exit(1)
