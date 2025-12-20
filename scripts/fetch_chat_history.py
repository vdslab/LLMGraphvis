import asyncio
import httpx
import os
import json
from dotenv import load_dotenv

load_dotenv()

API_URL = os.getenv("VITE_API_URL", "http://localhost:8000")
USERNAME = os.getenv("AUTH_USERNAME", "admin")
PASSWORD = os.getenv("AUTH_PASSWORD", "admin")

async def fetch_history():
    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. Login
        print("1. Logging in...")
        auth_res = await client.post(f"{API_URL}/api/v1/auth/token", data={"username": USERNAME, "password": PASSWORD})
        if auth_res.status_code != 200:
            print(f"Login failed: {auth_res.text}")
            return
        token = auth_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 2. Get Messages for Chat 4
        print("2. Fetching messages for Chat 4...")
        res = await client.get(f"{API_URL}/api/v1/chat/4/messages", headers=headers)
        if res.status_code != 200:
            print(f"Fetch failed: {res.text}")
            return
        
        messages = res.json()
        print(f"Found {len(messages)} messages.")
        
        for msg in messages:
            print(f"--- Role: {msg['role']} ---")
            # The content might be JSON string if it's a tool call log, or just text.
            # But in this system, tool calls are not stored in ChatMessage content usually?
            # Wait, llm_service stores tool calls in history but maybe not in ChatMessage table?
            # Let's see what's in 'content'.
            print(msg['content'])

if __name__ == "__main__":
    asyncio.run(fetch_history())
