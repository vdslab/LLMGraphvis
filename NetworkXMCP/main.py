"""
NetworkX MCP Server (FastMCP with OpenAPI)
==========================================

FastMCP Model Context Protocol (MCP) サーバー
ネットワーク分析と可視化のためのAPIを自動的にMCPツールとして公開します。
OpenAPI仕様からMCPツールを自動生成し、NetworkXを使用したグラフ分析を行います。
"""

import os
import logging
import networkx as nx
import numpy as np
from typing import Dict, Any, List, Optional, Union
from fastapi import FastAPI, Depends, HTTPException, Body, Request, Header
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import random
import json
import base64
import io
from datetime import datetime
import httpx
from fastmcp import FastMCP

# ロギングの設定
log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("networkx_mcp")

# FastAPIアプリケーションの作成
app = FastAPI(
    title="NetworkX MCP (FastMCP with OpenAPI)",
    description="FastMCP-based MCP server for network analysis and visualization using NetworkX with OpenAPI integration",
    version="0.3.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# CORSミドルウェアの設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

# 新しい分析ツール用のPydanticモデル


class CalculateMetricsParams(BaseModel):
    graphml_content: str = Field(...,
                                 description="GraphML content to analyze.")
    layout_type: str = Field(
        "spring", description="Layout algorithm to apply.")
    layout_params: Dict[str, Any] = Field({}, description="Layout parameters.")
    metrics_to_calculate: Optional[List[str]] = Field(
        None, description="List of metrics to calculate. If None, all metrics are calculated.")


class VisualizationParams(BaseModel):
    graph_id: str = Field(..., description="ID of the cached graph.")
    metric_name: str = Field(...,
                             description="Name of the metric to visualize.")
    color_scheme: str = Field(
        "viridis", description="Color scheme for visualization.")
    size_range: Optional[List[float]] = Field(
        None, description="Node size range [min, max].")


class CentralityCalculationParams(BaseModel):
    graphml_content: str = Field(...,
                                 description="GraphML content to analyze.")
    centrality_type: str = Field(
        "degree", description="Type of centrality to calculate.")
    centrality_params: Dict[str, Any] = Field(
        {}, description="Parameters for centrality calculation.")


class CentralityVisualizationParams(BaseModel):
    calculation_id: str = Field(...,
                                description="ID of the centrality calculation.")
    color_scheme: str = Field(
        "viridis", description="Color scheme for visualization.")
    size_range: List[float] = Field(
        [5, 20], description="Node size range [min, max].")


class CalculationIdParams(BaseModel):
    calculation_id: str = Field(...,
                                description="ID of the centrality calculation.")


class GraphIdParams(BaseModel):
    graph_id: str = Field(..., description="ID of the cached graph.")

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
        "fruchterman_reingold": nx.fruchterman_reingold_layout,
        "planar": nx.planar_layout,
        "spiral": nx.spiral_layout
    }

    # カスタムレイアウトの処理
    if layout_type == "grid":
        from layouts.layout_functions import calculate_grid_layout
        positions = calculate_grid_layout(G, **kwargs)
    elif layout_type == "tree":
        from layouts.layout_functions import calculate_tree_layout
        positions = calculate_tree_layout(G, **kwargs)
    elif layout_type == "radial":
        from layouts.layout_functions import calculate_radial_layout
        positions = calculate_radial_layout(G, **kwargs)
    elif layout_type == "multipartite":
        from layouts.layout_functions import calculate_multipartite_layout
        positions = calculate_multipartite_layout(G, **kwargs)
    elif layout_type == "bipartite":
        from layouts.layout_functions import calculate_bipartite_layout
        # bipartiteレイアウトは特別な処理が必要
        node_list = list(G.nodes())
        nodes = kwargs.get('nodes', node_list[:len(node_list)//2])
        positions = calculate_bipartite_layout(
            G, nodes, **{k: v for k, v in kwargs.items() if k != 'nodes'})
    else:
        # 既存のNetworkXレイアウト
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
        "name": "NetworkX MCP (FastMCP with OpenAPI)",
        "version": "0.3.0",
        "description": "FastMCP-based NetworkX graph analysis and visualization MCP server with OpenAPI integration",
        "tools": [
            {"name": "get_sample_network",
                "description": "Get a sample network in GraphML format"},
            {"name": "change_layout",
                "description": "Change the layout algorithm for a given network"},
            {"name": "calculate_centrality",
                "description": "Calculate centrality metrics for a given network"},
            {"name": "calculate_and_store_centrality",
                "description": "Calculate centrality and store results (Stage 1)"},
            {"name": "get_centrality_visualization",
                "description": "Get visualization data from stored centrality (Stage 2)"},
            {"name": "list_centrality_calculations",
                "description": "List all stored centrality calculations"},
            {"name": "get_centrality_status",
                "description": "Get status of a centrality calculation"},
            {"name": "calculate_and_store_metrics",
                "description": "Calculate all metrics and store graph in cache"},
            {"name": "get_visualization_data",
                "description": "Get visualization data for a specific metric"},
            {"name": "get_available_metrics",
                "description": "Get list of available metrics for a cached graph"}
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


@app.post("/tools/calculate_and_store_metrics", response_model=Dict[str, Any])
async def api_calculate_and_store_metrics(params: CalculateMetricsParams):
    """
    GraphMLからグラフを読み込み、レイアウトと指標を計算してキャッシュに保存する
    """
    try:
        from tools.analysis_tools import calculate_and_store_metrics

        result = calculate_and_store_metrics(
            graphml_content=params.graphml_content,
            layout_type=params.layout_type,
            layout_params=params.layout_params,
            metrics_to_calculate=params.metrics_to_calculate
        )

        if not result["success"]:
            error_msg = result.get(
                "error", "Unknown error during metrics calculation")
            logger.error(f"API: Metrics calculation failed: {error_msg}")
            raise HTTPException(status_code=400, detail=error_msg)

        return {"result": result}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in calculate_and_store_metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/get_visualization_data", response_model=Dict[str, Any])
async def api_get_visualization_data(params: VisualizationParams):
    """
    キャッシュされたグラフから指定された指標に基づく可視化データを取得する
    """
    try:
        from tools.analysis_tools import get_visualization_data

        size_range = tuple(params.size_range) if params.size_range else None

        result = get_visualization_data(
            graph_id=params.graph_id,
            metric_name=params.metric_name,
            color_scheme=params.color_scheme,
            size_range=size_range
        )

        if not result["success"]:
            error_msg = result.get(
                "error", "Unknown error during visualization data generation")
            logger.error(
                f"API: Visualization data generation failed: {error_msg}")
            raise HTTPException(status_code=400, detail=error_msg)

        return {"result": result}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_visualization_data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/get_available_metrics", response_model=Dict[str, Any])
async def api_get_available_metrics(params: GraphIdParams):
    """
    キャッシュされたグラフで利用可能な指標のリストを取得する
    """
    try:
        from tools.analysis_tools import get_available_metrics

        result = get_available_metrics(graph_id=params.graph_id)

        if not result["success"]:
            error_msg = result.get(
                "error", "Unknown error during metrics retrieval")
            logger.error(f"API: Metrics retrieval failed: {error_msg}")
            raise HTTPException(status_code=400, detail=error_msg)

        return {"result": result}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_available_metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/cache/stats", response_model=Dict[str, Any])
async def get_cache_stats():
    """
    キャッシュの統計情報を取得する
    """
    try:
        from tools.graph_cache import get_cache
        cache = get_cache()
        stats = cache.get_stats()

        return {
            "success": True,
            "stats": stats
        }
    except Exception as e:
        logger.error(f"Error getting cache stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/calculate_and_store_centrality", response_model=Dict[str, Any])
async def api_calculate_and_store_centrality(params: CentralityCalculationParams):
    """
    中心性を計算し結果を保存する（1段階目）
    """
    try:
        from tools.centrality_persistence import calculate_and_store_centrality

        result = calculate_and_store_centrality(
            graphml_content=params.graphml_content,
            centrality_type=params.centrality_type,
            centrality_params=params.centrality_params
        )

        if not result["success"]:
            error_msg = result.get(
                "error", "Unknown error during centrality calculation")
            logger.error(f"API: Centrality calculation failed: {error_msg}")
            raise HTTPException(status_code=400, detail=error_msg)

        return {"result": result}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in calculate_and_store_centrality: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/get_centrality_visualization", response_model=Dict[str, Any])
async def api_get_centrality_visualization(params: CentralityVisualizationParams):
    """
    保存された中心性データから可視化データを取得する（2段階目）
    """
    try:
        from tools.centrality_persistence import get_centrality_visualization_data

        size_range = tuple(params.size_range) if params.size_range else (5, 20)

        result = get_centrality_visualization_data(
            calculation_id=params.calculation_id,
            color_scheme=params.color_scheme,
            size_range=size_range
        )

        if not result["success"]:
            error_msg = result.get(
                "error", "Unknown error during visualization data generation")
            logger.error(
                f"API: Visualization data generation failed: {error_msg}")
            raise HTTPException(status_code=400, detail=error_msg)

        return {"result": result}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_centrality_visualization: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/list_centrality_calculations", response_model=Dict[str, Any])
async def api_list_centrality_calculations():
    """
    保存されている中心性計算のリストを取得する
    """
    try:
        from tools.centrality_persistence import list_stored_calculations

        result = list_stored_calculations()

        if not result["success"]:
            error_msg = result.get(
                "error", "Unknown error during calculations listing")
            logger.error(f"API: Calculations listing failed: {error_msg}")
            raise HTTPException(status_code=400, detail=error_msg)

        return {"result": result}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in list_centrality_calculations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/tools/get_centrality_status", response_model=Dict[str, Any])
async def api_get_centrality_status(params: CalculationIdParams):
    """
    中心性計算の状態を取得する
    """
    try:
        from tools.centrality_persistence import get_calculation_status

        result = get_calculation_status(calculation_id=params.calculation_id)

        if not result["success"]:
            error_msg = result.get(
                "error", "Unknown error during status retrieval")
            logger.error(f"API: Status retrieval failed: {error_msg}")
            raise HTTPException(status_code=400, detail=error_msg)

        return {"result": result}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_centrality_status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# FastMCP with OpenAPI integration
async def create_mcp_server():
    """Create FastMCP server from OpenAPI specification"""
    try:
        # サーバーがローカルで動作している場合のベースURL
        base_url = os.environ.get("BASE_URL", "http://localhost:8001")

        # HTTPクライアントを作成
        client = httpx.AsyncClient(base_url=base_url)

        # OpenAPI仕様を取得
        try:
            response = await client.get("/openapi.json")
            openapi_spec = response.json()
        except Exception as e:
            logger.warning(
                f"Could not fetch OpenAPI spec from running server: {e}")
            # サーバーが起動していない場合は、アプリからOpenAPI仕様を生成
            openapi_spec = app.openapi()

        # FastMCPサーバーを作成
        mcp = FastMCP.from_openapi(
            openapi_spec=openapi_spec,
            client=client,
            name="NetworkX MCP (FastMCP)",
            tags={"networkx", "graph-analysis", "visualization"}
        )

        logger.info(
            "FastMCP server created successfully with OpenAPI integration")
        return mcp

    except Exception as e:
        logger.error(f"Error creating FastMCP server: {e}")
        raise


if __name__ == "__main__":
    import uvicorn
    import asyncio

    # FastAPIアプリケーションとFastMCPサーバーを統合
    # まずFastAPIサーバーを起動し、その後OpenAPI仕様からMCPサーバーを作成
    try:
        logger.info(
            "Starting NetworkX MCP Server with FastMCP and OpenAPI integration")
        uvicorn.run(app, host="0.0.0.0", port=8001)
    except Exception as e:
        logger.error(f"Failed to start server: {e}")
        raise
