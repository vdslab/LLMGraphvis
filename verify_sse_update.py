import requests
import json
import time
import sys
import threading
import sseclient

BASE_URL = "http://localhost:8000/api/v1"
USERNAME = "testuser"
PASSWORD = "testpassword"

def verify_sse(chat_id):
    # 1. Login
    print("Logging in...")
    response = requests.post(f"{BASE_URL}/auth/token", data={"username": USERNAME, "password": PASSWORD})
    if response.status_code != 200:
        # Try registering
        print("Login failed, trying to register...")
        requests.post(f"{BASE_URL}/auth/register", json={"username": USERNAME, "password": PASSWORD})
        response = requests.post(f"{BASE_URL}/auth/token", data={"username": USERNAME, "password": PASSWORD})
    
    if response.status_code != 200:
        print(f"Authentication failed: {response.text}")
        return

    token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("Authenticated.")

    # 2. Start SSE Listener in a thread
    def listen_sse():
        print("Starting SSE listener...")
        messages = sseclient.SSEClient(f"{BASE_URL}/chat/{chat_id}/events", headers=headers)
        for msg in messages:
            print(f"SSE Event: {msg.event}")
            if msg.event == "render_update":
                print("SUCCESS: Received render_update event!")
                print(f"Data length: {len(msg.data)}")
                return # Exit success
            if msg.event == "error":
                print(f"FAILURE: Received error event: {msg.data}")
                return

    t = threading.Thread(target=listen_sse)
    t.daemon = True
    t.start()

    # 3. Trigger Visualization Update
    time.sleep(2) # Wait for connection
    print(f"Sending message to chat {chat_id} to trigger visualization...")
    msg_response = requests.post(
        f"{BASE_URL}/chat/{chat_id}/process",
        headers=headers,
        json={"message": {"content": "Color the nodes by degree centrality."}}
    )
    print(f"Message sent: {msg_response.status_code}")

    # 4. Wait for result
    time.sleep(15)
    print("Finished waiting.")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        chat_id = int(sys.argv[1])
    else:
        chat_id = 4
    verify_sse(chat_id)
