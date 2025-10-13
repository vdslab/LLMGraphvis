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
    中心性を計算し、結果を永続化する（1段階目）- Enhanced with progress reporting

    Args:
        graphml_content (str): GraphML文字列
        centrality_type (str): 中心性の種類 (degree, betweenness, closeness, eigenvector)
        centrality_params (dict): 中心性計算のパラメータ

    Returns:
        dict: 計算結果と計算ID
    """
    try:
        if centrality_params is None:
            centrality_params = {}

        logger.info(
            f"🔄 Starting enhanced centrality calculation: {centrality_type}")

        # Validate centrality type
        valid_types = ["degree", "betweenness",
                       "closeness", "eigenvector", "pagerank", "katz"]
        if centrality_type not in valid_types:
            return {
                "success": False,
                "error": f"Invalid centrality type '{centrality_type}'. Valid types: {valid_types}"
            }

        # GraphMLからグラフを構築
        import io
        content_io = io.BytesIO(graphml_content.encode('utf-8'))

        try:
            if not NETWORKX_AVAILABLE:
                return {
                    "success": False,
                    "error": "NetworkX not available for graph processing"
                }

            G = nx.read_graphml(content_io)
            logger.info(
                f"📊 Graph loaded: {G.number_of_nodes()} nodes, {G.number_of_edges()} edges")
        except ImportError:
            return {
                "success": False,
                "error": "NetworkX not available for graph processing"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to parse GraphML: {str(e)}"
            }

        if G.number_of_nodes() == 0:
            return {
                "success": False,
                "error": "Graph has no nodes"
            }

        # Enhanced centrality calculation with proper error handling
        logger.info(
            f"🧮 Calculating {centrality_type} centrality for {G.number_of_nodes()} nodes")

        centrality_values = {}
        try:
            if centrality_type == "degree":
                centrality_values = nx.degree_centrality(G)  # type: ignore
            elif centrality_type == "betweenness":
                # Add normalized parameter for betweenness
                centrality_values = nx.betweenness_centrality(
                    G, normalized=True, **centrality_params)  # type: ignore
            elif centrality_type == "closeness":
                centrality_values = nx.closeness_centrality(
                    G, **centrality_params)  # type: ignore
            elif centrality_type == "eigenvector":
                # Handle potential convergence issues
                try:
                    max_iter = centrality_params.get('max_iter', 1000)
                    centrality_values = nx.eigenvector_centrality(
                        # type: ignore
                        G, max_iter=max_iter, **{k: v for k, v in centrality_params.items() if k != 'max_iter'})
                except Exception:  # Catch any convergence errors
                    logger.warning(
                        "Eigenvector centrality failed to converge, using degree centrality as fallback")
                    centrality_values = nx.degree_centrality(G)  # type: ignore
                    centrality_type = "degree"  # Update type for accurate reporting
            elif centrality_type == "pagerank":
                centrality_values = nx.pagerank(
                    G, **centrality_params)  # type: ignore
            elif centrality_type == "katz":
                try:
                    centrality_values = nx.katz_centrality(
                        G, **centrality_params)  # type: ignore
                except Exception as e:
                    logger.warning(
                        f"Katz centrality failed: {e}, using degree centrality as fallback")
                    centrality_values = nx.degree_centrality(G)  # type: ignore
                    centrality_type = "degree"

            logger.info(
                f"✅ {centrality_type.title()} centrality calculation completed")

        except Exception as calc_error:
            logger.error(f"Centrality calculation failed: {calc_error}")
            return {
                "success": False,
                "error": f"Centrality calculation failed: {str(calc_error)}"
            }

        if not centrality_values:
            return {
                "success": False,
                "error": "Centrality calculation returned no values"
            }

        # Enhanced normalization with statistical information
        values_list = list(centrality_values.values())
        max_value = max(values_list)
        min_value = min(values_list)
        mean_value = sum(values_list) / len(values_list)

        # Normalize to [0, 1] range
        if max_value > min_value:
            normalized_centrality = {
                str(k): (v - min_value) / (max_value - min_value)
                for k, v in centrality_values.items()
            }
        else:
            # All values are the same
            normalized_centrality = {
                str(k): 0.5 for k in centrality_values.keys()}

        # 計算IDを生成
        calculation_id = str(uuid.uuid4())

        # グラフIDを生成（GraphMLのハッシュベース）
        import hashlib
        graph_id = hashlib.md5(graphml_content.encode()).hexdigest()[:12]

        # Enhanced metadata collection
        metadata = {
            "num_nodes": G.number_of_nodes(),
            "num_edges": G.number_of_edges(),
            "calculation_params": centrality_params,
            "original_values": {
                "max_value": max_value,
                "min_value": min_value,
                "mean_value": mean_value
            },
            "graph_properties": {
                # type: ignore
                "is_connected": nx.is_connected(G) if NETWORKX_AVAILABLE else False,
                # type: ignore
                "density": nx.density(G) if NETWORKX_AVAILABLE else 0.0,
                # type: ignore
                "number_of_components": nx.number_connected_components(G) if NETWORKX_AVAILABLE else 1
            },
            "calculation_timestamp": datetime.now().isoformat()
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
            f"💾 Centrality calculation completed and stored with ID: {calculation_id}")

        return {
            "success": True,
            "calculation_id": calculation_id,
            "graph_id": graph_id,
            "centrality_type": centrality_type,
            "status": "calculation_completed",
            "metadata": {
                "num_nodes": metadata["num_nodes"],
                "num_edges": metadata["num_edges"],
                "max_centrality": metadata["original_values"]["max_value"],
                "min_centrality": metadata["original_values"]["min_value"],
                "mean_centrality": metadata["original_values"]["mean_value"],
                "graph_density": metadata["graph_properties"]["density"],
                "is_connected": metadata["graph_properties"]["is_connected"]
            },
            "message": f"✅ {centrality_type.title()} centrality calculation completed for {metadata['num_nodes']} nodes"
        }

    except Exception as e:
        logger.error(f"❌ Error calculating centrality: {e}")
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
    保存された中心性データから可視化データを生成する（2段階目）- Enhanced with better color mapping

    Args:
        calculation_id (str): 計算ID
        color_scheme (str): カラースキーム (viridis, plasma, inferno, magma, simple)
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
            f"🎨 Generating enhanced visualization data for calculation {calculation_id}")

        # Enhanced color mapping
        color_map = generate_enhanced_color_map(
            centrality_values, color_scheme)

        # Enhanced size mapping with smoother scaling
        size_map = generate_enhanced_size_map(centrality_values, size_range)

        # Build comprehensive visualization data
        visualization_data = {}
        node_statistics = {
            "high_centrality_nodes": [],
            "medium_centrality_nodes": [],
            "low_centrality_nodes": []
        }

        for node_id, centrality_value in centrality_values.items():
            # Categorize nodes by centrality for analysis
            if centrality_value > 0.8:
                node_statistics["high_centrality_nodes"].append(node_id)
            elif centrality_value > 0.3:
                node_statistics["medium_centrality_nodes"].append(node_id)
            else:
                node_statistics["low_centrality_nodes"].append(node_id)

            visualization_data[node_id] = {
                "centrality_value": centrality_value,
                "color": color_map[node_id],
                "size": size_map[node_id],
                "normalized_value": centrality_value,  # 既に正規化済み
                "importance_level": get_importance_level(centrality_value),
                "percentile": get_percentile_rank(centrality_value, list(centrality_values.values()))
            }

        # Enhanced metadata with visualization insights
        enhanced_metadata = {
            **result.metadata,
            "color_scheme": color_scheme,
            "size_range": size_range,
            "timestamp": result.timestamp,
            "visualization_insights": {
                "most_central_node": max(centrality_values.keys(), key=lambda k: centrality_values[k]),
                "least_central_node": min(centrality_values.keys(), key=lambda k: centrality_values[k]),
                "high_centrality_count": len(node_statistics["high_centrality_nodes"]),
                "medium_centrality_count": len(node_statistics["medium_centrality_nodes"]),
                "low_centrality_count": len(node_statistics["low_centrality_nodes"])
            }
        }

        return {
            "success": True,
            "calculation_id": calculation_id,
            "centrality_type": result.centrality_type,
            "visualization_data": visualization_data,
            "node_statistics": node_statistics,
            "metadata": enhanced_metadata,
            "message": f"🎨 Enhanced visualization data generated for {len(visualization_data)} nodes with {color_scheme} color scheme"
        }

    except Exception as e:
        logger.error(f"❌ Error generating visualization data: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            "success": False,
            "error": f"Error generating visualization data: {str(e)}"
        }


def generate_enhanced_color_map(centrality_values: Dict[str, float],
                                color_scheme: str = "viridis") -> Dict[str, str]:
    """
    Enhanced color mapping with multiple color schemes

    Args:
        centrality_values (dict): 中心性値
        color_scheme (str): カラースキーム

    Returns:
        dict: ノードIDをキー、色を値とする辞書
    """
    try:
        color_map = {}

        # Define color schemes
        color_schemes = {
            "viridis": ["#440154", "#31688e", "#35b779", "#fde725"],
            "plasma": ["#0d0887", "#7e03a8", "#cc4778", "#f89441", "#f0f921"],
            "inferno": ["#000004", "#420a68", "#932667", "#dd513a", "#fca50a", "#fcffa4"],
            "magma": ["#000004", "#2c105c", "#711f81", "#b63679", "#ee605e", "#fdae78", "#fcfdbf"],
            "simple": ["#0080ff", "#80ff80", "#ffff00", "#ff8000", "#ff0000"],
            "blue_red": ["#0066cc", "#3399ff", "#66ccff", "#ffcc66", "#ff9933", "#cc0000"],
            "cool_warm": ["#3690c0", "#7fcdbb", "#c7e9b4", "#ffeda0", "#fd8d3c", "#e31a1c"]
        }

        colors = color_schemes.get(color_scheme, color_schemes["simple"])
        num_colors = len(colors)

        for node_id, value in centrality_values.items():
            # Map value to color index
            if value == 1.0:
                color_index = num_colors - 1
            else:
                color_index = int(value * num_colors)
                color_index = min(color_index, num_colors - 1)

            color_map[node_id] = colors[color_index]

        return color_map

    except Exception as e:
        logger.warning(
            f"Error generating enhanced color map: {e}, using fallback colors")
        # Fallback: simple color mapping
        return {node_id: "#1d4ed8" for node_id in centrality_values.keys()}


def generate_enhanced_size_map(centrality_values: Dict[str, float],
                               size_range: tuple = (5, 20)) -> Dict[str, float]:
    """
    Enhanced size mapping with smooth scaling and better visual distinction for centrality values

    Args:
        centrality_values (dict): 中心性値 (normalized between 0-1)
        size_range (tuple): サイズの範囲 (min, max)

    Returns:
        dict: ノードIDをキー、サイズを値とする辞書
    """
    import math

    min_size, max_size = size_range

    if not centrality_values:
        return {}

    # Get all centrality values for better scaling
    values = list(centrality_values.values())
    min_centrality = min(values)
    max_centrality = max(values)

    size_map = {}

    # If all values are the same, use average size
    if min_centrality == max_centrality:
        avg_size = (min_size + max_size) / 2
        for node_id in centrality_values.keys():
            size_map[node_id] = avg_size
        return size_map

    # Enhanced mapping with better scaling for visual distinction
    for node_id, value in centrality_values.items():
        # Normalize to 0-1 range within the actual data range
        normalized_value = (value - min_centrality) / \
            (max_centrality - min_centrality)

        # Apply enhanced scaling for better visual perception
        if normalized_value > 0:
            # Use a combination of linear and square root scaling for better distinction
            # This gives more pronounced differences between high and low centrality nodes
            scaled_value = 0.3 * normalized_value + \
                0.7 * math.sqrt(normalized_value)
        else:
            scaled_value = 0

        # Map to size range with ensured minimum
        size = min_size + (scaled_value * (max_size - min_size))
        size_map[node_id] = max(min_size, round(
            size, 1))  # Round to 1 decimal place

    logger.info(f"🎯 Enhanced size mapping: min={min_size}, max={max_size}, "
                f"centrality_range=[{min_centrality:.3f}, {max_centrality:.3f}], "
                f"size_range=[{min([size_map[k] for k in size_map]):.1f}, "
                f"{max([size_map[k] for k in size_map]):.1f}]")

    return size_map


def get_importance_level(centrality_value: float) -> str:
    """Get importance level based on centrality value"""
    if centrality_value > 0.8:
        return "very_high"
    elif centrality_value > 0.6:
        return "high"
    elif centrality_value > 0.4:
        return "medium"
    elif centrality_value > 0.2:
        return "low"
    else:
        return "very_low"


def get_percentile_rank(value: float, all_values: List[float]) -> float:
    """Calculate percentile rank of a value"""
    sorted_values = sorted(all_values)
    rank = sorted_values.index(value) + 1
    return (rank / len(sorted_values)) * 100


def generate_color_map(centrality_values: Dict[str, float],
                       color_scheme: str = "viridis") -> Dict[str, str]:
    """
    Legacy color mapping function - kept for backward compatibility
    """
    return generate_enhanced_color_map(centrality_values, color_scheme)


def generate_size_map(centrality_values: Dict[str, float],
                      size_range: tuple = (5, 20)) -> Dict[str, float]:
    """
    Legacy size mapping function - kept for backward compatibility
    """
    return generate_enhanced_size_map(centrality_values, size_range)


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
