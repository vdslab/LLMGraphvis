from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core import database
from app.logic import visualizer
from app.schemas.visualization import VisualizationRequest

router = APIRouter()

def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/{network_id}/visualization")
def generate_visualization(network_id: int, request: VisualizationRequest, db: Session = Depends(get_db)):
    """Generates visualization data."""
    try:
        return visualizer.generate_visualization_data(
            network_id,
            db,
            layout_name=request.layout_name,
            node_size_config=request.node_size_config,
            node_color_config=request.node_color_config,
            edge_width_config=request.edge_width_config,
            edge_color_config=request.edge_color_config,
            focus_network_id=request.focus_network_id,
            context_config=request.context_config,
            focus_config=request.focus_config,
            node_label_config=request.node_label_config,
            custom_node_colors=request.custom_node_colors
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
