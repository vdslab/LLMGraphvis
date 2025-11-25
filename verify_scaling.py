import requests
import json
import sys
import os
import time

BASE_URL = "http://localhost:8000"
USERNAME = "verify_scaling_user"
PASSWORD = "password123"

def verify_scaling():
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
    resp = session.post(f"{BASE_URL}/chat", json={"name": "Scaling Test Chat"})
    if resp.status_code != 200:
        print(f"Failed to create chat: {resp.text}")
        return False
    chat_id = resp.json()["id"]
    print(f"   Chat ID: {chat_id}")
    
    # 4. Upload Graph
    print("4. Uploading Graph...")
    if not os.path.exists("sample_data/scaling_test.graphml"):
        print("Error: sample_data/scaling_test.graphml not found")
        return False
        
    with open("sample_data/scaling_test.graphml", "rb") as f:
        files = {"file": ("scaling_test.graphml", f, "application/xml")}
        resp = session.post(f"{BASE_URL}/chat/{chat_id}/upload", files=files)
        if resp.status_code not in [200, 202]:
            print(f"Failed to upload graph: {resp.status_code} - {resp.text}")
            return False
    
    print("   Upload accepted. Waiting for processing...")
    time.sleep(3) # Wait for background task
            
    # 5. Send Message to trigger visualization
    print("5. Sending Message: 'Visualize by score'...")
    
    # We can directly call the tool via the LLM flow, or we can simulate the tool call if we could.
    # But sticking to the LLM flow is more integration-test like.
    # However, to be precise, we want to force the tool call parameters.
    # The LLM might not pick "score" automatically if it doesn't know it exists.
    # We should first list attributes.
    
    payload = {
        "message": {
            "role": "user", 
            "content": "List node attributes and then visualize with node size based on 'score' attribute."
        }
    }
    resp = session.post(f"{BASE_URL}/chat/{chat_id}/process", json=payload)
    if resp.status_code not in [200, 202]:
        print(f"Failed to send message: {resp.status_code} - {resp.text}")
        return False
        
    print("6. Listening for events...")
    resp = session.get(f"{BASE_URL}/chat/{chat_id}/stream", stream=True)
    
    start_time = time.time()
    timeout = 30
    
    verified = False
    
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
                    
                    if "nodes" in data:
                        nodes = data["nodes"]
                        print(f"   Render Update: {len(nodes)} nodes")
                        if nodes:
                            sizes = [n.get('size', 0) for n in nodes]
                            min_size = min(sizes)
                            max_size = max(sizes)
                            print(f"   Node Sizes: min={min_size}, max={max_size}")
                            
                            # The LLM likely used min=5, max=50 from few-shot examples.
                            # Data is 100 and 200.
                            # If normalization works: 100 -> min (5), 200 -> max (50).
                            # If normalization FAILED (old logic): 100 -> huge number.
                            
                            if abs(min_size - 5) < 1 and abs(max_size - 50) < 1:
                                print("   SUCCESS: Node sizes match expected scaling (5-50) for inputs (100-200).")
                                print("   This proves Dynamic Min-Max Normalization is working!")
                                verified = True
                                break
                            elif abs(min_size - 20) < 1 and abs(max_size - 60) < 1:
                                print("   SUCCESS: Node sizes match default scaling (20-60).")
                                verified = True
                                break
                            else:
                                print(f"   WARNING: Sizes {min_size}-{max_size} do not match expected ranges.")
                                
                    if "role" in data and data["role"] == "model":
                        print(f"   Assistant: {data['content']}")
                        if not verified:
                            break
                        
                except json.JSONDecodeError:
                    pass
    
    return verified

if __name__ == "__main__":
    if verify_scaling():
        print("\nVerification SUCCESS")
        sys.exit(0)
    else:
        print("\nVerification FAILED")
        sys.exit(1)
