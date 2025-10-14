"""
API endpoint to handle centrality calculation with frontend network data
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, Any, List
import networkx as nx
import io
import httpx
from pydantic import BaseModel
import tempfile

import models
from auth import get_current_active_user
from database import get_db
import os

# NetworkXMCPサーバーとの通信用URL
NETWORKX_MCP_URL = os.environ.get(
    "NETWORKX_MCP_URL", "http://networkx-mcp:8001")

router = APIRouter(
    prefix="/network",
    tags=["network"],
    dependencies=[Depends(get_current_active_user)],
    responses={404: {"description": "Not found"}},
)


class NetworkData(BaseModel):
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]


class CentralityRequest(BaseModel):
    network: NetworkData
    centrality_type: str = "degree"
    color_scheme: str = "viridis"
    size_range: List[float] = [30, 80]  # Updated for better node visibility


def convert_frontend_network_to_graphml(nodes: List[Dict], edges: List[Dict]) -> str:
    """Convert frontend network format to GraphML"""
    try:
        # Create NetworkX graph
        G = nx.Graph()

        # Add nodes
        for node in nodes:
            node_id = str(node.get('id', ''))
            label = node.get('label', node_id)
            G.add_node(node_id, label=label)

        # Add edges
        for edge in edges:
            source = str(edge.get('source', ''))
            target = str(edge.get('target', ''))
            if source and target:
                G.add_edge(source, target)

        # Convert to GraphML - use BytesIO and decode to handle NetworkX compatibility
        try:
            # Use BytesIO since NetworkX might output bytes
            output = io.BytesIO()
            nx.write_graphml(G, output, encoding='utf-8', prettyprint=True)
            output.seek(0)
            graphml_bytes = output.getvalue()
            output.close()

            # Decode bytes to string
            if isinstance(graphml_bytes, bytes):
                graphml_content = graphml_bytes.decode('utf-8')
            else:
                graphml_content = str(graphml_bytes)

            return graphml_content
        except Exception as write_error:
            print(
                f"Warning: BytesIO write failed ({write_error}), trying temporary file method")
            # Alternative: use temporary file with binary mode, then read as text
            with tempfile.NamedTemporaryFile(mode='wb', suffix='.graphml', delete=False) as tmp:
                nx.write_graphml(G, tmp, encoding='utf-8', prettyprint=True)
                tmp.flush()

            # Read back the content as text
            with open(tmp.name, 'r', encoding='utf-8') as f:
                graphml_content = f.read()
            os.unlink(tmp.name)
            return graphml_content

    except Exception as e:
        raise HTTPException(
            status_code=400, detail=f"Error converting network to GraphML: {str(e)}")


@router.post("/calculate-centrality-direct")
async def calculate_centrality_direct(
    request: CentralityRequest,
    current_user: models.User = Depends(get_current_active_user)
):
    """
    Calculate centrality using the frontend network data directly.
    This bypasses the database storage and works with the current frontend network.
    """
    try:
        # Convert frontend network to GraphML
        graphml_content = convert_frontend_network_to_graphml(
            request.network.nodes,
            request.network.edges
        )

        print(
            f"🔄 Direct centrality calculation requested for {len(request.network.nodes)} nodes, {len(request.network.edges)} edges")

        # Stage 1: Calculate and store centrality
        stage1_payload = {
            "graphml_content": graphml_content,
            "centrality_type": request.centrality_type
        }

        async with httpx.AsyncClient() as client:
            # Call NetworkX MCP for centrality calculation
            stage1_url = f"{NETWORKX_MCP_URL}/tools/calculate_and_store_centrality"
            response = await client.post(stage1_url, json=stage1_payload, timeout=60.0)

            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Stage 1 failed: {response.text}"
                )

            response_data = response.json()
            stage1_result = response_data.get("result", {})
            if not stage1_result.get("success"):
                raise HTTPException(
                    status_code=400,
                    detail=f"Stage 1 failed: {stage1_result.get('error')}"
                )

            calculation_id = stage1_result.get("calculation_id")
            centrality_type = stage1_result.get("centrality_type")
            
            # calculation_idが取得できない場合のエラーハンドリング
            if not calculation_id:
                print(f"❌ calculation_id is null. Stage 1 response: {response_data}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Stage 1 did not return valid calculation_id. Response: {stage1_result}"
                )

            print(f"✅ Stage 1 completed. Calculation ID: {calculation_id}")

            # Stage 2: Get visualization data
            stage2_payload = {
                "calculation_id": calculation_id,
                "color_scheme": request.color_scheme,
                "size_range": request.size_range
            }

            stage2_url = f"{NETWORKX_MCP_URL}/tools/get_centrality_visualization"
            viz_response = await client.post(stage2_url, json=stage2_payload, timeout=60.0)

            if viz_response.status_code != 200:
                raise HTTPException(
                    status_code=viz_response.status_code,
                    detail=f"Stage 2 failed: {viz_response.text}"
                )

            viz_response_data = viz_response.json()
            stage2_result = viz_response_data.get("result", {})
            if not stage2_result.get("success"):
                raise HTTPException(
                    status_code=400,
                    detail=f"Stage 2 failed: {stage2_result.get('error')}"
                )

            visualization_data = stage2_result.get("visualization_data", {})
            
            # visualization_dataが空の場合のエラーハンドリング
            if not visualization_data:
                print(f"❌ visualization_data is empty. Stage 2 response: {viz_response_data}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Stage 2 did not return visualization data. Response: {stage2_result}"
                )

            print(
                f"✅ Stage 2 completed. Generated visualization data for {len(visualization_data)} nodes")

            return {
                "success": True,
                "centrality_type": centrality_type,
                "calculation_id": calculation_id,
                "visualization_data": visualization_data,
                "metadata": stage2_result.get("metadata", {}),
                "node_statistics": stage2_result.get("node_statistics", {}),
                "message": f"{centrality_type.capitalize()} centrality visualization completed successfully! Nodes are now sized and colored by their centrality values."
            }

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error in direct centrality calculation: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Internal error: {str(e)}")


# テスト用の認証不要エンドポイント
@router.post("/test-centrality-direct")
async def test_centrality_direct(request: CentralityRequest):
    """
    テスト用の認証不要の中心性計算エンドポイント
    """
    try:
        # Convert frontend network to GraphML
        graphml_content = convert_frontend_network_to_graphml(
            request.network.nodes,
            request.network.edges
        )

        print(
            f"🔄 TEST: Direct centrality calculation for {len(request.network.nodes)} nodes, {len(request.network.edges)} edges")

        # Stage 1: Calculate and store centrality
        stage1_payload = {
            "graphml_content": graphml_content,
            "centrality_type": request.centrality_type
        }

        async with httpx.AsyncClient() as client:
            # Call NetworkX MCP for centrality calculation
            stage1_url = f"{NETWORKX_MCP_URL}/tools/calculate_and_store_centrality"
            response = await client.post(stage1_url, json=stage1_payload, timeout=60.0)

            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Stage 1 failed: {response.text}"
                )

            response_data = response.json()
            stage1_result = response_data.get("result", {})
            if not stage1_result.get("success"):
                raise HTTPException(
                    status_code=400,
                    detail=f"Stage 1 failed: {stage1_result.get('error')}"
                )

            calculation_id = stage1_result.get("calculation_id")
            centrality_type = stage1_result.get("centrality_type")
            
            # calculation_idが取得できない場合のエラーハンドリング
            if not calculation_id:
                print(f"❌ calculation_id is null. Stage 1 response: {response_data}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Stage 1 did not return valid calculation_id. Response: {stage1_result}"
                )

            print(f"✅ TEST Stage 1 completed. Calculation ID: {calculation_id}")

            # Stage 2: Get visualization data
            stage2_payload = {
                "calculation_id": calculation_id,
                "color_scheme": request.color_scheme,
                "size_range": request.size_range
            }

            stage2_url = f"{NETWORKX_MCP_URL}/tools/get_centrality_visualization"
            viz_response = await client.post(stage2_url, json=stage2_payload, timeout=60.0)

            if viz_response.status_code != 200:
                raise HTTPException(
                    status_code=viz_response.status_code,
                    detail=f"Stage 2 failed: {viz_response.text}"
                )

            viz_response_data = viz_response.json()
            stage2_result = viz_response_data.get("result", {})
            if not stage2_result.get("success"):
                raise HTTPException(
                    status_code=400,
                    detail=f"Stage 2 failed: {stage2_result.get('error')}"
                )

            visualization_data = stage2_result.get("visualization_data", {})
            
            # visualization_dataが空の場合のエラーハンドリング
            if not visualization_data:
                print(f"❌ visualization_data is empty. Stage 2 response: {viz_response_data}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Stage 2 did not return visualization data. Response: {stage2_result}"
                )

            print(
                f"✅ TEST Stage 2 completed. Generated visualization data for {len(visualization_data)} nodes")

            return {
                "success": True,
                "centrality_type": centrality_type,
                "calculation_id": calculation_id,
                "visualization_data": visualization_data,
                "metadata": stage2_result.get("metadata", {}),
                "node_statistics": stage2_result.get("node_statistics", {}),
                "message": f"TEST: {centrality_type.capitalize()} centrality visualization completed successfully! Nodes are now sized and colored by their centrality values."
            }

    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ TEST Error in direct centrality calculation: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"TEST Internal error: {str(e)}")
