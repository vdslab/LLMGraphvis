from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from app.core import database
from app.logic import importer, exporter, attributes
from app import models
from app.core.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)

def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/initialize")
def initialize_network(network_id: int = Body(...), graphml_data: str = Body(...), db: Session = Depends(get_db)):
    """Initializes a network from GraphML data."""
    try:
        logger.info(f"Initializing network_id={network_id}")
        final_network_id = importer.parse_and_save_graphml(network_id, graphml_data, db)
        logger.info(f"Network initialized successfully: network_id={final_network_id}")
        return {"network_id": final_network_id, "status": "initialized"}
    except Exception as e:
        logger.error(f"Failed to initialize network: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{network_id}/export")
def export_network(network_id: int, db: Session = Depends(get_db)):
    """Exports the network to GraphML."""
    try:
        logger.info(f"Exporting network_id={network_id}")
        data = exporter.export_network_to_graphml(network_id, db)
        return {"graphml": data}
    except Exception as e:
        logger.error(f"Failed to export network: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{network_id}/attributes/nodes")
def list_node_attributes(network_id: int, db: Session = Depends(get_db)):
    """Lists available node attributes."""
    try:
        return attributes.get_attribute_stats(
            network_id,
            models.NodeAttribute,
            models.NodeAttributeValue,
            models.NodeFloatAttributeValue,
            models.NodeTextAttributeValue,
            db
        )
    except Exception as e:
        logger.error(f"Error listing node attributes: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{network_id}/attributes/edges")
def list_edge_attributes(network_id: int, db: Session = Depends(get_db)):
    """Lists available edge attributes."""
    try:
        return attributes.get_attribute_stats(
            network_id,
            models.EdgeAttribute,
            models.EdgeAttributeValue,
            models.EdgeFloatAttributeValue,
            models.EdgeTextAttributeValue,
            db
        )
    except Exception as e:
        logger.error(f"Error listing edge attributes: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

from app.schemas.network import UpdateNetworkMetadataRequest, NetworkMetadataResponse

@router.get("/{network_id}/metadata", response_model=NetworkMetadataResponse)
def get_network_metadata(network_id: int, db: Session = Depends(get_db)):
    """Get network metadata."""
    network = db.query(models.Network).filter(models.Network.id == network_id).first()
    if not network:
        raise HTTPException(status_code=404, detail="Network not found")
    
    return NetworkMetadataResponse(
        id=network.id,
        name=network.name,
        description=network.description,
        created_at=network.created_at,
        updated_at=network.updated_at,
        is_subgraph=network.parent_network_id is not None,
        parent_network_id=network.parent_network_id
    )

@router.put("/{network_id}/metadata", response_model=NetworkMetadataResponse)
def update_network_metadata(
    network_id: int, 
    request: UpdateNetworkMetadataRequest, 
    db: Session = Depends(get_db)
):
    """Update network metadata (name, description)."""
    network = db.query(models.Network).filter(models.Network.id == network_id).first()
    if not network:
        raise HTTPException(status_code=404, detail="Network not found")
    
    if request.name is not None:
        network.name = request.name
    if request.description is not None:
        network.description = request.description
    
    try:
        db.commit()
        db.refresh(network)
    except Exception as e:
        logger.error(f"Error updating network metadata: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Database commit failed")
    
    return NetworkMetadataResponse(
        id=network.id,
        name=network.name,
        description=network.description,
        created_at=network.created_at,
        updated_at=network.updated_at,
        is_subgraph=network.parent_network_id is not None,
        parent_network_id=network.parent_network_id
    )
