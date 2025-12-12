import requests
import json
import sys
import os
import time

BASE_URL = "http://localhost:8000"
USERNAME = "verify_lcc_user_jp"
PASSWORD = "password123"

def verify_user_query_lcc():
    session = requests.Session()
    
    # 1. Register
    print("1. Registering...")
    resp = session.post(f"{BASE_URL}/auth/register", json={"username": USERNAME, "password": PASSWORD})
    # Ignore 409 (already exists)
        
    # 2. Login
    print("2. Logging in...")
    resp = session.post(f"{BASE_URL}/auth/token", data={"username": USERNAME, "password": PASSWORD})
    if resp.status_code != 200:
        print(f"Failed to login: {resp.text}")
        return False
        
    # 3. Create Chat
    print("3. Creating Chat...")
    resp = session.post(f"{BASE_URL}/chat", json={"name": "LCC Vis Chat JP"})
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
            
    # 5. Send Message (The specific user query)
    prompt = "最大連結成分で分析したい"
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
    
    lcc_tool_called = False
    
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
                        print(f"   Tool Execution: {tool_name} (Status: {data.get('status')})")
                        
                        if tool_name == "create_largest_component_subgraph":
                            lcc_tool_called = True
                            print("   SUCCESS: LLM called 'create_largest_component_subgraph'.")

                    if "role" in data and data["role"] == "model":
                        print(f"   Assistant: {data['content']}")
                        print("   Assistant response received. Stopping.")
                        break
                        
                except json.JSONDecodeError:
                    pass
    
    if lcc_tool_called:
        return True
    else:
        print("FAILED: LLM did NOT call 'create_largest_component_subgraph'.")
        return False

if __name__ == "__main__":
    if verify_user_query_lcc():
        print("\nVerification SUCCESS")
        sys.exit(0)
    else:
        print("\nVerification FAILED")
        sys.exit(1)
