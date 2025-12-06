import requests
import json
import time
import sys
import threading

BASE_URL = "http://localhost:8000"
USERNAME = "testuser"
PASSWORD = "testpassword"

def verify_sse_broadcast(chat_id):
    # 1. Login
    print("Logging in...")
    response = requests.post(f"{BASE_URL}/auth/token", data={"username": USERNAME, "password": PASSWORD})
    if response.status_code != 200:
        print("Login failed, trying to register...")
        requests.post(f"{BASE_URL}/auth/register", json={"username": USERNAME, "password": PASSWORD})
        response = requests.post(f"{BASE_URL}/auth/token", data={"username": USERNAME, "password": PASSWORD})
    
    if response.status_code != 200:
        print(f"Authentication failed: {response.text}")
        return

    token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("Authenticated.")

    # Create a chat first
    print("Creating chat...")
    create_response = requests.post(
        f"{BASE_URL}/chat",
        headers=headers,
        json={"name": "Test Chat for SSE"}
    )
    if create_response.status_code != 200:
        print(f"Failed to create chat: {create_response.text}")
        return
    
    chat_id = create_response.json()["id"]
    print(f"Created chat {chat_id}")

    results = {"client1": [], "client2": []}
    
    def listen_sse(client_name):
        print(f"Starting SSE listener: {client_name}...")
        try:
            with requests.get(f"{BASE_URL}/chat/{chat_id}/stream", headers=headers, stream=True) as r:
                for line in r.iter_lines():
                    if line:
                        decoded_line = line.decode('utf-8')
                        if decoded_line.startswith("event:"):
                            event_type = decoded_line.split(":", 1)[1].strip()
                            print(f"[{client_name}] Event: {event_type}")
                            results[client_name].append(event_type)
        except Exception as e:
            print(f"[{client_name}] Error: {e}")

    # Start two clients
    t1 = threading.Thread(target=listen_sse, args=("client1",))
    t2 = threading.Thread(target=listen_sse, args=("client2",))
    t1.daemon = True
    t2.daemon = True
    t1.start()
    t2.start()

    time.sleep(2) # Wait for connections

    # 3. Trigger Visualization Update
    print(f"Sending message to chat {chat_id}...")
    msg_response = requests.post(
        f"{BASE_URL}/chat/{chat_id}/process",
        headers=headers,
        json={"message": {"content": "Hello World"}}
    )
    print(f"Message sent: {msg_response.status_code}")

    # 4. Wait for processing
    time.sleep(15)
    
    print("\n--- Results ---")
    print(f"Client 1 events: {results['client1']}")
    print(f"Client 2 events: {results['client2']}")
    
    if len(results['client1']) > 0 and len(results['client2']) > 0:
        print("SUCCESS: Both clients received events.")
    else:
        print("FAILURE: Some clients missed events (likely stolen by the other).")

if __name__ == "__main__":
    verify_sse_broadcast(None)
