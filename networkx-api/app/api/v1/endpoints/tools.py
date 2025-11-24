from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from app.core import database
from app import models
from app.logic import graph_processor, visualizer

router = APIRouter(
    prefix="/tools",
    tags=["tools"]
)

class InitializeNetworkRequest(BaseModel):
    network_id: int
    graphml_data: str

class CalculateCentralityRequest(BaseModel):
    network_id: int
    centrality_type: str

class VisualizeCentralityRequest(BaseModel):
    network_id: int
    centrality_type: str

class GenerateVisualizationRequest(BaseModel):
    network_id: int
    layout_name: Optional[str] = "spring"
    node_size_config: Optional[Dict[str, Any]] = None
    node_color_config: Optional[Dict[str, Any]] = None

class CalculateLayoutRequest(BaseModel):
    network_id: int
    layout_name: str

@router.post("/initialize_network")
def initialize_network(request: InitializeNetworkRequest, db: Session = Depends(database.get_db)):
    try:
        # 1. Parse GraphML and save to DB
        graph_processor.parse_and_save_graphml(request.network_id, request.graphml_data, db)
        
        # 2. Calculate initial layout
        graph_processor.calculate_layout(request.network_id, "spring", db)
        
        # 3. Generate initial visualization
        vis_data = visualizer.generate_visualization_data(request.network_id, db)
        
        return vis_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/list_attributes")
def list_attributes(network_id: int, db: Session = Depends(database.get_db)):
    attributes = db.query(models.NodeAttribute).filter(models.NodeAttribute.network_id == network_id).all()
    return [attr.attribute_name for attr in attributes]

@router.post("/calculate_centrality")
def calculate_centrality(request: CalculateCentralityRequest, db: Session = Depends(database.get_db)):
    try:
        graph_processor.calculate_centrality(request.network_id, request.centrality_type, db)
        return {"status": "success", "message": f"{request.centrality_type} centrality calculated."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/visualize_centrality")
def visualize_centrality(request: VisualizeCentralityRequest, db: Session = Depends(database.get_db)):
    try:
        # 1. Calculate Centrality
        graph_processor.calculate_centrality(request.network_id, request.centrality_type, db)
        
        # 2. Generate Visualization
        # Use default layout (spring) and map centrality to node size
        vis_config = {
            "layout_name": "spring", # Default to spring
            "node_size_config": {
                "attribute": f"{request.centrality_type}_centrality",
                "min": 5.0,
                "max": 20.0
            }
        }
        
        vis_data = visualizer.generate_visualization_data(
            request.network_id, 
            db, 
            layout_name=vis_config["layout_name"],
            node_size_config=vis_config["node_size_config"]
        )
        
        return vis_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/calculate_layout")
def calculate_layout(request: CalculateLayoutRequest, db: Session = Depends(database.get_db)):
    try:
        graph_processor.calculate_layout(request.network_id, request.layout_name, db)
        return {"status": "success", "message": f"Layout '{request.layout_name}' calculated and saved."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/generate_visualization")
def generate_visualization(request: GenerateVisualizationRequest, db: Session = Depends(database.get_db)):
    try:
        # Note: We do NOT calculate layout here anymore. 
        # We assume it's already calculated or we use default/fallback in visualizer.
        vis_data = visualizer.generate_visualization_data(
            request.network_id, 
            db, 
            layout_name=request.layout_name,
            node_size_config=request.node_size_config,
            node_color_config=request.node_color_config
        )
        return vis_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
