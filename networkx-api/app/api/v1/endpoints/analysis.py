from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from common import models

from app.logic import centrality
from app.schemas.analysis import CentralityRequest

router = APIRouter()

from app.core.database import get_db


@router.post("/{network_id}/centrality")
def calculate_centrality(
    network_id: int, request: CentralityRequest, db: Session = Depends(get_db)
):
    """Calculates centrality for a network."""
    try:
        centrality.calculate_centrality(network_id, request.centrality_type, db)
        return {"status": "calculated", "type": request.centrality_type}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{network_id}/nodes/top")
def get_top_nodes(
    network_id: int, metric: str, k: int = 10, db: Session = Depends(get_db)
):
    """Returns top K nodes based on a metric."""
    try:
        return centrality.get_top_nodes(network_id, metric, k, db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
