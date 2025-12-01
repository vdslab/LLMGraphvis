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

class GenerateVisualizationRequest(BaseModel):
    network_id: int
    layout_name: Optional[str] = "spring"
    node_size_config: Optional[Dict[str, Any]] = None
    node_color_config: Optional[Dict[str, Any]] = None
    edge_width_config: Optional[Dict[str, Any]] = None
    edge_color_config: Optional[Dict[str, Any]] = None
    overlay_network_id: Optional[int] = None

class CalculateLayoutRequest(BaseModel):
    network_id: int
    layout_name: str

class CreateEgoNetworkRequest(BaseModel):
    source_network_id: int
    center_node_id: str
    radius: int

class CreateSubgraphFromNodesRequest(BaseModel):
    source_network_id: int
    node_ids: List[str]

class CreatePathSubgraphRequest(BaseModel):
    source_network_id: int
    source_node_id: str
    target_node_id: str

class CreateKCoreSubgraphRequest(BaseModel):
    source_network_id: int
    k: int

class CreateLargestComponentSubgraphRequest(BaseModel):
    source_network_id: int

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
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/list_node_attributes")
def list_node_attributes(network_id: int, db: Session = Depends(database.get_db)):
    attributes = db.query(models.NodeAttribute).filter(models.NodeAttribute.network_id == network_id).all()
    return [attr.attribute_name for attr in attributes]

@router.get("/list_edge_attributes")
def list_edge_attributes(network_id: int, db: Session = Depends(database.get_db)):
    attributes = db.query(models.EdgeAttribute).filter(models.EdgeAttribute.network_id == network_id).all()
    return [attr.attribute_name for attr in attributes]

@router.post("/calculate_centrality")
def calculate_centrality(request: CalculateCentralityRequest, db: Session = Depends(database.get_db)):
    try:
        graph_processor.calculate_centrality(request.network_id, request.centrality_type, db)
        return {"status": "success", "message": f"{request.centrality_type} centrality calculated."}
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
            node_color_config=request.node_color_config,
            edge_width_config=request.edge_width_config,
            edge_color_config=request.edge_color_config,
            overlay_network_id=request.overlay_network_id
        )
        return vis_data
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/create_ego_network")
def create_ego_network(request: CreateEgoNetworkRequest, db: Session = Depends(database.get_db)):
    try:
        result = graph_processor.create_ego_network(request.source_network_id, request.center_node_id, request.radius, db)
        return result
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/create_subgraph_from_nodes")
def create_subgraph_from_nodes(request: CreateSubgraphFromNodesRequest, db: Session = Depends(database.get_db)):
    try:
        result = graph_processor.create_subgraph_from_nodes(request.source_network_id, request.node_ids, db)
        return result
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/create_path_subgraph")
def create_path_subgraph(request: CreatePathSubgraphRequest, db: Session = Depends(database.get_db)):
    try:
        result = graph_processor.create_path_subgraph(request.source_network_id, request.source_node_id, request.target_node_id, db)
        return result
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/create_k_core_subgraph")
def create_k_core_subgraph(request: CreateKCoreSubgraphRequest, db: Session = Depends(database.get_db)):
    try:
        result = graph_processor.create_k_core_subgraph(request.source_network_id, request.k, db)
        return result
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/create_largest_component_subgraph")
def create_largest_component_subgraph(request: CreateLargestComponentSubgraphRequest, db: Session = Depends(database.get_db)):
    try:
        result = graph_processor.create_largest_component_subgraph(request.source_network_id, db)
        return result
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/get_subgraphs")
def get_subgraphs(network_id: int, db: Session = Depends(database.get_db)):
    try:
        subgraphs = db.query(models.Network).filter(models.Network.parent_network_id == network_id).all()
        return [{"id": s.id, "name": s.name, "created_at": s.created_at} for s in subgraphs]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
