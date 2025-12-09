
import asyncio
import httpx
import os

BACKEND_URL = "http://localhost:8000"
# Simple GraphML for testing
GRAPHML_DATA = """<?xml version="1.0" encoding="UTF-8"?>
<graphml xmlns="http://graphml.graphdrawing.org/xmlns">
    <key id="d0" for="node" attr.name="color" attr.type="string"/>
    <graph id="G" edgedefault="undirected">
        <node id="n0">
            <data key="d0">blue</data>
        </node>
        <node id="n1">
            <data key="d0">red</data>
        </node>
        <edge source="n0" target="n1"/>
    </graph>
</graphml>
"""

async def verify_upload():
    async with httpx.AsyncClient() as client:
        # 1. Login (if auth needed? Assumed disabled or specific user for dev)
        # Note: In this dev env, we might be able to bypass auth or create a user.
        # Let's try creating a user first or assume a default user.
        # However, looking at previous steps, auth endpoints exist.
        
        # Actually, let's just assume we can invoke the upload endpoint if we have a valid token.
        # Or better, let's look at how to get a token.
        # For simplicity, let's try to hit the endpoint. If 401, we need to sign up.
        
        # Register/Login
        email = "test@example.com"
        password = "password"
        try:
            await client.post(f"{BACKEND_URL}/auth/register", json={"username": email, "password": password, "full_name": "Test User"})
        except:
            pass # user might exist

        login_res = await client.post(f"{BACKEND_URL}/auth/token", data={"username": email, "password": password})
        if login_res.status_code != 200:
            print(f"Login failed: {login_res.text}")
            return
        
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        
        # 2. Create Chat
        chat_res = await client.post(f"{BACKEND_URL}/chat", json={"name": "Upload Test"}, headers=headers)
        if chat_res.status_code != 200:
            print(f"Create chat failed: {chat_res.text}")
            return
        
        chat_id = chat_res.json()["id"]
        network_id = chat_res.json()["network_id"] # Network is created with chat
        print(f"Created chat {chat_id} with network {network_id}")

        # 3. Upload File
        # Endpoint: POST /api/v1/chat/{chat_id}/upload_file
        files = {'file': ('test.graphml', GRAPHML_DATA, 'application/xml')}
        
        print("Uploading file...")
        upload_res = await client.post(f"{BACKEND_URL}/chat/{chat_id}/upload", files=files, headers=headers)
        
        if upload_res.status_code == 202:
            print("Upload request accepted (background task).")
        else:
            print(f"Upload failed immediately: {upload_res.status_code} {upload_res.text}")
            return # Don't proceed if upload upload failed
            
        # 4. Wait for background task
        print("Waiting for background processing...")
        await asyncio.sleep(5)
        
        # 5. Check Chat State (GET /chat/{id}) to confirm network data is present
        print(f"Checking chat state for {chat_id}...")
        chat_state_res = await client.get(f"{BACKEND_URL}/chat/{chat_id}", headers=headers)
        if chat_state_res.status_code == 200:
            print("Get chat succeeded.")
            data = chat_state_res.json()
            # print(data)
            if "network" in data and data["network"]:
                 print("Network data present in response.")
            else:
                 print("Network field missing or empty.")
        else:
            print(f"Get chat failed: {chat_state_res.status_code} {chat_state_res.text}")

if __name__ == "__main__":
    asyncio.run(verify_upload())
