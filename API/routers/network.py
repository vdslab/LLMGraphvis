"""
API endpoints for managing network data.

This module provides routes for uploading, exporting, and retrieving
network data in various formats.
"""

from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Response
from sqlalchemy.orm import Session
from typing import Dict, Any, List, Optional
import networkx as nx
import io
import json
import logging

import models
import schemas
import auth
from database import get_db
from services import mcp_client

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/network",
    tags=["network"],
    responses={404: {"description": "Not found"}},
)

def get_network_for_user(db: Session, network_id: int, user_id: int) -> models.Network:
    """
    Retrieves a network for a given user, ensuring ownership.

    Args:
        db: The database session.
        network_id: The ID of the network to retrieve.
        user_id: The ID of the user requesting the network.

    Returns:
        The network object.
    """
    db_network = db.query(models.Network).filter(
        models.Network.id == network_id
    ).first()

    if not db_network:
        raise HTTPException(status_code=404, detail="Network not found")

    # Check if the network's conversation belongs to the current user
    if db_network.conversation.user_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to access this network")
        
    return db_network

@router.get("/{network_id}/cytoscape", response_model=Dict[str, Any])
async def get_network_cytoscape_format(
    network_id: int,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Retrieves a network in Cytoscape.js JSON format.

    Args:
        network_id: The ID of the network to retrieve.
        current_user: The current authenticated user.
        db: The database session.

    Returns:
        A dictionary containing the network data in Cytoscape.js format.
    """
    db_network = get_network_for_user(db, network_id, current_user.id)
    
    try:
        G = nx.read_graphml(io.StringIO(db_network.graphml_content))
        
        # 位置情報もCytoscape形式に含める
        nodes = []
        for n, data in G.nodes(data=True):
            node_data = {"data": {"id": str(n), **data}}
            if 'x' in data and 'y' in data:
                node_data["position"] = {"x": data['x'], "y": data['y']}
            nodes.append(node_data)
            
        edges = [{"data": {"source": str(u), "target": str(v), **d}} for u, v, d in G.edges(data=True)]
        
        return {"elements": {"nodes": nodes, "edges": edges}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing GraphML: {str(e)}")

@router.get("/{network_id}/visdata", response_model=Dict[str, Any])
async def get_network_visualization_data(
    network_id: int,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Retrieves network data optimized for visualization.
    
    This endpoint dynamically generates rendering data by combining the network structure
    with visual mapping rules and attribute values from the database.
    
    Args:
        network_id: The ID of the network to retrieve.
        current_user: The current authenticated user.
        db: The database session.
        
    Returns:
        A dictionary containing nodes and links data ready for visualization.
    """
    db_network = get_network_for_user(db, network_id, current_user.id)
    
    try:
        # Parse GraphML content
        G = nx.read_graphml(io.StringIO(db_network.graphml_content))
        
        # Default visual properties
        default_node_size = 5
        default_node_color = "#82b3ff"  # システムのテーマカラーに合わせた明るい青
        default_edge_width = 1
        default_edge_color = "#cccccc"  # 他の要素を邪魔しない薄いグレー
        
        # Prepare nodes data
        nodes_data = []
        for node_id, attrs in G.nodes(data=True):
            # Extract position from attributes
            x = float(attrs.get('x', 0))
            y = float(attrs.get('y', 0))
            
            # Extract or set default visual properties
            size = float(attrs.get('size', default_node_size))
            color = attrs.get('color', default_node_color)
            label = attrs.get('name', str(node_id))
            
            # Create node object
            node = {
                "id": str(node_id),
                "label": label,
                "x": x,
                "y": y,
                "size": size,
                "color": color
            }
            
            # Add any additional attributes that might be useful
            for key, value in attrs.items():
                if key not in ["id", "label", "x", "y", "size", "color", "name"]:
                    node[key] = value
            
            nodes_data.append(node)
        
        # Prepare edges data
        links_data = []
        for source, target, attrs in G.edges(data=True):
            # Extract or set default visual properties
            width = float(attrs.get('width', default_edge_width))
            color = attrs.get('color', default_edge_color)
            
            # Create edge object
            edge = {
                "source": str(source),
                "target": str(target),
                "width": width,
                "color": color
            }
            
            # Add any additional attributes
            for key, value in attrs.items():
                if key not in ["source", "target", "width", "color"]:
                    edge[key] = value
            
            links_data.append(edge)
        
        # Return the visualization data
        return {
            "nodes": nodes_data,
            "links": links_data
        }
    except Exception as e:
        logger.error(f"Error generating visualization data: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail={
                "error_code": "VISUALIZATION_ERROR",
                "message": f"Error generating visualization data: {str(e)}",
                "context": {"network_id": network_id}
            }
        )

