from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from app.core import database
from app.logic import importer, exporter, attributes, search
from app import models
from app.core.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)

from app.core.database import get_db

@router.post("/initialize")
def initialize_network(network_id: int = Body(...), graphml_data: str = Body(...), db: Session = Depends(get_db)):
    """Initializes a network from GraphML data."""
    try:
        logger.info(f"Initializing network_id={network_id}")
        final_network_id = importer.parse_and_save_graphml(network_id, graphml_data, db)
        
        # Calculate default layout (Required for visualization)
        from app.logic import layout
        layout.calculate_layout(final_network_id, "forceatlas2", db)
        
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

@router.get("/{network_id}/nodes/search")
def search_nodes(
    network_id: int, 
    q: str, 
    attribute: str = None, 
    limit: int = 10, 
    db: Session = Depends(get_db)
):
    """
    Search for nodes in a network.
    
    - **q**: Search query string.
    - **attribute**: (Optional) Filter by specific attribute name.
    - **limit**: Max results (default 10).
    """
    try:
        results = search.search_nodes(network_id, q, attribute, limit, db)
        return results
    except Exception as e:
        logger.error(f"Error searching nodes: {e}", exc_info=True)
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
        parent_network_id=network.parent_network_id,
        last_layout_name=network.last_layout_name,
        last_node_size_config=network.last_node_size_config,
        last_node_color_config=network.last_node_color_config
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
        parent_network_id=network.parent_network_id,
        last_layout_name=network.last_layout_name,
        last_node_size_config=network.last_node_size_config,
        last_node_color_config=network.last_node_color_config
    )

from app.schemas.filter import SubgraphFilterRequest
from app.logic import filter

@router.post("/{network_id}/subgraphs/filter")
def create_subgraph_by_filter_endpoint(
    network_id: int,
    request: SubgraphFilterRequest,
    db: Session = Depends(get_db)
):
    """
    Creates a subgraph by filtering nodes based on attributes.
    """
    try:
        logger.info(f"Received filter request for network {network_id}")
        result = filter.create_subgraph_by_filter(network_id, request.conditions, request.suffix, db)
        return result
    except ValueError as e:
        logger.warning(f"Filter error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating filtered subgraph: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
