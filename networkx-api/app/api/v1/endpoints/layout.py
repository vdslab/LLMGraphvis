from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.logic import layout
from app.schemas.layout import LayoutRequest

router = APIRouter()

from app.core.database import get_db


@router.post("/{network_id}/layout")
def calculate_layout(
    network_id: int, request: LayoutRequest, db: Session = Depends(get_db)
):
    """Calculates layout for a network."""
    try:
        layout.calculate_layout(network_id, request.layout_name, db)
        return {"status": "calculated", "layout": request.layout_name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