@router.get("/{network_id}/export")
async def export_network_graphml(
    network_id: int,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """
    Exports a network as a GraphML file.

    Args:
        network_id: The ID of the network to export.
        current_user: The current authenticated user.
        db: The database session.

    Returns:
        A GraphML file as a response.
    """
    db_network = get_network_for_user(db, network_id, current_user.id)
    return Response(
        content=db_network.graphml_content,
        media_type="application/xml",
        headers={"Content-Disposition": f"attachment; filename=network_{network_id}.graphml"}
    )

@router.post("/upload", response_model=Dict[str, int])
async def upload_new_network(
    file: UploadFile = File(...),
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Uploads a new network from a GraphML file.

    Args:
        file: The GraphML file to upload.
        current_user: The current authenticated user.
        db: The database session.

    Returns:
        A dictionary with the new conversation and network IDs.
    """
    if not file.filename.endswith(".graphml"):
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload a .graphml file.")
    
    try:
        graphml_content_bytes = await file.read()
        graphml_content_str = graphml_content_bytes.decode("utf-8")

        # Call NetworkXMCP to convert/normalize the GraphML
        try:
            result = await mcp_client.convert_graphml(graphml_content_str)
            normalized_graphml_str = result.get("graphml_content", "")
            logger.info(f"Normalized GraphML length: {len(normalized_graphml_str)}")
        except mcp_client.MCPError as e:
            logger.error(f"Error from NetworkXMCP: {e.message}")
            raise HTTPException(status_code=e.status_code, detail=e.message)

        # Create a new conversation
        db_conversation = models.Conversation(
            title=f"Conversation for {file.filename}",
            user_id=current_user.id
        )
        db.add(db_conversation)
        db.commit()
        db.refresh(db_conversation)

        # Create the associated network with the normalized content
        db_network = models.Network(
            name=file.filename,
            conversation_id=db_conversation.id,
            graphml_content=normalized_graphml_str
        )
        db.add(db_network)
        db.commit()
        db.refresh(db_network)

        # Calculate default layout (spring) for the network
        try:
            await mcp_client.change_layout(db_network.id, "spring")
            logger.info(f"Applied default spring layout to network {db_network.id}")
        except mcp_client.MCPError as e:
            # Log the error but don't fail the upload
            logger.error(f"Error applying default layout: {e.message}")
            # We continue without raising an exception since the network was created successfully

        return {"conversation_id": db_conversation.id, "network_id": db_network.id}

    except HTTPException as e:
        # Re-raise HTTPException to preserve status code and detail
        raise e
    except Exception as e:
        logger.error(f"Unexpected error in upload_new_network: {str(e)}")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")


@router.post("/{network_id}/layout")
async def calculate_network_layout(
    network_id: int,
    layout_type: str = "spring",
    layout_params: Dict[str, Any] = {},
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Calculates the layout for a network.

    This endpoint proxies the layout calculation to the NetworkXMCP service.

    Args:
        network_id: The ID of the network.
        layout_type: The type of layout to apply.
        layout_params: Parameters for the layout algorithm.
        current_user: The current authenticated user.
        db: The database session.

    Returns:
        The result of the layout calculation from the NetworkXMCP service.
    """
    # First, verify the user has access to this network.
    get_network_for_user(db, network_id, current_user.id)
    
    try:
        result = await mcp_client.change_layout(network_id, layout_type, layout_params)
        return result
    except mcp_client.MCPError as e:
        raise HTTPException(status_code=e.status_code, detail=e.message)
    except Exception as e:
        logger.error(f"Unexpected error in calculate_network_layout: {str(e)}")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")


@router.post("/{conversation_id}/upload", response_model=schemas.Network)
async def upload_and_overwrite_network(
    conversation_id: int,
    file: UploadFile = File(...),
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Uploads a GraphML file to overwrite an existing network.

    Args:
        conversation_id: The ID of the conversation containing the network.
        file: The GraphML file to upload.
        current_user: The current authenticated user.
        db: The database session.

    Returns:
        The updated network.
    """
    if not file.filename.endswith(".graphml"):
        raise HTTPException(status_code=400, detail="Invalid file type. Please upload a .graphml file.")
    
    # Find the conversation and verify ownership
    db_conversation = db.query(models.Conversation).filter(
        models.Conversation.id == conversation_id,
        models.Conversation.user_id == current_user.id
    ).first()

    if not db_conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")

    db_network = db_conversation.network
    if not db_network:
        raise HTTPException(status_code=404, detail="Network not found for this conversation")

    try:
        graphml_content_bytes = await file.read()
        graphml_content_str = graphml_content_bytes.decode("utf-8")

        # Call NetworkXMCP to convert/normalize the GraphML
        try:
            result = await mcp_client.convert_graphml(graphml_content_str)
            normalized_graphml_str = result.get("graphml_content", "")
            logger.info(f"Normalized GraphML length: {len(normalized_graphml_str)}")
        except mcp_client.MCPError as e:
            logger.error(f"Error from NetworkXMCP: {e.message}")
            raise HTTPException(status_code=e.status_code, detail=e.message)

        # Update the network content
        db_network.graphml_content = normalized_graphml_str
        db_network.name = file.filename
        db.commit()
        db.refresh(db_network)
        
        # Calculate default layout (spring) for the network
        try:
            await mcp_client.change_layout(db_network.id, "spring")
            logger.info(f"Applied default spring layout to network {db_network.id}")
        except mcp_client.MCPError as e:
            # Log the error but don't fail the upload
            logger.error(f"Error applying default layout: {e.message}")
            # We continue without raising an exception since the network was updated successfully
        
        return db_network
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Unexpected error in upload_and_overwrite_network: {str(e)}")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")