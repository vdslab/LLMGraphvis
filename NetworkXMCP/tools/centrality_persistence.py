"""
Centrality calculation and persistence tools module
=================================================

Provides centrality calculation tools that integrate with the new MCP architecture.
Supports two-stage process (calculation and visualization) with persistent storage.
"""

import logging
import json
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, List

try:
    import networkx as nx
    NETWORKX_AVAILABLE = True
except ImportError:
    NETWORKX_AVAILABLE = False
    nx = None

try:
    from mcp.server.fastmcp import FastMCP, Context
    from mcp.server.session import ServerSession
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False

    class FastMCP:
        def tool(self):
            def decorator(func):
                return func
            return decorator

    class Context:
        pass

    class ServerSession:
        pass

from core.context import ServerContext
from core.graph_utils import parse_graphml_content

logger = logging.getLogger("networkx_mcp.tools.centrality_persistence")

# 中心性計算結果のキャッシュ
centrality_cache = {}


class CentralityCalculationResult:
    """中心性計算結果を保持するクラス"""

    def __init__(self, calculation_id: str, graph_id: str, centrality_type: str,
                 centrality_values: Dict[str, float], metadata: Optional[Dict[str, Any]] = None):
        self.calculation_id = calculation_id
        self.graph_id = graph_id
        self.centrality_type = centrality_type
        self.centrality_values = centrality_values
        self.metadata = metadata or {}
        self.timestamp = datetime.now().isoformat()
        self.status = "completed"

    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換"""
        return {
            "calculation_id": self.calculation_id,
            "graph_id": self.graph_id,
            "centrality_type": self.centrality_type,
            "centrality_values": self.centrality_values,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
            "status": self.status
        }


def calculate_and_store_centrality(graphml_content: str, centrality_type: str = "degree",
                                   centrality_params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    中心性を計算し、結果を永続化する（1段階目）

    Args:
        graphml_content (str): GraphML文字列
        centrality_type (str): 中心性の種類
        centrality_params (dict): 中心性計算のパラメータ

    Returns:
        dict: 計算結果と計算ID
    """
    try:
        if centrality_params is None:
            centrality_params = {}

        logger.info(f"Starting centrality calculation: {centrality_type}")

        # GraphMLからグラフを構築
        import io
        from tools.network_tools import parse_graphml_string
        content_io = io.BytesIO(graphml_content.encode('utf-8'))

        try:
            import networkx as nx
            G = nx.read_graphml(content_io)
        except ImportError:
            return {
                "success": False,
                "error": "NetworkX not available for graph processing"
            }

        if G.number_of_nodes() == 0:
            return {
                "success": False,
                "error": "Graph has no nodes"
            }

        # 中心性計算関数を取得
        try:
            from metrics.centrality_functions import get_centrality_function
            centrality_func = get_centrality_function(centrality_type)
        except ImportError:
            return {
                "success": False,
                "error": "Centrality functions not available"
            }

        # 中心性を計算
        logger.info(
            f"Calculating {centrality_type} centrality for {G.number_of_nodes()} nodes")

        if centrality_type == "degree":
            centrality_values = centrality_func(G)
        elif centrality_type == "betweenness":
            centrality_values = centrality_func(G, **centrality_params)
        elif centrality_type == "eigenvector":
            centrality_values = centrality_func(G, **centrality_params)
        else:
            centrality_values = centrality_func(G, **centrality_params)

        # 結果を正規化
        max_value = max(centrality_values.values()
                        ) if centrality_values else 1.0
        if max_value > 0:
            normalized_centrality = {
                str(k): v / max_value for k, v in centrality_values.items()}
        else:
            normalized_centrality = {
                str(k): 0.0 for k in centrality_values.keys()}

        # 計算IDを生成
        calculation_id = str(uuid.uuid4())

        # グラフIDを生成（GraphMLのハッシュベース）
        import hashlib
        graph_id = hashlib.md5(graphml_content.encode()).hexdigest()[:12]

        # メタデータを収集
        metadata = {
            "num_nodes": G.number_of_nodes(),
            "num_edges": G.number_of_edges(),
            "calculation_params": centrality_params,
            "max_value": max_value,
            "min_value": min(centrality_values.values()) if centrality_values else 0.0,
            "mean_value": sum(centrality_values.values()) / len(centrality_values) if centrality_values else 0.0
        }

        # 結果を保存
        result = CentralityCalculationResult(
            calculation_id=calculation_id,
            graph_id=graph_id,
            centrality_type=centrality_type,
            centrality_values=normalized_centrality,
            metadata=metadata
        )

        # キャッシュに保存
        centrality_cache[calculation_id] = result
        logger.info(
            f"Centrality calculation completed and stored with ID: {calculation_id}")

        return {
            "success": True,
            "calculation_id": calculation_id,
            "graph_id": graph_id,
            "centrality_type": centrality_type,
            "status": "calculation_completed",
            "metadata": {
                "num_nodes": metadata["num_nodes"],
                "num_edges": metadata["num_edges"],
                "max_centrality": metadata["max_value"],
                "min_centrality": metadata["min_value"],
                "mean_centrality": metadata["mean_value"]
            },
            "message": f"{centrality_type.title()} centrality calculation completed for {metadata['num_nodes']} nodes"
        }

    except Exception as e:
        logger.error(f"Error calculating centrality: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            "success": False,
            "error": f"Error calculating centrality: {str(e)}"
        }


