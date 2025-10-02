"""
NetworkX MCP Server (Stateless)
=================================

FastAPI Model Context Protocol (MCP) サーバー
ネットワーク分析と可視化のためのステートレスなAPIを提供します。
GraphML形式のデータをサポートし、NetworkXを使用したグラフ分析を行います。
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
import base64
import io
from datetime import datetime

# ロギングの設定
log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("networkx_mcp")

# FastAPIアプリケーションの作成
app = FastAPI(
    title="NetworkX MCP (Stateless)",
    description="Stateless MCP server for network analysis and visualization using NetworkX",
    version="0.2.0",
)

# CORSミドルウェアの設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# FastAPI MCPの統合
mcp = FastApiMCP(app)
mcp.mount()  # MCPサーバーを /mcp にマウント

# --- Pydanticモデル定義 ---


class GraphData(BaseModel):
    graphml_content: str = Field(...,
                                 description="GraphML content representing the network.")


class LayoutParams(GraphData):
    layout_type: str = Field(
        "spring", description="The layout algorithm to apply.")
    layout_params: Dict[str, Any] = Field(
        {}, description="Parameters for the layout algorithm.")


class CentralityParams(GraphData):
    centrality_type: str = Field(
        "degree", description="The type of centrality to calculate.")
    centrality_params: Dict[str, Any] = Field(
        {}, description="Parameters for the centrality calculation.")

# GraphMLインポート用のPydanticモデル


class GraphMLImportParams(BaseModel):
    graphml_content: str = Field(..., description="GraphML content to import.")

# GraphML変換用のPydanticモデル


class GraphMLConvertParams(BaseModel):
    graphml_content: str = Field(...,
                                 description="GraphML content to convert.")

# GraphMLエクスポート用のPydanticモデル


class GraphMLExportParams(BaseModel):
    graphml_content: str = Field(..., description="GraphML content to export.")
    include_positions: bool = Field(
        True, description="Include node positions in the exported GraphML.")
    include_visual_properties: bool = Field(
        True, description="Include visual properties in the exported GraphML.")

# --- ヘルパー関数 ---


def parse_graphml_string(graphml_content: str) -> nx.Graph:
    """GraphML文字列をパースしてNetworkXグラフを返す"""
    try:
        # デバッグ情報を記録
        logger.debug(
            f"Parsing GraphML string (length: {len(graphml_content)})")

        content_io = io.BytesIO(graphml_content.encode('utf-8'))
        G = nx.read_graphml(content_io)

        logger.debug(
            f"Successfully parsed GraphML with {G.number_of_nodes()} nodes and {G.number_of_edges()} edges")
        return G
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error parsing GraphML string: {error_msg}")

        # より詳細なエラーメッセージを提供
        if "XML" in error_msg:
            raise HTTPException(
                status_code=400, detail=f"Invalid XML in GraphML content: {error_msg}")
        else:
            raise HTTPException(
                status_code=400, detail=f"Invalid GraphML content: {error_msg}")


def graph_to_cytoscape(G: nx.Graph, positions: Optional[Dict] = None) -> Dict[str, Any]:
    """NetworkXグラフをCytoscape.jsが期待するJSON形式に変換する"""
    nodes = []
    for node, attrs in G.nodes(data=True):
        node_data = {
            "data": {"id": str(node), "label": attrs.get("name", str(node)), **attrs}}
        if positions and str(node) in positions:
            node_data["position"] = positions[str(node)]
        nodes.append(node_data)

    edges = [
        {"data": {"source": str(u), "target": str(v), **attrs}}
        for u, v, attrs in G.edges(data=True)
    ]
    return {"nodes": nodes, "edges": edges}


def apply_layout(G: nx.Graph, layout_type: str, **kwargs) -> Dict:
    """レイアウトアルゴリズムを適用し、ノードの位置を返す"""
    layout_functions = {
        "spring": nx.spring_layout,
        "circular": nx.circular_layout,
        "random": nx.random_layout,
        "spectral": nx.spectral_layout,
        "shell": nx.shell_layout,
        "kamada_kawai": nx.kamada_kawai_layout,
        "fruchterman_reingold": nx.fruchterman_reingold_layout
    }
    layout_func = layout_functions.get(layout_type, nx.spring_layout)
    positions = layout_func(G, **kwargs)
    # JSONシリアライズ可能な形式に変換
    return {str(k): {"x": float(v[0]), "y": float(v[1])} for k, v in positions.items()}

# --- APIエンドポイント ---


@app.get("/health")
async def health_check():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


@app.get("/info")
async def get_mcp_info():
    """MCPサーバーの情報を返す"""
    return {
        "success": True,
        "name": "NetworkX MCP (Stateless)",
        "version": "0.2.0",
        "description": "Stateless NetworkX graph analysis and visualization MCP server",
        "tools": [
            {"name": "get_sample_network",
                "description": "Get a sample network in GraphML format"},
            {"name": "change_layout",
                "description": "Change the layout algorithm for a given network"},
            {"name": "calculate_centrality",
                "description": "Calculate centrality metrics for a given network"}
        ]
    }


@app.get("/get_sample_network", response_model=Dict[str, Any])
async def get_sample_network():
    """サンプルネットワークを生成し、GraphML形式で返す"""
    try:
        num_nodes = random.randint(18, 25)
        edge_probability = random.uniform(0.15, 0.25)
        G = nx.gnp_random_graph(num_nodes, edge_probability)

        if not nx.is_connected(G):
            components = list(nx.connected_components(G))
            largest_component = max(components, key=len)
            for component in components:
                if component != largest_component:
                    node_from = random.choice(list(component))
                    node_to = random.choice(list(largest_component))
                    G.add_edge(node_from, node_to)

        # GraphMLとして出力
        output = io.BytesIO()
        nx.write_graphml(G, output)
        output.seek(0)
        graphml_content = output.read().decode("utf-8")

        return {
            "success": True,
            "graphml_content": graphml_content
        }
    except Exception as e:
        logger.error(f"Error creating sample network: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/change_layout", response_model=Dict[str, Any])
async def api_change_layout(params: LayoutParams):
    """
    与えられたネットワークのレイアウトを計算し、更新されたGraphMLと位置情報を返す
    """
    try:
        from tools.network_tools import apply_layout_to_graphml
        result = apply_layout_to_graphml(
            params.graphml_content,
            params.layout_type,
            params.layout_params
        )

        if not result["success"]:
            error_msg = result.get(
                "error", "Unknown error during layout calculation")
            logger.error(f"API: Layout calculation failed: {error_msg}")
            raise HTTPException(status_code=400, detail=error_msg)

        return {
            "result": {
                "success": True,
                "layout_type": result["layout_type"],
                "positions": result["positions"],
                "graphml_content": result["graphml_content"]
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error changing layout: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/calculate_centrality", response_model=Dict[str, Any])
async def api_calculate_centrality(params: CentralityParams):
    """
    与えられたネットワークの中心性を計算し、各ノードの値を返す
    """
    try:
        G = parse_graphml_string(params.graphml_content)
        # network_toolsからインポートした関数を使用
        from tools.network_tools import calculate_centrality as tools_calculate_centrality
        result = tools_calculate_centrality(
            G, params.centrality_type, **params.centrality_params)

        if not result["success"]:
            error_msg = result.get(
                "error", "Unknown error during centrality calculation")
            logger.error(f"API: Centrality calculation failed: {error_msg}")
            raise HTTPException(status_code=400, detail=error_msg)

        return {
            "result": {
                "success": True,
                "centrality_type": result["centrality_type"],
                "centrality_values": result["centrality"]
            }
        }
    except Exception as e:
        logger.error(f"Error calculating centrality: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/import_graphml", response_model=Dict[str, Any])
async def api_import_graphml(params: GraphMLImportParams):
    """
    GraphML形式からネットワークをインポートする
    """
    try:
        # デバッグ情報を記録
        logger.debug(
            f"API: Importing GraphML content (length: {len(params.graphml_content)})")

        # 名前の衝突を避けるため、tools.network_toolsモジュールから関数をインポートする際に
        # 別名を使用する
        from tools.network_tools import parse_graphml_string as tools_parse_graphml_string
        result = tools_parse_graphml_string(params.graphml_content)

        if not result["success"]:
            error_msg = result.get(
                "error", "Unknown error during GraphML import")
            logger.error(f"API: GraphML import failed: {error_msg}")
            raise HTTPException(status_code=400, detail=error_msg)

        logger.debug(
            f"API: GraphML import successful with {len(result['nodes'])} nodes and {len(result['edges'])} edges")
        return {
            "result": {
                "success": True,
                "nodes": result["nodes"],
                "edges": result["edges"]
            }
        }
    except HTTPException:
        # 既に処理済みのHTTPExceptionはそのまま再スロー
        raise
    except Exception as e:
        error_msg = f"Error importing GraphML: {str(e)}"
        logger.error(f"API: Unexpected error: {error_msg}")
        raise HTTPException(status_code=500, detail=error_msg)


@app.post("/tools/convert_graphml", response_model=Dict[str, Any])
async def api_convert_graphml(params: GraphMLConvertParams):
    """
    GraphMLを標準形式に変換する
    """
    try:
        # デバッグ情報を記録
        logger.debug(
            f"API: Converting GraphML content (length: {len(params.graphml_content)})")

        # 名前の衝突を避けるため、tools.network_toolsモジュールから関数をインポートする際に
        # 別名を使用する
        from tools.network_tools import convert_to_standard_graphml as tools_convert_to_standard_graphml
        result = tools_convert_to_standard_graphml(params.graphml_content)

        if not result["success"]:
            error_msg = result.get(
                "error", "Unknown error during GraphML conversion")
            logger.error(f"API: GraphML conversion failed: {error_msg}")
            raise HTTPException(status_code=400, detail=error_msg)

        logger.debug("API: GraphML conversion successful")
        return {
            "success": True,
            "graphml_content": result["graphml_content"]
        }
    except HTTPException:
        # 既に処理済みのHTTPExceptionはそのまま再スロー
        raise
    except Exception as e:
        error_msg = f"Error converting GraphML: {str(e)}"
        logger.error(f"API: Unexpected error: {error_msg}")
        raise HTTPException(status_code=500, detail=error_msg)


@app.post("/tools/export_graphml", response_model=Dict[str, Any])
async def api_export_graphml(params: GraphMLExportParams):
    """
    ネットワークをGraphML形式でエクスポートする
    """
    try:
        # デバッグ情報を記録
        logger.debug(
            f"API: Exporting GraphML content (length: {len(params.graphml_content)})")

        try:
            G = parse_graphml_string(params.graphml_content)
        except HTTPException as parse_error:
            logger.error(
                f"API: GraphML parse error during export: {parse_error.detail}")
            raise

        from tools.network_tools import export_network_as_graphml
        result = export_network_as_graphml(G, None, None)

        if not result["success"]:
            error_msg = result.get(
                "error", "Unknown error during GraphML export")
            logger.error(f"API: GraphML export failed: {error_msg}")
            raise HTTPException(status_code=400, detail=error_msg)

        logger.debug(f"API: GraphML export successful")
        return {
            "result": {
                "success": True,
                "format": "graphml",
                "content": result["content"]
            }
        }
    except HTTPException:
        # 既に処理済みのHTTPExceptionはそのまま再スロー
        raise
    except Exception as e:
        error_msg = f"Error exporting GraphML: {str(e)}"
        logger.error(f"API: Unexpected error: {error_msg}")
        raise HTTPException(status_code=500, detail=error_msg)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
