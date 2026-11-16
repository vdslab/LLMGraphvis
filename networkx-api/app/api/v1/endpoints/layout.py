from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.logic import layout
from app.schemas.layout import LayoutRequest

router = APIRouter()


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


@router.post("/{network_id}/layout/initial")
def calculate_initial_layout(network_id: int, db: Session = Depends(get_db)):
    """The first layout of an upload, chosen by the app from the network's size.

    ForceAtlas2, or spring where ForceAtlas2 would not settle (ADR 0047). The
    response names the layout that ran.
    """
    try:
        info = layout.calculate_initial_layout(network_id, db)
        return {"status": "calculated", "layout": info["layout_name"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
