"""
API endpoints for managing network data.

This module provides routes for uploading, exporting, and retrieving
network data in various formats.
"""

from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Response
from sqlalchemy.orm import Session
from typing import Dict, Any
import networkx as nx
import io
import json

import models
import schemas
import auth
from database import get_db
import os
import httpx

# NetworkXMCPサーバーとの通信用URL
NETWORKX_MCP_URL = os.environ.get("NETWORKX_MCP_URL", "http://networkx-mcp:8001")

router = APIRouter(
    prefix="/network",
    tags=["network"],
    dependencies=[Depends(auth.get_current_active_user)],
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

@router.get("/{network_id}/export")
async def export_network_graphml(
    network_id: int,
    current_user: models.User = Depends(auth.get_current_active_user),
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
        async with httpx.AsyncClient() as client:
            url = f"{NETWORKX_MCP_URL}/tools/convert_graphml"
            payload = {"graphml_content": graphml_content_str}
            print(f"Sending GraphML to NetworkXMCP for conversion: {url}")
            
            response = await client.post(url, json=payload, timeout=60.0)
            print(f"Response status: {response.status_code}")
            
            if response.status_code != 200:
                error_msg = f"Error from NetworkXMCP: {response.text}"
                print(f"Error: {error_msg}")
                raise HTTPException(status_code=500, detail=error_msg)
            
            result = response.json()
            print(f"Response from NetworkXMCP: {result}")
            
            if not result.get("success"):
                error_msg = result.get("error", "Unknown error from NetworkXMCP")
                print(f"Error: {error_msg}")
                raise HTTPException(status_code=500, detail=error_msg)
            
            normalized_graphml_str = result.get("graphml_content", "")
            print(f"Normalized GraphML length: {len(normalized_graphml_str)}")

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

        return {"conversation_id": db_conversation.id, "network_id": db_network.id}

    except HTTPException as e:
        # Re-raise HTTPException to preserve status code and detail
        raise e
    except Exception as e:
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
        async with httpx.AsyncClient() as client:
            url = f"{NETWORKX_MCP_URL}/tools/change_layout"
            # The new payload now only needs the network_id and layout parameters
            payload = {
                "network_id": network_id,
                "layout_type": layout_type,
                "layout_params": layout_params
            }
            print(f"Proxying layout request to NetworkXMCP: {url} with payload: {payload}")
            
            response = await client.post(url, json=payload, timeout=60.0)
            
            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail=f"Error from NetworkXMCP: {response.text}")
            
            # Return the exact response from the MCP service
            return response.json()

    except HTTPException as e:
        raise e
    except Exception as e:
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
        async with httpx.AsyncClient() as client:
            url = f"{NETWORKX_MCP_URL}/tools/convert_graphml"
            payload = {"graphml_content": graphml_content_str}
            print(f"Sending GraphML to NetworkXMCP for conversion: {url}")
            
            response = await client.post(url, json=payload, timeout=60.0)
            print(f"Response status: {response.status_code}")
            
            if response.status_code != 200:
                error_msg = f"Error from NetworkXMCP: {response.text}"
                print(f"Error: {error_msg}")
                raise HTTPException(status_code=500, detail=error_msg)
            
            result = response.json()
            print(f"Response from NetworkXMCP: {result}")
            
            if not result.get("success"):
                error_msg = result.get("error", "Unknown error from NetworkXMCP")
                print(f"Error: {error_msg}")
                raise HTTPException(status_code=500, detail=error_msg)
            
            normalized_graphml_str = result.get("graphml_content", "")
            print(f"Normalized GraphML length: {len(normalized_graphml_str)}")

        # Update the network content
        db_network.graphml_content = normalized_graphml_str
        db_network.name = file.filename
        db.commit()
        db.refresh(db_network)
        
        return db_network
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")
