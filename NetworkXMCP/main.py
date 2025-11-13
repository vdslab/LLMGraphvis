"""
Stateful NetworkX MCP Server.

This FastAPI application provides a stateful API for network analysis and
visualization. It uses a database to cache calculation results for
improved performance.
"""

import os
import logging
import networkx as nx
import numpy as np
from typing import Dict, Any, List, Optional, Union
from fastapi import FastAPI, Depends, HTTPException, Body, Request, Header
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi_mcp import FastApiMCP
from pydantic import BaseModel, Field
import random
import json
import io
from datetime import datetime

# SQLAlchemy imports
from sqlalchemy import create_engine, Column, Integer, String, Text, ForeignKey
from sqlalchemy.orm import sessionmaker, relationship, Session
from sqlalchemy.ext.declarative import declarative_base

# --- Database Setup ---
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@db:5432/graphvis")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# --- SQLAlchemy Models ---
class Conversation(Base):
    __tablename__ = "conversations"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer)

class Network(Base):
    __tablename__ = "networks"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, default="Untitled Network")
    conversation_id = Column(Integer, ForeignKey("conversations.id"), unique=True)
    graphml_content = Column(Text, nullable=False)
    layout_cache = Column(Text, default="{}")
    centrality_cache = Column(Text, default="{}")

    conversation = relationship("Conversation")

