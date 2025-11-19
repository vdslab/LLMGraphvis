import requests
import json
import sseclient
import sys
import os

BASE_URL = "http://localhost:8000"
USERNAME = "verify_user_centrality"
PASSWORD = "password123"

def verify_flow():
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
    resp = session.post(f"{BASE_URL}/chat", json={"name": "Verification Chat"})
    if resp.status_code != 200:
        print(f"Failed to create chat: {resp.text}")
        return False
    chat_id = resp.json()["id"]
    print(f"   Chat ID: {chat_id}")
    
    # 4. Upload Graph
    print("4. Uploading Graph...")
    with open("sample_data/karate_club.graphml", "rb") as f:
        files = {"file": ("karate_club.graphml", f, "application/xml")}
        resp = session.post(f"{BASE_URL}/chat/{chat_id}/upload", files=files)
        if resp.status_code not in [200, 202]:
            print(f"Failed to upload graph: {resp.status_code} - {resp.text}")
            return False
    
    print("   Upload accepted. Waiting for processing...")
    import time
    time.sleep(2) # Wait for background task
            
    # 5. Send Message & Listen to SSE
    print("5. Sending Message: 'Show people with many friends larger'...")
    
    payload = {
        "message": {
            "role": "user", 
            "content": "Show people with many friends larger"
        }
    }
    resp = session.post(f"{BASE_URL}/chat/{chat_id}/process", json=payload)
    if resp.status_code not in [200, 202]:
        print(f"Failed to send message: {resp.status_code} - {resp.text}")
        return False
        
    print("6. Listening for events...")
    # Manual SSE parsing
    resp = session.get(f"{BASE_URL}/chat/{chat_id}/stream", stream=True)
    
    tool_executed = False
    render_updated = False
    
    for line in resp.iter_lines():
        if line:
            decoded_line = line.decode('utf-8')
            if decoded_line.startswith("event:"):
                current_event = decoded_line[6:].strip()
            elif decoded_line.startswith("data:"):
                data_str = decoded_line[5:].strip()
                try:
                    data = json.loads(data_str)
                    print(f"   Event: {current_event}, Data: {data}")
                    
                    if current_event == "tool_execution":
                        if data.get("tool") == "calculate_centrality":
                            print("   Verified: calculate_centrality called")
                        if data.get("tool") == "generate_visualization":
                            print("   Verified: generate_visualization called")
                            tool_executed = True
                            
                    if current_event == "render_update":
                        print(f"   Render Data: {len(data['nodes'])} nodes")
                        sizes = [n['size'] for n in data['nodes']]
                        print(f"   Node Sizes: {sizes}")
                        if len(set(sizes)) > 1:
                            print("   Verified: Node sizes vary (Degree Centrality applied)")
                            render_updated = True
                        else:
                            print("   Warning: Node sizes are uniform.")
                            
                    if current_event == "message" and data.get("role") == "assistant":
                        print("   Assistant response received. Stopping.")
                        break
                except json.JSONDecodeError:
                    pass
            
    if render_updated:
        return True
    return False

if __name__ == "__main__":
    if verify_flow():
        print("\nVerification SUCCESS")
        sys.exit(0)
    else:
        print("\nVerification FAILED")
        sys.exit(1)
