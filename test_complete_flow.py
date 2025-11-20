#!/usr/bin/env python3
"""
Test script to verify the complete flow:
1. Login/Register
2. Create a chat
3. Upload GraphML
4. Send chat message to visualize with degree centrality
"""

import requests
import time
import json

BASE_URL = "http://localhost:8000/api"

def test_complete_flow():
    print("=" * 60)
    print("Testing Complete Flow: Login → Upload → Chat → Visualization")
    print("=" * 60)
    
    # Step 1: Register/Login
    print("\n1. Registering/Logging in...")
    username = f"testuser_{int(time.time())}"
    password = "testpass123"
    
    try:
        response = requests.post(
            f"{BASE_URL}/auth/register",
            json={"username": username, "password": password}
        )
        if response.status_code == 201:
            print(f"✓ Registered new user: {username}")
        else:
            print(f"✗ Registration failed: {response.status_code}")
            print(response.text)
            return
    except Exception as e:
        print(f"✗ Error during registration: {e}")
        return
    
    token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # Step 2: Create a chat
    print("\n2. Creating a new chat...")
    try:
        response = requests.post(
            f"{BASE_URL}/chat",
            json={"name": "Test Network Chat"},
            headers=headers
        )
        if response.status_code == 200:
            chat_data = response.json()
            chat_id = chat_data["id"]
            network_id = chat_data["network_id"]
            print(f"✓ Created chat with ID: {chat_id}, Network ID: {network_id}")
        else:
            print(f"✗ Chat creation failed: {response.status_code}")
            print(response.text)
            return
    except Exception as e:
        print(f"✗ Error creating chat: {e}")
        return
    
    # Step 3: Upload GraphML
    print("\n3. Uploading GraphML file...")
    graphml_path = "sample_data/karate_club.graphml"
    
    try:
        with open(graphml_path, 'rb') as f:
            files = {'file': ('karate_club.graphml', f, 'application/xml')}
            response = requests.post(
                f"{BASE_URL}/chat/{chat_id}/upload",
                files=files,
                headers=headers
            )
        
        if response.status_code == 202:
            print(f"✓ Upload accepted (202). Waiting for processing...")
            # Wait a bit for background processing
            time.sleep(3)
            print("✓ Upload should be processed by now")
        else:
            print(f"✗ Upload failed: {response.status_code}")
            print(response.text)
            return
    except Exception as e:
        print(f"✗ Error uploading file: {e}")
        return
    
    # Step 4: Send chat message
    print("\n4. Sending chat message: '友達が多い人を大きく表示して'")
    try:
        response = requests.post(
            f"{BASE_URL}/chat/{chat_id}/process",
            json={"message": {"content": "友達が多い人を大きく表示して"}},
            headers=headers
        )
        
        if response.status_code == 202:
            print(f"✓ Message accepted (202). Processing in background...")
            print("  Note: Check SSE stream at GET /chat/{chat_id}/stream for real-time updates")
        else:
            print(f"✗ Message processing failed: {response.status_code}")
            print(response.text)
            return
    except Exception as e:
        print(f"✗ Error sending message: {e}")
        return
    
    # Step 5: Get messages to verify
    print("\n5. Retrieving chat messages...")
    time.sleep(5)  # Wait for LLM processing
    
    try:
        response = requests.get(
            f"{BASE_URL}/chat/{chat_id}/messages",
            headers=headers
        )
        
        if response.status_code == 200:
            messages = response.json()
            print(f"✓ Retrieved {len(messages)} messages:")
            for msg in messages:
                role = msg['role']
                content = msg['content'][:100] + "..." if len(msg['content']) > 100 else msg['content']
                print(f"  [{role}]: {content}")
        else:
            print(f"✗ Failed to retrieve messages: {response.status_code}")
            print(response.text)
    except Exception as e:
        print(f"✗ Error retrieving messages: {e}")
    
    print("\n" + "=" * 60)
    print("Test Complete!")
    print("=" * 60)
    print(f"\nChat ID: {chat_id}")
    print(f"Access the chat at: http://localhost:5173/chat/{chat_id}")
    print(f"SSE Stream: {BASE_URL}/chat/{chat_id}/stream")

if __name__ == "__main__":
    test_complete_flow()