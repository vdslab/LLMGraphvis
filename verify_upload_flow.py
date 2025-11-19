import requests
import sys

BASE_URL = "http://localhost:8000"
USERNAME = "verify_user_01"
PASSWORD = "password123"
FILE_PATH = "/Users/takuma/develop/vdslab/master/GraphVisAgent/sample_data/karate_club.graphml"

def run_verification():
    # 1. Register
    print(f"Registering user {USERNAME}...")
    resp = requests.post(f"{BASE_URL}/auth/register", json={"username": USERNAME, "password": PASSWORD})
    if resp.status_code == 400 and "already registered" in resp.text:
        print("User already exists, proceeding to login.")
    elif resp.status_code not in [200, 201]:
        print(f"Registration failed: {resp.text}")
        # Try to login anyway, maybe it failed for another reason but user exists

    
    # 2. Login
    print("Logging in...")
    resp = requests.post(f"{BASE_URL}/auth/token", data={"username": USERNAME, "password": PASSWORD})
    if resp.status_code != 200:
        print(f"Login failed: {resp.text}")
        sys.exit(1)
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 3. Create Chat
    print("Creating chat...")
    resp = requests.post(f"{BASE_URL}/chat", headers=headers, json={"name": "Verification Chat"})
    if resp.status_code not in [200, 201]:
        print(f"Create chat failed (Status {resp.status_code}): {resp.text}")
        sys.exit(1)
    chat_data = resp.json()
    chat_id = chat_data["id"]
    print(f"Chat created with ID: {chat_id}")

    # 4. Upload File
    print(f"Uploading file to chat {chat_id}...")
    with open(FILE_PATH, "rb") as f:
        files = {"file": ("karate_club.graphml", f, "application/xml")}
        resp = requests.post(f"{BASE_URL}/chat/{chat_id}/upload", headers=headers, files=files)
    
    if resp.status_code != 202:
        print(f"Upload failed: {resp.text}")
        sys.exit(1)
    
    print("Upload successful (202 Accepted).")
    print(f"CHAT_ID={chat_id}")
    print(f"USERNAME={USERNAME}")
    print(f"PASSWORD={PASSWORD}")

if __name__ == "__main__":
    run_verification()
