import requests
import json
import time
import sys
import threading

BASE_URL = "http://localhost:8000"
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
        try:
            with requests.get(f"{BASE_URL}/chat/{chat_id}/stream", headers=headers, stream=True) as r:
                for line in r.iter_lines():
                    if line:
                        decoded_line = line.decode('utf-8')
                        if decoded_line.startswith("event:"):
                            event_type = decoded_line.split(":", 1)[1].strip()
                            print(f"SSE Event: {event_type}")
                            if event_type == "render_update":
                                print("SUCCESS: Received render_update event!")
                                return # Exit success
                            if event_type == "error":
                                print(f"FAILURE: Received error event")
                                return
        except Exception as e:
            print(f"Error in listener: {e}")

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
