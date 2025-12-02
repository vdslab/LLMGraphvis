import requests
import json
import time
import sys

BASE_URL = "http://localhost:8000/api/v1"
USERNAME = "testuser"
PASSWORD = "testpassword"

def verify_api(chat_id):
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

    # 2. Send message to color nodes
    print(f"Sending message to chat {chat_id}...")
    msg_response = requests.post(
        f"{BASE_URL}/chat/{chat_id}/process",
        headers=headers,
        json={"message": {"content": "Color the nodes by degree centrality with red color for top 5 nodes."}}
    )
    print(f"Message sent: {msg_response.status_code}")

    # 3. Wait for processing
    print("Waiting 10 seconds for processing...")
    time.sleep(10)

    # 4. Get Chat details
    print(f"Fetching chat {chat_id} details...")
    chat_response = requests.get(f"{BASE_URL}/chat/{chat_id}", headers=headers)
    if chat_response.status_code != 200:
        print(f"Failed to get chat: {chat_response.text}")
        return

    chat_data = chat_response.json()
    network = chat_data.get("network")
    
    if not network:
        print("No network data found in response.")
        return

    nodes = network.get("nodes", [])
    if not nodes:
        print("No nodes found in network data.")
        return

    print(f"Found {len(nodes)} nodes.")
    
    # Check colors
    red_nodes = [n for n in nodes if n.get("color") == "red" or n.get("color") == "#FF0000"]
    print(f"Found {len(red_nodes)} red nodes.")
    
    if len(red_nodes) > 0:
        print("SUCCESS: Visualization state (colors) seems to be saved and returned.")
    else:
        print("FAILURE: No red nodes found. Visualization state might not be saved or applied.")
        # Print sample node colors
        sample_colors = [n.get("color") for n in nodes[:5]]
        print(f"Sample node colors: {sample_colors}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        chat_id = int(sys.argv[1])
    else:
        chat_id = 4
    verify_api(chat_id)
