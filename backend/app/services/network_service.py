import httpx
import os
from dotenv import load_dotenv
from app.core.logging import get_logger

logger = get_logger(__name__)

load_dotenv()

NETWORKX_API_URL = os.getenv("NETWORKX_API_URL", "http://localhost:8001")

async def initialize_network(network_id: int, graphml_data: str):
    logger.info(f"Initializing network {network_id} via NetworkXAPI")
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{NETWORKX_API_URL}/tools/initialize_network",
            json={"network_id": network_id, "graphml_data": graphml_data}
        )
        response.raise_for_status()
        return response.json()

async def list_node_attributes(network_id: int):
    logger.info(f"Listing node attributes for network {network_id}")
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{NETWORKX_API_URL}/tools/list_node_attributes",
            params={"network_id": network_id}
        )
        response.raise_for_status()
        return response.json()

async def list_edge_attributes(network_id: int):
    logger.info(f"Listing edge attributes for network {network_id}")
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{NETWORKX_API_URL}/tools/list_edge_attributes",
            params={"network_id": network_id}
        )
        response.raise_for_status()
        return response.json()

async def calculate_centrality(network_id: int, centrality_type: str):
    logger.info(f"Calculating {centrality_type} centrality for network {network_id}")
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{NETWORKX_API_URL}/tools/calculate_centrality",
            json={"network_id": network_id, "centrality_type": centrality_type}
        )
        response.raise_for_status()
        return response.json()

async def calculate_layout(network_id: int, layout_name: str):
    logger.info(f"Calculating {layout_name} layout for network {network_id}")
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{NETWORKX_API_URL}/tools/calculate_layout",
            json={"network_id": network_id, "layout_name": layout_name}
        )
        response.raise_for_status()
        return response.json()

async def generate_visualization(network_id: int, params: dict):
    logger.info(f"Generating visualization for network {network_id} with params: {params}")
    async with httpx.AsyncClient() as client:
        # params should include layout_name, node_size_config, etc.
        payload = {"network_id": network_id, **params}
        response = await client.post(
            f"{NETWORKX_API_URL}/tools/generate_visualization",
            json=payload
        )
        response.raise_for_status()
        return response.json()

async def export_network(network_id: int) -> str:
    """Export network as GraphML from NetworkXAPI"""
    logger.info(f"Exporting network {network_id}")
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{NETWORKX_API_URL}/tools/export_network",
            params={"network_id": network_id}
        )
        response.raise_for_status()
        return response.text