def get_centrality_visualization_data(calculation_id: str,
                                      color_scheme: str = "viridis",
                                      size_range: tuple = (5, 20)) -> Dict[str, Any]:
    """
    保存された中心性データから可視化データを生成する（2段階目）

    Args:
        calculation_id (str): 計算ID
        color_scheme (str): カラースキーム
        size_range (tuple): ノードサイズの範囲

    Returns:
        dict: 可視化データ
    """
    try:
        # キャッシュから結果を取得
        if calculation_id not in centrality_cache:
            return {
                "success": False,
                "error": f"Calculation ID {calculation_id} not found"
            }

        result = centrality_cache[calculation_id]
        centrality_values = result.centrality_values

        logger.info(
            f"Generating visualization data for calculation {calculation_id}")

        # カラーマップを生成
        color_map = generate_color_map(centrality_values, color_scheme)

        # サイズマップを生成
        size_map = generate_size_map(centrality_values, size_range)

        # 可視化データを構築
        visualization_data = {}
        for node_id, centrality_value in centrality_values.items():
            visualization_data[node_id] = {
                "centrality_value": centrality_value,
                "color": color_map[node_id],
                "size": size_map[node_id],
                "normalized_value": centrality_value  # 既に正規化済み
            }

        return {
            "success": True,
            "calculation_id": calculation_id,
            "centrality_type": result.centrality_type,
            "visualization_data": visualization_data,
            "metadata": {
                **result.metadata,
                "color_scheme": color_scheme,
                "size_range": size_range,
                "timestamp": result.timestamp
            },
            "message": f"Visualization data generated for {len(visualization_data)} nodes"
        }

    except Exception as e:
        logger.error(f"Error generating visualization data: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            "success": False,
            "error": f"Error generating visualization data: {str(e)}"
        }


def generate_color_map(centrality_values: Dict[str, float],
                       color_scheme: str = "viridis") -> Dict[str, str]:
    """
    中心性値に基づいてカラーマップを生成する

    Args:
        centrality_values (dict): 中心性値
        color_scheme (str): カラースキーム

    Returns:
        dict: ノードIDをキー、色を値とする辞書
    """
    try:
        # シンプルな色分けロジックを使用
        color_map = {}
        for node_id, value in centrality_values.items():
            if value > 0.8:
                color_map[node_id] = "#ff0000"  # 赤: 高い中心性
            elif value > 0.6:
                color_map[node_id] = "#ff8000"  # オレンジ
            elif value > 0.4:
                color_map[node_id] = "#ffff00"  # 黄色
            elif value > 0.2:
                color_map[node_id] = "#80ff80"  # 薄緑
            else:
                color_map[node_id] = "#0080ff"  # 青: 低い中心性

        return color_map

    except Exception as e:
        logger.warning(
            f"Error generating color map: {e}, using default colors")
        # フォールバック: デフォルト色
        color_map = {}
        for node_id in centrality_values.keys():
            color_map[node_id] = "#1d4ed8"  # デフォルト青色

        return color_map


def generate_size_map(centrality_values: Dict[str, float],
                      size_range: tuple = (5, 20)) -> Dict[str, float]:
    """
    中心性値に基づいてサイズマップを生成する

    Args:
        centrality_values (dict): 中心性値
        size_range (tuple): サイズの範囲 (min, max)

    Returns:
        dict: ノードIDをキー、サイズを値とする辞書
    """
    min_size, max_size = size_range
    size_range_span = max_size - min_size

    size_map = {}
    for node_id, value in centrality_values.items():
        # 正規化された値をサイズに変換
        size = min_size + (value * size_range_span)
        size_map[node_id] = size

    return size_map


def list_stored_calculations() -> Dict[str, Any]:
    """
    保存されている計算結果のリストを取得する

    Returns:
        dict: 計算結果のリスト
    """
    try:
        calculations = []
        for calc_id, result in centrality_cache.items():
            calculations.append({
                "calculation_id": calc_id,
                "graph_id": result.graph_id,
                "centrality_type": result.centrality_type,
                "timestamp": result.timestamp,
                "num_nodes": result.metadata.get("num_nodes", 0),
                "status": result.status
            })

        return {
            "success": True,
            "calculations": calculations,
            "total_count": len(calculations)
        }

    except Exception as e:
        logger.error(f"Error listing calculations: {e}")
        return {
            "success": False,
            "error": f"Error listing calculations: {str(e)}"
        }


def delete_calculation(calculation_id: str) -> Dict[str, Any]:
    """
    保存された計算結果を削除する

    Args:
        calculation_id (str): 計算ID

    Returns:
        dict: 削除結果
    """
    try:
        if calculation_id not in centrality_cache:
            return {
                "success": False,
                "error": f"Calculation ID {calculation_id} not found"
            }

        del centrality_cache[calculation_id]
        logger.info(f"Deleted calculation {calculation_id}")

        return {
            "success": True,
            "message": f"Calculation {calculation_id} deleted successfully"
        }

    except Exception as e:
        logger.error(f"Error deleting calculation: {e}")
        return {
            "success": False,
            "error": f"Error deleting calculation: {str(e)}"
        }


def get_calculation_status(calculation_id: str) -> Dict[str, Any]:
    """
    計算の状態を取得する

    Args:
        calculation_id (str): 計算ID

    Returns:
        dict: 計算状態
    """
    try:
        if calculation_id not in centrality_cache:
            return {
                "success": False,
                "error": f"Calculation ID {calculation_id} not found"
            }

        result = centrality_cache[calculation_id]

        return {
            "success": True,
            "calculation_id": calculation_id,
            "status": result.status,
            "centrality_type": result.centrality_type,
            "timestamp": result.timestamp,
            "metadata": result.metadata
        }

    except Exception as e:
        logger.error(f"Error getting calculation status: {e}")
        return {
            "success": False,
            "error": f"Error getting calculation status: {str(e)}"
        }