# Dependency to get DB session
def get_db():
    """
    Provides a database session for dependency injection.

    Yields:
        A new database session.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Logging Setup ---
log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=log_level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("networkx_mcp")

# --- FastAPI App ---
app = FastAPI(
    title="NetworkX MCP (Stateful)",
    description="Stateful MCP server for network analysis with caching.",
    version="0.3.0",
)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

# --- Pydantic Models ---
class GraphDataBase(BaseModel):
    network_id: int = Field(..., description="The ID of the network to operate on.")

class LayoutParams(GraphDataBase):
    layout_type: str = Field("spring", description="The layout algorithm to apply.")
    layout_params: Dict[str, Any] = Field({}, description="Parameters for the layout algorithm.")

class CentralityParams(GraphDataBase):
    centrality_type: str = Field("degree", description="The type of centrality to calculate.")
    centrality_params: Dict[str, Any] = Field({}, description="Parameters for the centrality calculation.")

class VisualMappingParams(GraphDataBase):
    metric: str = Field("degree_centrality", description="The metric to map (e.g. degree_centrality).")
    visual: str = Field("node_size", description="The visual attribute to map to (e.g. node_size, node_color).")
    mapping: Dict[str, Any] = Field({}, description="Mapping parameters (e.g. min_size, max_size).")

class GraphMLConvertParams(BaseModel):
    graphml_content: str = Field(..., description="GraphML content to convert.")

# --- Helper Functions ---
def parse_graphml_string(graphml_content: str) -> nx.Graph:
    """
    Parses a GraphML string and returns a NetworkX graph.

    Args:
        graphml_content: The GraphML content as a string.

    Returns:
        A NetworkX graph object.
    """
    try:
        content_io = io.BytesIO(graphml_content.encode('utf-8'))
        return nx.read_graphml(content_io)
    except Exception as e:
        logger.error(f"Error parsing GraphML string: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid GraphML content: {e}")

# --- API Endpoints ---
@app.get("/health")
async def health_check():
    """
    Checks the health of the service.

    Returns:
        A dictionary with the health status.
    """
    return {"status": "ok"}

@app.post("/tools/change_layout", response_model=Dict[str, Any])
async def api_change_layout(params: LayoutParams, db: Session = Depends(get_db)):
    """
    Changes the layout of a network.

    Args:
        params: The layout parameters.
        db: The database session.

    Returns:
        The result of the layout change operation.
    """
    db_network = db.query(Network).filter(Network.id == params.network_id).first()
    if not db_network:
        raise HTTPException(status_code=404, detail="Network not found")

    try:
        layout_cache = json.loads(db_network.layout_cache)
        if params.layout_type in layout_cache:
            logger.info(f"Cache hit for layout '{params.layout_type}' on network {params.network_id}")
            return {"result": {"success": True, "layout_type": params.layout_type, "positions": layout_cache[params.layout_type]}}
    except (json.JSONDecodeError, TypeError):
        layout_cache = {}

    logger.info(f"Cache miss for layout '{params.layout_type}'. Calculating...")
    from tools.network_tools import apply_layout_to_graphml
    
    result = apply_layout_to_graphml(
        db_network.graphml_content,
        params.layout_type,
        params.layout_params
    )

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Layout calculation failed"))

    # Update DB and cache
    db_network.graphml_content = result["graphml_content"]
    layout_cache[params.layout_type] = result["positions"]
    db_network.layout_cache = json.dumps(layout_cache)
    db.commit()
    
    logger.info(f"Cached new layout '{params.layout_type}' for network {params.network_id}")
    return {"result": result}

@app.post("/tools/calculate_centrality", response_model=Dict[str, Any])
async def api_calculate_centrality(params: CentralityParams, db: Session = Depends(get_db)):
    """
    Calculates a centrality metric for a network.

    Args:
        params: The centrality calculation parameters.
        db: The database session.

    Returns:
        The result of the centrality calculation.
    """
    db_network = db.query(Network).filter(Network.id == params.network_id).first()
    if not db_network:
        raise HTTPException(status_code=404, detail="Network not found")

    try:
        centrality_cache = json.loads(db_network.centrality_cache)
        if params.centrality_type in centrality_cache:
            logger.info(f"Cache hit for centrality '{params.centrality_type}' on network {params.network_id}")
            return {"result": centrality_cache[params.centrality_type]}
    except (json.JSONDecodeError, TypeError):
        centrality_cache = {}

    logger.info(f"Cache miss for centrality '{params.centrality_type}'. Calculating...")
    G = parse_graphml_string(db_network.graphml_content)
    
    from tools.network_analysis import calculate_centrality as tools_calculate_centrality
    result = tools_calculate_centrality(G, params.centrality_type, **params.centrality_params)

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Centrality calculation failed"))

    # Update cache
    centrality_cache[params.centrality_type] = {
        "success": True,
        "centrality_type": result["centrality_type"],
        "centrality_values": result["centrality"]
    }
    db_network.centrality_cache = json.dumps(centrality_cache)
    db.commit()
    
    logger.info(f"Cached new centrality '{params.centrality_type}' for network {params.network_id}")
    return {"result": centrality_cache[params.centrality_type]}

@app.post("/tools/apply_metric_to_visual", response_model=Dict[str, Any])
async def api_apply_metric_to_visual(params: VisualMappingParams, db: Session = Depends(get_db)):
    """
    中心性指標などのメトリックをノードの視覚属性（サイズや色など）に適用します。
    
    Args:
        params: 視覚マッピングパラメータ
        db: データベースセッション
    
    Returns:
        視覚マッピングの結果
    """
    db_network = db.query(Network).filter(Network.id == params.network_id).first()
    if not db_network:
        raise HTTPException(status_code=404, detail="Network not found")

    # メトリック値の取得（主に中心性指標）
    try:
        # キャッシュから中心性指標を取得
        metric_type = params.metric
        centrality_type = metric_type.replace("_centrality", "")  # "degree_centrality" -> "degree"
        
        centrality_cache = json.loads(db_network.centrality_cache)
        metric_values = None
        
        # キャッシュから値を取得
        if metric_type in centrality_cache:
            logger.info(f"Cache hit for metric '{metric_type}' on network {params.network_id}")
            if centrality_cache[metric_type].get("centrality_values"):
                metric_values = centrality_cache[metric_type]["centrality_values"]
        
        # キャッシュミスの場合、計算してキャッシュ更新
        if metric_values is None:
            logger.info(f"Cache miss for metric '{metric_type}'. Calculating...")
            G = parse_graphml_string(db_network.graphml_content)
            
            from tools.network_analysis import calculate_centrality as tools_calculate_centrality
            result = tools_calculate_centrality(G, centrality_type)
            
            if not result.get("success"):
                raise HTTPException(status_code=400, detail=result.get("error", f"Failed to calculate {metric_type}"))
            
            metric_values = result["centrality"]
            
            # キャッシュ更新
            centrality_cache[metric_type] = {
                "success": True,
                "centrality_type": metric_type,
                "centrality_values": metric_values
            }
            db_network.centrality_cache = json.dumps(centrality_cache)
            db.commit()
            logger.info(f"Cached new metric '{metric_type}' for network {params.network_id}")
        
        # 視覚属性へのマッピング
        from tools.network_tools import apply_metric_to_visual_in_graphml
        visual_attr = params.visual
        if visual_attr == "node_size":
            visual_attr = "size"  # GraphML属性名に変換
        
        result = apply_metric_to_visual_in_graphml(
            db_network.graphml_content,
            metric_values,
            visual_attr=visual_attr,
            mapping=params.mapping
        )
        
        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("error", "Visual mapping failed"))
        
        # 更新されたGraphMLを保存
        db_network.graphml_content = result["graphml_content"]
        db.commit()
        
        return {
            "result": {
                "success": True,
                "metric": params.metric,
                "visual": params.visual,
                "mapped_nodes": len(result.get("mapped_values", {}))
            }
        }
    
    except (json.JSONDecodeError, TypeError) as e:
        logger.error(f"JSON error in centrality cache: {e}")
        raise HTTPException(status_code=500, detail=f"Error processing centrality data: {str(e)}")
    except Exception as e:
        logger.error(f"Error applying metric to visual: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Error applying metric to visual: {str(e)}")

# Other endpoints like convert_graphml can remain stateless as they don't depend on network_id
@app.post("/tools/convert_graphml", response_model=Dict[str, Any])
async def api_convert_graphml(params: GraphMLConvertParams):
    """
    Converts a GraphML file to a standard format.

    Args:
        params: The GraphML content to convert.

    Returns:
        The converted GraphML content.
    """
    try:
        from tools.graphml_converter import convert_to_standard_graphml
        result = convert_to_standard_graphml(params.graphml_content)

        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("error", "GraphML conversion failed"))
        
        return {
            "success": True,
            "graphml_content": result["graphml_content"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


