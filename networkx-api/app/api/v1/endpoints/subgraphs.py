from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core import database
from app.logic import subgraph
from app import models
from app.schemas.subgraph import (
    EgoNetworkRequest, 
    NodesSubgraphRequest, 
    PathSubgraphRequest, 
    PathSubgraphRequest, 
    KCoreRequest,
    ComponentContainingNodeRequest
)

router = APIRouter()

def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("/{network_id}/subgraphs")
def get_subgraphs(network_id: int, db: Session = Depends(get_db)):
    """List subgraphs."""
    try:
        subgraphs = db.query(models.Network).filter(models.Network.parent_network_id == network_id).all()
        return [{"id": s.id, "name": s.name, "created_at": str(s.created_at)} for s in subgraphs]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{network_id}/subgraphs/ego")
def create_ego_network(network_id: int, request: EgoNetworkRequest, db: Session = Depends(get_db)):
    try:
        return subgraph.create_ego_network(network_id, request.center_node_id, request.radius, db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{network_id}/subgraphs/from-nodes")
def create_subgraph_from_nodes(network_id: int, request: NodesSubgraphRequest, db: Session = Depends(get_db)):
    try:
        return subgraph.create_subgraph_from_nodes(network_id, request.node_ids, db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{network_id}/subgraphs/path")
def create_path_subgraph(network_id: int, request: PathSubgraphRequest, db: Session = Depends(get_db)):
    try:
        return subgraph.create_path_subgraph(network_id, request.source_node_id, request.target_node_id, db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{network_id}/subgraphs/k-core")
def create_k_core_subgraph(network_id: int, request: KCoreRequest, db: Session = Depends(get_db)):
    try:
        return subgraph.create_k_core_subgraph(network_id, request.k, db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{network_id}/subgraphs/largest-component")
def create_largest_component_subgraph(network_id: int, db: Session = Depends(get_db)):
    try:
        return subgraph.create_largest_component_subgraph(network_id, db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/{network_id}/subgraphs/component-containing-node")
def create_component_containing_node(network_id: int, request: ComponentContainingNodeRequest, db: Session = Depends(get_db)):
    try:
        return subgraph.create_component_containing_node(network_id, request.node_id, db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
