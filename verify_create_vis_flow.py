import requests
import json
import sseclient
import time
import sys

BASE_URL = "http://localhost:8000"
API_V1_STR = ""

def verify_create_vis_flow():
    print("1. Registering...")
    email = f"test_create_vis_{int(time.time())}@example.com"
    password = "password123"
    try:
        reg_res = requests.post(f"{BASE_URL}/auth/register", json={"email": email, "username": email, "password": password})
        print(f"   Register Status: {reg_res.status_code}")
        print(f"   Register Response: {reg_res.text}")
    except Exception as e:
        print(f"   Register Failed: {e}")

    print("2. Logging in...")
    login_res = requests.post(f"{BASE_URL}/auth/token", data={"username": email, "password": password})
    print(f"   Login Status: {login_res.status_code}")
    if login_res.status_code != 200:
        print(f"   Login Response: {login_res.text}")
        sys.exit(1)
        
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    print("3. Creating Chat...")
    chat_res = requests.post(f"{BASE_URL}{API_V1_STR}/chat", headers=headers, json={"name": "Create Vis Chat"})
    print(f"   Chat Creation Status: {chat_res.status_code}")
    if chat_res.status_code != 200:
        print(f"   Chat Creation Response: {chat_res.text}")
        sys.exit(1)
    
    chat_data = chat_res.json()
    print(f"   Chat Data: {chat_data}")
    chat_id = chat_data["id"]
    print(f"   Chat ID: {chat_id}")

    print("4. Uploading Graph...")
    with open("sample_data/karate_club.graphml", "rb") as f:
        files = {"file": ("karate_club.graphml", f, "application/xml")}
        requests.post(f"{BASE_URL}{API_V1_STR}/chat/{chat_id}/upload", headers=headers, files=files)
    
    # Wait for upload processing
    time.sleep(2)

    print("5. Sending Message: 'Apply circular layout and show popular nodes'...")
    # This prompt requires:
    # 1. list_attributes
    # 2. calculate_centrality (degree)
    # 3. calculate_layout (circular)
    # 4. list_attributes (check both)
    # 5. generate_visualization (layout='circular', size='degree_centrality')
    
    msg_res = requests.post(
        f"{BASE_URL}{API_V1_STR}/chat/{chat_id}/process",
        headers=headers,
        json={"message": {"content": "Apply circular layout and show popular nodes"}}
    )
    
    print("6. Listening for events...")
    messages_url = f"{BASE_URL}{API_V1_STR}/chat/{chat_id}/stream"
    response = requests.get(messages_url, headers=headers, stream=True)
    client = sseclient.SSEClient(response)

    tools_called = set()
    
    for event in client.events():
        if event.event == "tool_execution":
            data = json.loads(event.data)
            tool_name = data["tool"]
            status = data["status"]
            print(f"   Tool: {tool_name} ({status})")
            if status == "completed":
                tools_called.add(tool_name)
                
        elif event.event == "render_update":
            data = json.loads(event.data)
            nodes = data.get("nodes", [])
            print(f"   Render Update: {len(nodes)} nodes")
            if nodes and "x" in nodes[0] and "y" in nodes[0]:
                print("   Verified: Nodes have coordinates.")
            
        elif event.event == "message":
            print("   Message received. Verification Complete.")
            break
            
    # Verification Checks
    success = True
    
    if "calculate_centrality" not in tools_called:
        print("FAILURE: calculate_centrality was NOT called.")
        success = False
    else:
        print("SUCCESS: calculate_centrality was called.")

    if "calculate_layout" not in tools_called:
        print("FAILURE: calculate_layout was NOT called.")
        success = False
    else:
        print("SUCCESS: calculate_layout was called.")
        
    if "generate_visualization" not in tools_called:
        print("FAILURE: generate_visualization was NOT called.")
        success = False
    else:
        print("SUCCESS: generate_visualization was called.")

    if success:
        print("\nVerification SUCCESS")
        sys.exit(0)
    else:
        print("\nVerification FAILED")
        sys.exit(1)

if __name__ == "__main__":
    verify_create_vis_flow()
