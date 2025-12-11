import requests
import json
import sys
import os
import time

BASE_URL = "http://localhost:8000"
import random
USERNAME = f"verify_llm_vis_{random.randint(1000, 9999)}"
PASSWORD = "password123"

def verify_llm_visualization():
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
    resp = session.post(f"{BASE_URL}/chat", json={"name": "LLM Vis Chat"})
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
            
    # 5. Send Message & Listen to SSE
    print("5. Sending Message: '友達が多い人を大きく表示して'...")
    
    payload = {
        "message": {
            "role": "user", 
            "content": "友達が多い人を大きく表示して"
        }
    }
    resp = session.post(f"{BASE_URL}/chat/{chat_id}/process", json=payload)
    if resp.status_code not in [200, 202]:
        print(f"Failed to send message: {resp.status_code} - {resp.text}")
        return False
        
    print("6. Listening for events...")
    # Manual SSE parsing
    resp = session.get(f"{BASE_URL}/chat/{chat_id}/stream", stream=True)
    
    tool_called = False
    render_updated = False
    centrality_calculated = False
    messages = []
    
    start_time = time.time()
    timeout = 120 # 120 seconds timeout
    
    for line in resp.iter_lines():
        if time.time() - start_time > timeout:
            print("   Timeout waiting for response.")
            break
            
        if line:
            decoded_line = line.decode('utf-8')
            if decoded_line.startswith("event:"):
                current_event = decoded_line[6:].strip()
            elif decoded_line.startswith("data:"):
                data_str = decoded_line[5:].strip()
                try:
                    data = json.loads(data_str)
                    # print(f"   Event: {data}")
                    
                    if "nodes" in data:
                        nodes = data["nodes"]
                        print(f"   Render Update: {len(nodes)} nodes")
                        if nodes:
                            sizes = [n.get('size', 0) for n in nodes]
                            min_size = min(sizes)
                            max_size = max(sizes)
                            print(f"   Node Sizes: min={min_size}, max={max_size}")
                            
                            if max_size > min_size:
                                print("   Verified: Node sizes vary (Centrality applied)")
                                render_updated = True
                            else:
                                print("   Warning: Node sizes are uniform.")

                    if "tool" in data:
                        tool_name = data["tool"]
                        status = data.get("status")
                        print(f"   Tool: {tool_name} ({status})")
                        if tool_name == "calculate_centrality" and status == "completed":
                            centrality_calculated = True
                        if tool_name == "generate_visualization" and status == "completed":
                            tool_called = True
                            
                    if "role" in data and data["role"] == "model":
                        # Gemini 2.0/2.5 often returns 'model' role
                        content = data.get('content', '')
                        print(f"   Assistant: {content}")
                        messages.append(content)
                        print("   Assistant response received. Stopping.")
                        break
                        
                except json.JSONDecodeError:
                    pass
    
    if centrality_calculated:
        print("SUCCESS: calculate_centrality tool was called.")
    else:
        print("FAILED: calculate_centrality tool was not called.")

    if tool_called:
        print("SUCCESS: generate_visualization tool was called.")
    else:
        print("FAILED: generate_visualization tool was not called.")
        
    if render_updated:
        print("SUCCESS: render_update showed varying node sizes.")
    else:
        print("FAILED: render_update did not show varying node sizes.")

    if centrality_calculated and tool_called and render_updated:
        return True
    else:
        return False

if __name__ == "__main__":
    if verify_llm_visualization():
        print("\nVerification SUCCESS")
        sys.exit(0)
    else:
        print("\nVerification FAILED")
        sys.exit(1)
