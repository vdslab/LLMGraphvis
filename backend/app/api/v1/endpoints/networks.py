from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app import models, schemas
from app.core import database
from app.core import database
from app.services.llm import mcp_client
from app.api.v1.endpoints.auth import get_current_user

router = APIRouter(
    prefix="/networks",
    tags=["networks"]
)

def verify_network_access(network_id: int, user_id: int, db: Session):
    # Check direct ownership via Chat
    chat = db.query(models.Chat).filter(models.Chat.network_id == network_id, models.Chat.user_id == user_id).first()
    if chat: return True
    
    # Check if it's a subgraph (traverse up)
    current_id = network_id
    # Limit depth to avoid infinite loops if cycle exists (should not happen in DAG)
    for _ in range(10):
        network = db.query(models.Network).get(current_id)
        if not network: return False
        if network.parent_network_id:
            current_id = network.parent_network_id
            chat = db.query(models.Chat).filter(models.Chat.network_id == current_id, models.Chat.user_id == user_id).first()
            if chat: return True
        else:
            return False
    return False

@router.get("/{network_id}/subgraphs", response_model=List[schemas.Subgraph])
async def get_subgraphs(
    network_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(database.get_db)
):
    if not verify_network_access(network_id, current_user.id, db):
        raise HTTPException(status_code=403, detail="Access denied")
        
    subgraphs = await mcp_client.execute_tool("get_subgraphs", {"network_id": network_id})
    return subgraphs

@router.post("/{network_id}/subgraphs/ego")
async def create_ego_network(
    network_id: int,
    request: schemas.CreateEgoNetworkRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(database.get_db)
):
    if not verify_network_access(network_id, current_user.id, db):
        raise HTTPException(status_code=403, detail="Access denied")
        
    result = await mcp_client.execute_tool("create_ego_network", {"source_network_id": network_id, "center_node_id": request.center_node_id, "radius": request.radius})
    return result

@router.post("/{network_id}/subgraphs/from_nodes")
async def create_subgraph_from_nodes(
    network_id: int,
    request: schemas.CreateSubgraphFromNodesRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(database.get_db)
):
    if not verify_network_access(network_id, current_user.id, db):
        raise HTTPException(status_code=403, detail="Access denied")
        
    result = await mcp_client.execute_tool("create_subgraph_from_nodes", {"source_network_id": network_id, "node_ids": request.node_ids})
    return result

@router.post("/{network_id}/subgraphs/path")
async def create_path_subgraph(
    network_id: int,
    request: schemas.CreatePathSubgraphRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(database.get_db)
):
    if not verify_network_access(network_id, current_user.id, db):
        raise HTTPException(status_code=403, detail="Access denied")
        
    result = await mcp_client.execute_tool("create_path_subgraph", {"source_network_id": network_id, "source_node_id": request.source_node_id, "target_node_id": request.target_node_id})
    return result

@router.post("/{network_id}/subgraphs/k_core")
async def create_k_core_subgraph(
    network_id: int,
    request: schemas.CreateKCoreSubgraphRequest,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(database.get_db)
):
    if not verify_network_access(network_id, current_user.id, db):
        raise HTTPException(status_code=403, detail="Access denied")
        
    result = await mcp_client.execute_tool("create_k_core_subgraph", {"source_network_id": network_id, "k": request.k})
    return result

@router.post("/{network_id}/subgraphs/largest_component")
async def create_largest_component_subgraph(
    network_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(database.get_db)
):
    if not verify_network_access(network_id, current_user.id, db):
        raise HTTPException(status_code=403, detail="Access denied")
        
    result = await mcp_client.execute_tool("create_largest_component_subgraph", {"source_network_id": network_id})
    return result

@router.get("/{network_id}/nodes/top")
async def get_top_nodes(
    network_id: int,
    metric: str,
    k: int = 10,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(database.get_db)
):
    if not verify_network_access(network_id, current_user.id, db):
        raise HTTPException(status_code=403, detail="Access denied")
        
    result = await mcp_client.execute_tool("get_top_nodes", {"network_id": network_id, "metric": metric, "k": k})
    return result
