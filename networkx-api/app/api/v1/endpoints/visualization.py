from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.logic import visualizer
from app.schemas.visualization import VisualizationRequest
from common import models

router = APIRouter()
logger = get_logger(__name__)

from app.core.database import get_db


@router.post("/{network_id}/visualization")
def generate_visualization(
    network_id: int, request: VisualizationRequest, db: Session = Depends(get_db)
):
    """Generates visualization data."""
    try:
        logger.info(
            f"Generating visualization for network_id={network_id}, layout={request.layout_name}"
        )
        return visualizer.generate_visualization_data(
            network_id,
            db,
            layout_name=request.layout_name,
            node_size_config=request.node_size_config.model_dump()
            if request.node_size_config
            else None,
            node_color_config=request.node_color_config.model_dump()
            if request.node_color_config
            else None,
            edge_width_config=request.edge_width_config.model_dump()
            if request.edge_width_config
            else None,
            edge_color_config=request.edge_color_config.model_dump()
            if request.edge_color_config
            else None,
            focus_network_id=request.focus_network_id,
            context_config=request.context_config,
            focus_config=request.focus_config,
            node_label_config=request.node_label_config.model_dump()
            if request.node_label_config
            else None,
            custom_node_colors=request.custom_node_colors,
        )
    except ValueError as e:
        logger.warning(f"Validation error in visualization: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error generating visualization: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
