import asyncio
import httpx
import time

BACKEND_URL = "http://localhost:8000"
USERNAME = "testuser_subgraph_final"
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
        resp = await client.post(f"{BACKEND_URL}/chat", json={"name": "Subgraph Final Test"}, headers=headers)
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
        
        files = {"file": ("test.graphml", graphml.encode('utf-8'), "application/xml")}
        await client.post(f"{BACKEND_URL}/chat/{chat_id}/upload", files=files, headers=headers)
        await asyncio.sleep(2)

        # 4. Create Ego Network
        print("Creating ego network...")
        resp = await client.post(
            f"{BACKEND_URL}/networks/{network_id}/subgraphs/ego",
            json={"source_network_id": network_id, "center_node_id": "n0", "radius": 1},
            headers=headers
        )
        resp.raise_for_status()
        subgraph = resp.json()
        print(f"Created subgraph: {subgraph}")
        
        # 5. List Subgraphs
        print("Listing subgraphs...")
        resp = await client.get(f"{BACKEND_URL}/networks/{network_id}/subgraphs", headers=headers)
        resp.raise_for_status()
        subgraphs = resp.json()
        print(f"Subgraphs: {subgraphs}")
        
        assert len(subgraphs) > 0
        print("Verification Successful!")

if __name__ == "__main__":
    asyncio.run(main())
