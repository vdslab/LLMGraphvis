from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from common import models
from app import schemas
from app.api.v1.endpoints.auth import get_current_user
from app.core import database
from app.services.llm import mcp_client
from app.services.network_service import NetworkService

router = APIRouter(prefix="/networks", tags=["networks"])


@router.get("/{network_id}/subgraphs", response_model=List[schemas.Subgraph])
async def get_subgraphs(
    network_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(database.get_db),
):
    """
    Get all subgraphs for a given network.
    """
    if not NetworkService.verify_network_access(network_id, current_user.id, db):
        raise HTTPException(status_code=403, detail="Access denied")

    subgraphs = await mcp_client.execute_tool(
        "get_subgraphs", {"network_id": network_id}
    )
    return subgraphs


@router.post("/{network_id}/subgraphs/ego")
async def create_ego_network(
    network_id: int,
    request: schemas.CreateEgoNetworkRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(database.get_db),
):
    """
    Create an ego network subgraph.
    """
    if not NetworkService.verify_network_access(network_id, current_user.id, db):
        raise HTTPException(status_code=403, detail="Access denied")

    result = await mcp_client.execute_tool(
        "create_ego_network",
        {
            "source_network_id": network_id,
            "center_node_id": request.center_node_id,
            "radius": request.radius,
        },
    )
    return result


@router.post("/{network_id}/subgraphs/from_nodes")
async def create_subgraph_from_nodes(
    network_id: int,
    request: schemas.CreateSubgraphFromNodesRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(database.get_db),
):
    """
    Create a subgraph from a specific list of nodes.
    """
    if not NetworkService.verify_network_access(network_id, current_user.id, db):
        raise HTTPException(status_code=403, detail="Access denied")

    result = await mcp_client.execute_tool(
        "create_subgraph_from_nodes",
        {"source_network_id": network_id, "node_ids": request.node_ids},
    )
    return result


@router.post("/{network_id}/subgraphs/path")
async def create_path_subgraph(
    network_id: int,
    request: schemas.CreatePathSubgraphRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(database.get_db),
):
    """
    Create a subgraph consisting of the shortest path between two nodes.
    """
    if not NetworkService.verify_network_access(network_id, current_user.id, db):
        raise HTTPException(status_code=403, detail="Access denied")

    result = await mcp_client.execute_tool(
        "create_path_subgraph",
        {
            "source_network_id": network_id,
            "source_node_id": request.source_node_id,
            "target_node_id": request.target_node_id,
        },
    )
    return result


@router.post("/{network_id}/subgraphs/k_core")
async def create_k_core_subgraph(
    network_id: int,
    request: schemas.CreateKCoreSubgraphRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(database.get_db),
):
    """
    Create a k-core subgraph.
    """
    if not NetworkService.verify_network_access(network_id, current_user.id, db):
        raise HTTPException(status_code=403, detail="Access denied")

    result = await mcp_client.execute_tool(
        "create_k_core_subgraph", {"source_network_id": network_id, "k": request.k}
    )
    return result


@router.post("/{network_id}/subgraphs/largest_component")
async def create_largest_component_subgraph(
    network_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(database.get_db),
):
    """
    Create a subgraph for the largest connected component.
    """
    if not NetworkService.verify_network_access(network_id, current_user.id, db):
        raise HTTPException(status_code=403, detail="Access denied")

    result = await mcp_client.execute_tool(
        "create_largest_component_subgraph", {"source_network_id": network_id}
    )
    return result


@router.post("/{network_id}/subgraphs/component_containing_node")
async def create_component_containing_node(
    network_id: int,
    request: schemas.CreateComponentContainingNodeRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(database.get_db),
):
    """
    Create a subgraph for the connected component containing a specific node.
    """
    if not NetworkService.verify_network_access(network_id, current_user.id, db):
        raise HTTPException(status_code=403, detail="Access denied")

    result = await mcp_client.execute_tool(
        "create_component_containing_node",
        {"source_network_id": network_id, "node_id": request.node_id},
    )
    return result


@router.get("/{network_id}/nodes/top")
async def get_top_nodes(
    network_id: int,
    metric: str,
    k: int = 10,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(database.get_db),
):
    """
    Get the top K nodes based on a specific centrality metric.
    """
    if not NetworkService.verify_network_access(network_id, current_user.id, db):
        raise HTTPException(status_code=403, detail="Access denied")

    result = await mcp_client.execute_tool(
        "get_top_nodes", {"network_id": network_id, "metric": metric, "k": k}
    )
    return result


@router.get("/{network_id}/nodes/{node_id}")
async def get_node_details(
    network_id: int,
    node_id: str,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(database.get_db),
):
    """
    Get details for a specific node, including all attributes.
    """
    if not NetworkService.verify_network_access(network_id, current_user.id, db):
        raise HTTPException(status_code=403, detail="Access denied")

    result = await mcp_client.execute_tool(
        "node_get_details", {"network_id": network_id, "node_id": node_id}
    )

    # Helper for error handling from tool
    if isinstance(result, dict) and "error" in result:
        # Check if it's really a 404 or just some other error
        if "not found" in result["error"].lower():
            raise HTTPException(status_code=404, detail=result["error"])
        # Use 400 for bad requests or other errors
        raise HTTPException(status_code=400, detail=result["error"])

    return result
