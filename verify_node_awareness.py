import asyncio
import httpx

BACKEND_URL = "http://localhost:8000"
USERNAME = "testuser_nodes"
PASSWORD = "testpassword"

async def main():
    async with httpx.AsyncClient(timeout=60.0) as client:
        # 1. Register/Login
        try:
            await client.post(f"{BACKEND_URL}/auth/register", json={"username": USERNAME, "password": PASSWORD})
        except:
            pass
        
        resp = await client.post(f"{BACKEND_URL}/auth/token", data={"username": USERNAME, "password": PASSWORD})
        token = resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 2. Create Chat
        resp = await client.post(f"{BACKEND_URL}/chat", json={"name": "Node Awareness Test"}, headers=headers)
        chat = resp.json()
        chat_id = chat["id"]
        network_id = chat["network_id"]

        # 3. Upload GraphML
        graphml = """<?xml version="1.0" encoding="UTF-8"?>
<graphml xmlns="http://graphml.graphdrawing.org/xmlns"  
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xsi:schemaLocation="http://graphml.graphdrawing.org/xmlns
     http://graphml.graphdrawing.org/xmlns/1.0/graphml.xsd">
  <graph id="G" edgedefault="undirected">
    <node id="n0"/>
    <node id="n1"/>
    <node id="n2"/>
    <edge source="n0" target="n1"/>
    <edge source="n0" target="n2"/>
  </graph>
</graphml>"""
        
        files = {"file": ("nodes.graphml", graphml.encode('utf-8'), "application/xml")}
        await client.post(f"{BACKEND_URL}/chat/{chat_id}/upload", files=files, headers=headers)
        await asyncio.sleep(2)

        # 4. Get Top Nodes (Degree)
        print("Getting top nodes (degree)...")
        resp = await client.get(
            f"{BACKEND_URL}/networks/{network_id}/nodes/top",
            params={"metric": "degree", "k": 3},
            headers=headers
        )
        resp.raise_for_status()
        top_nodes = resp.json()
        print(f"Top Nodes: {top_nodes}")
        
        # Verify n0 is top (connected to n1 and n2)
        assert len(top_nodes) > 0
        assert top_nodes[0]["node_id"] == "n0"
        
        print("Verification Successful!")

if __name__ == "__main__":
    asyncio.run(main())
