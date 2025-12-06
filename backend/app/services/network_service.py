import httpx
import os
from dotenv import load_dotenv
from app.core.logging import get_logger
from typing import List, Dict, Any

logger = get_logger(__name__)

load_dotenv()

NETWORKX_API_URL = os.getenv("NETWORKX_API_URL", "http://localhost:8001")

async def initialize_network(network_id: int, graphml_data: str):
    logger.info(f"Initializing network {network_id} via NetworkXAPI")
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{NETWORKX_API_URL}/tools/initialize_network",
            json={"network_id": network_id, "graphml_data": graphml_data}
        )
        if response.is_error:
            logger.error(f"NetworkXAPI Error (initialize_network): {response.status_code} - {response.text}")
        response.raise_for_status()
        return response.json()

async def list_node_attributes(network_id: int):
    logger.info(f"Listing node attributes for network {network_id}")
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.get(
            f"{NETWORKX_API_URL}/tools/list_node_attributes",
            params={"network_id": network_id}
        )
        response.raise_for_status()
        return response.json()

async def list_edge_attributes(network_id: int):
    logger.info(f"Listing edge attributes for network {network_id}")
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.get(
            f"{NETWORKX_API_URL}/tools/list_edge_attributes",
            params={"network_id": network_id}
        )
        response.raise_for_status()
        return response.json()

async def calculate_centrality(network_id: int, centrality_type: str):
    logger.info(f"Calculating {centrality_type} centrality for network {network_id}")
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{NETWORKX_API_URL}/tools/calculate_centrality",
            json={"network_id": network_id, "centrality_type": centrality_type}
        )
        if response.is_error:
            logger.error(f"NetworkXAPI Error (calculate_centrality): {response.status_code} - {response.text}")
        response.raise_for_status()
        return response.json()

async def calculate_layout(network_id: int, layout_name: str):
    logger.info(f"Calculating {layout_name} layout for network {network_id}")
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{NETWORKX_API_URL}/tools/calculate_layout",
            json={"network_id": network_id, "layout_name": layout_name}
        )
        if response.is_error:
            logger.error(f"NetworkXAPI Error (calculate_layout): {response.status_code} - {response.text}")
        response.raise_for_status()
        return response.json()

async def generate_visualization(network_id: int, params: dict):
    logger.info(f"Generating visualization for network {network_id} with params: {params}")
    async with httpx.AsyncClient(timeout=120.0) as client:
        # params should include layout_name, node_size_config, etc.
        payload = {"network_id": network_id, **params}
        response = await client.post(
            f"{NETWORKX_API_URL}/tools/generate_visualization",
            json=payload
        )
        if response.is_error:
            logger.error(f"NetworkXAPI Error (generate_visualization): {response.status_code} - {response.text}")
        response.raise_for_status()
        return response.json()

async def export_network(network_id: int) -> str:
    """Export network as GraphML from NetworkXAPI"""
    logger.info(f"Exporting network {network_id}")
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.get(
            f"{NETWORKX_API_URL}/tools/export_network",
            params={"network_id": network_id}
        )
        response.raise_for_status()
        return response.text

async def create_ego_network(source_network_id: int, center_node_id: str, radius: int):
    logger.info(f"Creating ego network for {source_network_id} center={center_node_id} radius={radius}")
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{NETWORKX_API_URL}/tools/create_ego_network",
            json={"source_network_id": source_network_id, "center_node_id": center_node_id, "radius": radius}
        )
        response.raise_for_status()
        return response.json()

async def create_subgraph_from_nodes(source_network_id: int, node_ids: list):
    logger.info(f"Creating subgraph from nodes for {source_network_id} count={len(node_ids)}")
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{NETWORKX_API_URL}/tools/create_subgraph_from_nodes",
            json={"source_network_id": source_network_id, "node_ids": node_ids}
        )
        response.raise_for_status()
        return response.json()

async def create_path_subgraph(source_network_id: int, source_node_id: str, target_node_id: str):
    logger.info(f"Creating path subgraph for {source_network_id} {source_node_id}->{target_node_id}")
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{NETWORKX_API_URL}/tools/create_path_subgraph",
            json={"source_network_id": source_network_id, "source_node_id": source_node_id, "target_node_id": target_node_id}
        )
        response.raise_for_status()
        return response.json()

async def create_k_core_subgraph(source_network_id: int, k: int):
    logger.info(f"Creating k-core subgraph for {source_network_id} k={k}")
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{NETWORKX_API_URL}/tools/create_k_core_subgraph",
            json={"source_network_id": source_network_id, "k": k}
        )
        response.raise_for_status()
        return response.json()

async def create_largest_component_subgraph(source_network_id: int):
    logger.info(f"Creating largest component subgraph for {source_network_id}")
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{NETWORKX_API_URL}/tools/create_largest_component_subgraph",
            json={"source_network_id": source_network_id}
        )
        response.raise_for_status()
        return response.json()

async def get_subgraphs(network_id: int):
    logger.info(f"Getting subgraphs for {network_id}")
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.get(
            f"{NETWORKX_API_URL}/tools/get_subgraphs",
            params={"network_id": network_id}
        )
        response.raise_for_status()
        return response.json()

async def get_top_nodes(network_id: int, metric: str, k: int = 10) -> List[Dict[str, Any]]:
    logger.info(f"Getting top {k} nodes for network {network_id} by metric {metric}")
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{NETWORKX_API_URL}/tools/get_top_nodes",
            json={"network_id": network_id, "metric": metric, "k": k}
        )
        if response.is_error:
            logger.error(f"NetworkXAPI Error (get_top_nodes): {response.status_code} - {response.text}")
        response.raise_for_status()
        return response.json()
