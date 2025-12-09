from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.orm import Session
from app.core import database
from app.logic import importer, exporter, attributes
from app import models

router = APIRouter()

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
        final_network_id = importer.parse_and_save_graphml(network_id, graphml_data, db)
        return {"network_id": final_network_id, "status": "initialized"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{network_id}/export")
def export_network(network_id: int, db: Session = Depends(get_db)):
    """Exports the network to GraphML."""
    try:
        data = exporter.export_network_to_graphml(network_id, db)
        return {"graphml": data}
    except Exception as e:
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
        raise HTTPException(status_code=500, detail=str(e))
