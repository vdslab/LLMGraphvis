import requests
import json
import sys
import os
import time

BASE_URL = "http://localhost:8000"
USERNAME = "verify_upload_user"
PASSWORD = "password123"

def verify_upload_flow():
    session = requests.Session()
    
    # 1. Register/Login
    print("1. Authenticating...")
    resp = session.post(f"{BASE_URL}/auth/register", json={"username": USERNAME, "password": PASSWORD})
    if resp.status_code not in [200, 409]:
        print(f"Failed to register: {resp.text}")
        return False
        
    resp = session.post(f"{BASE_URL}/auth/token", data={"username": USERNAME, "password": PASSWORD})
    if resp.status_code != 200:
        print(f"Failed to login: {resp.text}")
        return False
        
    # 2. Create Chat
    print("2. Creating Chat...")
    resp = session.post(f"{BASE_URL}/chat", json={"name": "Upload Verification Chat"})
    if resp.status_code != 200:
        print(f"Failed to create chat: {resp.text}")
        return False
    chat_id = resp.json()["id"]
    print(f"   Chat ID: {chat_id}")
    
    # 3. Upload Graph
    print("3. Uploading Graph...")
    if not os.path.exists("sample_data/karate_club.graphml"):
        print("   Error: sample_data/karate_club.graphml not found")
        return False
        
    with open("sample_data/karate_club.graphml", "rb") as f:
        files = {"file": ("karate_club.graphml", f, "application/xml")}
        resp = session.post(f"{BASE_URL}/chat/{chat_id}/upload", files=files)
        if resp.status_code not in [200, 202]:
            print(f"Failed to upload graph: {resp.status_code} - {resp.text}")
            return False
    
    print("   Upload accepted. Listening for SSE events to confirm processing...")
    
    # 4. Listen to SSE
    resp = session.get(f"{BASE_URL}/chat/{chat_id}/stream", stream=True)
    
    start_time = time.time()
    for line in resp.iter_lines():
        if time.time() - start_time > 10:
            print("   Timeout waiting for render_update")
            return False
            
        if line:
            decoded_line = line.decode('utf-8')
            if decoded_line.startswith("event: render_update"):
                print("   Success: Received render_update event")
                return True
            if decoded_line.startswith("event: error"):
                print(f"   Error event received: {decoded_line}")
                return False
                
    return False

if __name__ == "__main__":
    if verify_upload_flow():
        print("\nUpload Verification SUCCESS")
        sys.exit(0)
    else:
        print("\nUpload Verification FAILED")
        sys.exit(1)
