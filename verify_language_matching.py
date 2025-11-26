import requests
import json
import sys
import os
import time
import re

BASE_URL = "http://localhost:8000"
USERNAME = "verify_lang_user"
PASSWORD = "password123"

def verify_language_matching():
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
    resp = session.post(f"{BASE_URL}/chat", json={"name": "Language Test Chat"})
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
            
    # 5. Send Message in Japanese
    print("5. Sending Message: '次数中心性を計算して' (Calculate degree centrality)...")
    
    payload = {
        "message": {
            "role": "user", 
            "content": "次数中心性を計算して"
        }
    }
    resp = session.post(f"{BASE_URL}/chat/{chat_id}/process", json=payload)
    if resp.status_code not in [200, 202]:
        print(f"Failed to send message: {resp.status_code} - {resp.text}")
        return False
        
    print("6. Listening for events...")
    resp = session.get(f"{BASE_URL}/chat/{chat_id}/stream", stream=True)
    
    assistant_response = ""
    
    start_time = time.time()
    timeout = 120
    
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
                    
                    if "role" in data and (data["role"] == "model" or data["role"] == "assistant"):
                        assistant_response = data["content"]
                        print(f"   Assistant: {assistant_response}")
                        break
                        
                except json.JSONDecodeError:
                    pass
    
    if not assistant_response:
        print("FAILED: No response from assistant.")
        return False

    # Check if response contains Japanese characters
    # Hiragana: \u3040-\u309F
    # Katakana: \u30A0-\u30FF
    # Kanji: \u4E00-\u9FAF
    japanese_pattern = re.compile(r'[\u3040-\u309F\u30A0-\u30FF\u4E00-\u9FAF]')
    
    if japanese_pattern.search(assistant_response):
        print("SUCCESS: Response contains Japanese characters.")
        return True
    else:
        print("FAILED: Response does not contain Japanese characters.")
        return False

if __name__ == "__main__":
    if verify_language_matching():
        print("\nVerification SUCCESS")
        sys.exit(0)
    else:
        print("\nVerification FAILED")
        sys.exit(1)
