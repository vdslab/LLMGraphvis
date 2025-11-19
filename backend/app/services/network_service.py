import httpx
import os
from dotenv import load_dotenv

load_dotenv()

NETWORKX_API_URL = os.getenv("NETWORKX_API_URL", "http://localhost:8001")

async def initialize_network(network_id: int, graphml_data: str):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{NETWORKX_API_URL}/tools/initialize_network",
            json={"network_id": network_id, "graphml_data": graphml_data}
        )
        response.raise_for_status()
        return response.json()

async def list_attributes(network_id: int):
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{NETWORKX_API_URL}/tools/list_attributes",
            params={"network_id": network_id}
        )
        response.raise_for_status()
        return response.json()

async def calculate_centrality(network_id: int, centrality_type: str):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{NETWORKX_API_URL}/tools/calculate_centrality",
            json={"network_id": network_id, "centrality_type": centrality_type}
        )
        response.raise_for_status()
        return response.json()

async def generate_visualization(network_id: int, params: dict):
    async with httpx.AsyncClient() as client:
        # params should include layout_name, node_size_config, etc.
        payload = {"network_id": network_id, **params}
        response = await client.post(
            f"{NETWORKX_API_URL}/tools/generate_visualization",
            json=payload
        )
        response.raise_for_status()
        return response.json()
