import requests
import json
import sys
import os
import time

BASE_URL = "http://localhost:8000"
USERNAME = "verify_lcc_user"
PASSWORD = "password123"

def verify_lcc_visualization():
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
    resp = session.post(f"{BASE_URL}/chat", json={"name": "LCC Vis Chat"})
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
    time.sleep(3) 
            
    # 5. Send Message
    prompt = "最大連結成分だけのネットワークを作成しそれに着目してください。"
    print(f"5. Sending Message: '{prompt}'...")
    
    payload = {
        "message": {
            "role": "user", 
            "content": prompt
        }
    }
    resp = session.post(f"{BASE_URL}/chat/{chat_id}/process", json=payload)
    if resp.status_code not in [200, 202]:
        print(f"Failed to send message: {resp.status_code} - {resp.text}")
        return False
        
    print("6. Listening for events...")
    resp = session.get(f"{BASE_URL}/chat/{chat_id}/stream", stream=True)
    
    lcc_created = False
    visualization_generated = False
    subgraph_id = None
    vis_network_id = None
    
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
                print(f"DEBUG: {data_str}")
                try:
                    data = json.loads(data_str)
                    
                    if "tool" in data:
                        tool_name = data["tool"]
                        status = data.get("status")
                        result = data.get("result")
                        args = data.get("args", {})
                        
                        if tool_name == "create_largest_component_subgraph" and status == "completed":
                            lcc_created = True
                            if result and isinstance(result, dict) and "subgraph_id" in result:
                                subgraph_id = result["subgraph_id"]
                                print(f"   LCC Subgraph Created: ID={subgraph_id}")
                                
                        if tool_name == "generate_visualization" and status == "started":
                            vis_network_id = args.get("network_id")
                            focus_network_id = args.get("focus_network_id")
                            print(f"   Visualization Started: network_id={vis_network_id}, focus_network_id={focus_network_id}")
                            visualization_generated = True

                    if "role" in data and data["role"] == "model":
                        print(f"   Assistant: {data['content']}")
                        print("   Assistant response received. Stopping.")
                        break
                        
                except json.JSONDecodeError:
                    pass
    
    if lcc_created and visualization_generated:
        if str(vis_network_id) == str(subgraph_id):
            print("SUCCESS: Visualized LCC as standalone network.")
            return True
        else:
            print(f"FAILED: Visualized network_id={vis_network_id}, expected subgraph_id={subgraph_id}. (Likely Focus+Context)")
            return False
    else:
        print("FAILED: Tools not called correctly.")
        return False

if __name__ == "__main__":
    if verify_lcc_visualization():
        print("\nVerification SUCCESS")
        sys.exit(0)
    else:
        print("\nVerification FAILED")
        sys.exit(1)
