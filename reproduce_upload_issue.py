import requests
import json
import sys
import os
import time

BASE_URL = "http://localhost:8000"
USERNAME = "reproduce_user"
PASSWORD = "password123"
FILE_PATH = "sample_data/concert_networks/concert_network.graphml"

def reproduce_issue():
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
    resp = session.post(f"{BASE_URL}/chat", json={"name": "Large Graph Upload Test"})
    if resp.status_code != 200:
        print(f"Failed to create chat: {resp.text}")
        return False
    chat_id = resp.json()["id"]
    print(f"   Chat ID: {chat_id}")
    
    # 4. Upload Graph
    print(f"4. Uploading Graph: {FILE_PATH}...")
    if not os.path.exists(FILE_PATH):
        print(f"Error: {FILE_PATH} not found")
        return False
        
    start_time = time.time()
    with open(FILE_PATH, "rb") as f:
        files = {"file": ("concert_network.graphml", f, "application/xml")}
        try:
            resp = session.post(f"{BASE_URL}/chat/{chat_id}/upload", files=files, timeout=60) # 60s timeout for request
            end_time = time.time()
            print(f"   Upload Request took {end_time - start_time:.2f} seconds")
            
            if resp.status_code not in [200, 202]:
                print(f"Failed to upload graph: {resp.status_code} - {resp.text}")
                return False
            else:
                print("   Upload accepted (202 Accepted).")
        except requests.exceptions.Timeout:
            print("   Upload Request Timed Out!")
            return False
        except Exception as e:
            print(f"   Upload Request Failed: {e}")
            return False
            
    # 5. Wait for Processing (Listen to SSE)
    print("5. Listening for processing completion...")
    resp = session.get(f"{BASE_URL}/chat/{chat_id}/stream", stream=True)
    
    wait_start = time.time()
    timeout = 120 # Wait up to 2 minutes for processing
    
    for line in resp.iter_lines():
        if time.time() - wait_start > timeout:
            print("   Timeout waiting for processing completion.")
            return False
            
        if line:
            decoded_line = line.decode('utf-8')
            if decoded_line.startswith("data:"):
                data_str = decoded_line[5:].strip()
                try:
                    data = json.loads(data_str)
                    if "nodes" in data:
                        nodes = data['nodes']
                        print(f"   Received Render Update: {len(nodes)} nodes")
                        if nodes:
                            print(f"   First Node Size: {nodes[0].get('size')}")
                        print("   SUCCESS: Graph processed and rendered.")
                        return True
                    if "error" in data:
                         print(f"   Received Error Event: {data['error']}")
                         return False
                except:
                    pass
    return False

if __name__ == "__main__":
    if reproduce_issue():
        print("\nReproduction Test PASSED (No issue found)")
        sys.exit(0)
    else:
        print("\nReproduction Test FAILED (Issue reproduced)")
        sys.exit(1)
