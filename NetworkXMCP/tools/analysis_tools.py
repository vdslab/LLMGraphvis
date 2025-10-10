"""
分析ツールモジュール
===================

ネットワーク分析の計算と可視化データ取得のためのツールを提供します。
計算と表示の2段階プロセスを実現します。
"""

import networkx as nx
import logging
import io
from typing import Dict, Any, List, Optional
from .graph_cache import get_cache
from ..metrics.network_metrics import calculate_all_metrics
from ..metrics.centrality_functions import get_centrality_function
from ..metrics.network_metrics import get_metric_function

# ロギングの設定
logger = logging.getLogger("networkx_mcp.tools.analysis")

def calculate_and_store_metrics(
    graphml_content: str,
    layout_type: str = "spring",
    layout_params: Optional[Dict[str, Any]] = None,
    metrics_to_calculate: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    GraphMLからグラフを読み込み、レイアウトと指標を計算してキャッシュに保存する
    
    Args:
        graphml_content (str): GraphML文字列
        layout_type (str): レイアウトアルゴリズムの種類
        layout_params (dict, optional): レイアウトパラメータ
        metrics_to_calculate (list, optional): 計算する指標のリスト（Noneの場合は全て計算）
        
    Returns:
        dict: 処理結果（graph_id、計算された指標のリスト、統計情報など）
    """
    try:
        # GraphMLをパース
        logger.debug(f"Parsing GraphML content (length: {len(graphml_content)})")
        content_io = io.BytesIO(graphml_content.encode('utf-8'))
        G = nx.read_graphml(content_io)
        
        if G.number_of_nodes() == 0:
            return {
                "success": False,
                "error": "Graph has no nodes"
            }
        
        logger.info(f"Loaded graph with {G.number_of_nodes()} nodes and {G.number_of_edges()} edges")
        
        # レイアウトを計算
        from ..layouts.layout_functions import get_layout_function
        layout_func = get_layout_function(layout_type)
        
        if layout_params is None:
            layout_params = {}
        
        logger.debug(f"Calculating {layout_type} layout")
        positions = layout_func(G, **layout_params)
        
        # 位置情報をノード属性として設定
        for node, pos in positions.items():
            G.nodes[node]['x'] = float(pos[0])
            G.nodes[node]['y'] = float(pos[1])
        
        # 指標を計算
        calculated_metrics = {}
        
        if metrics_to_calculate is None:
            # 全ての指標を計算
            logger.debug("Calculating all metrics")
            calculated_metrics = calculate_all_metrics(G, include_centrality=True)
        else:
            # 指定された指標のみ計算
            logger.debug(f"Calculating specified metrics: {metrics_to_calculate}")
            for metric_name in metrics_to_calculate:
                # 中心性指標かどうかチェック
                centrality_types = ["degree", "closeness", "betweenness", "eigenvector", 
                                   "pagerank", "katz", "load", "harmonic", "subgraph", 
                                   "communicability_betweenness"]
                
                if metric_name in centrality_types:
                    func = get_centrality_function(metric_name)
                    calculated_metrics[metric_name] = func(G)
                else:
                    func = get_metric_function(metric_name)
                    calculated_metrics[metric_name] = func(G)
        
        # 計算した指標をノード属性として設定
        for metric_name, metric_values in calculated_metrics.items():
            if isinstance(metric_values, dict):
                nx.set_node_attributes(G, metric_values, metric_name)
        
        # メタデータを準備
        metadata = {
            "layout_type": layout_type,
            "layout_params": layout_params,
            "calculated_metrics": list(calculated_metrics.keys()),
            "num_nodes": G.number_of_nodes(),
            "num_edges": G.number_of_edges(),
            "is_directed": G.is_directed()
        }
        
        # キャッシュに保存
        cache = get_cache()
        graph_id = cache.store(G, metadata)
        
        logger.info(f"Stored graph with ID: {graph_id}, calculated {len(calculated_metrics)} metrics")
        
        return {
            "success": True,
            "graph_id": graph_id,
            "metadata": metadata,
            "message": f"Successfully calculated and stored {len(calculated_metrics)} metrics"
        }
        
    except Exception as e:
        logger.error(f"Error in calculate_and_store_metrics: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            "success": False,
            "error": str(e)
        }

def get_visualization_data(
    graph_id: str,
    metric_name: str,
    color_scheme: str = "viridis",
    size_range: Optional[tuple] = None
) -> Dict[str, Any]:
    """
    キャッシュされたグラフから指定された指標に基づく可視化データを取得する
    
    Args:
        graph_id (str): グラフのID
        metric_name (str): 可視化する指標名
        color_scheme (str): カラースキーム（viridis, plasma, inferno, magma, cividis）
        size_range (tuple, optional): ノードサイズの範囲 (min, max)
        
    Returns:
        dict: Cytoscape.js形式の可視化データ
    """
    try:
        # キャッシュからグラフを取得
        cache = get_cache()
        G = cache.get(graph_id)
        
        if G is None:
            return {
                "success": False,
                "error": f"Graph not found in cache: {graph_id}"
            }
        
        metadata = cache.get_metadata(graph_id)
        
        # 指標がノード属性として存在するか確認
        if metric_name not in metadata.get("calculated_metrics", []):
            return {
                "success": False,
                "error": f"Metric '{metric_name}' not found. Available metrics: {metadata.get('calculated_metrics', [])}"
            }
        
        # 指標値を取得
        metric_values = nx.get_node_attributes(G, metric_name)
        
        if not metric_values:
            return {
                "success": False,
                "error": f"No values found for metric: {metric_name}"
            }
        
        # 値の範囲を取得
        values = list(metric_values.values())
        
        # コミュニティ検出の場合は整数値
        is_community = metric_name.startswith("community_")
        
        if is_community:
            # コミュニティの場合は離散的な色分け
            unique_communities = sorted(set(values))
            color_map = _get_community_colors(len(unique_communities))
        else:
            # 連続値の場合は正規化
            min_val = min(values)
            max_val = max(values)
            value_range = max_val - min_val if max_val > min_val else 1.0
        
        # サイズ範囲の設定
        if size_range is None:
            size_range = (10, 50)
        min_size, max_size = size_range
        
        # ノードデータを構築
        nodes = []
        for node, attrs in G.nodes(data=True):
            node_id = str(node)
            metric_value = metric_values.get(node, 0)
            
            # 色の計算
            if is_community:
                community_idx = unique_communities.index(metric_value)
                color = color_map[community_idx]
            else:
                # 正規化された値に基づいて色を計算
                normalized_value = (metric_value - min_val) / value_range if value_range > 0 else 0
                color = _get_color_from_scheme(normalized_value, color_scheme)
            
            # サイズの計算（連続値の場合のみ）
            if is_community:
                size = 20  # コミュニティの場合は固定サイズ
            else:
                normalized_value = (metric_value - min_val) / value_range if value_range > 0 else 0
                size = min_size + (max_size - min_size) * normalized_value
            
            node_data = {
                "data": {
                    "id": node_id,
                    "label": attrs.get("name", node_id),
                    metric_name: metric_value
                },
                "position": {
                    "x": float(attrs.get("x", 0)) * 500,  # スケーリング
                    "y": float(attrs.get("y", 0)) * 500
                },
                "style": {
                    "background-color": color,
                    "width": size,
                    "height": size
                }
            }
            nodes.append(node_data)
        
        # エッジデータを構築
        edges = []
        for u, v, attrs in G.edges(data=True):
            edge_data = {
                "data": {
                    "source": str(u),
                    "target": str(v)
                }
            }
            edges.append(edge_data)
        
        logger.info(f"Generated visualization data for metric '{metric_name}' with {len(nodes)} nodes")
        
        return {
            "success": True,
            "graph_id": graph_id,
            "metric_name": metric_name,
            "elements": {
                "nodes": nodes,
                "edges": edges
            },
            "metadata": {
                "num_nodes": len(nodes),
                "num_edges": len(edges),
                "metric_type": "community" if is_community else "continuous",
                "value_range": {
                    "min": min(values),
                    "max": max(values)
                } if not is_community else None,
                "num_communities": len(unique_communities) if is_community else None
            }
        }
        
    except Exception as e:
        logger.error(f"Error in get_visualization_data: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            "success": False,
            "error": str(e)
        }

def _get_color_from_scheme(value: float, scheme: str = "viridis") -> str:
    """
    正規化された値（0-1）からカラースキームに基づいて色を取得する
    
    Args:
        value (float): 正規化された値（0-1）
        scheme (str): カラースキーム名
        
    Returns:
        str: RGB色文字列
    """
    # 簡易的なカラーマッピング（matplotlib風）
    color_schemes = {
        "viridis": [
            (68, 1, 84), (72, 40, 120), (62, 73, 137), (49, 104, 142),
            (38, 130, 142), (31, 158, 137), (53, 183, 121), (109, 205, 89),
            (180, 222, 44), (253, 231, 37)
        ],
        "plasma": [
            (13, 8, 135), (75, 3, 161), (125, 3, 168), (168, 34, 150),
            (203, 70, 121), (229, 107, 93), (248, 148, 65), (253, 195, 40),
            (240, 249, 33), (240, 249, 33)
        ],
        "inferno": [
            (0, 0, 4), (40, 11, 84), (101, 21, 110), (159, 42, 99),
            (212, 72, 66), (245, 125, 21), (250, 193, 39), (245, 251, 173),
            (252, 255, 164), (252, 255, 164)
        ]
    }
    
    colors = color_schemes.get(scheme, color_schemes["viridis"])
    
    # 値に基づいてインデックスを計算
    idx = int(value * (len(colors) - 1))
    idx = max(0, min(len(colors) - 1, idx))
    
    r, g, b = colors[idx]
    return f"rgb({r}, {g}, {b})"

def _get_community_colors(num_communities: int) -> List[str]:
    """
    コミュニティ数に基づいて色のリストを生成する
    
    Args:
        num_communities (int): コミュニティ数
        
    Returns:
        list: RGB色文字列のリスト
    """
    # 定義済みの色パレット
    base_colors = [
        "rgb(31, 119, 180)",   # 青
        "rgb(255, 127, 14)",   # オレンジ
        "rgb(44, 160, 44)",    # 緑
        "rgb(214, 39, 40)",    # 赤
        "rgb(148, 103, 189)",  # 紫
        "rgb(140, 86, 75)",    # 茶
        "rgb(227, 119, 194)",  # ピンク
        "rgb(127, 127, 127)",  # グレー
        "rgb(188, 189, 34)",   # 黄緑
        "rgb(23, 190, 207)",   # シアン
    ]
    
    # 必要に応じて色を繰り返す
    colors = []
    for i in range(num_communities):
        colors.append(base_colors[i % len(base_colors)])
    
    return colors

def get_available_metrics(graph_id: str) -> Dict[str, Any]:
    """
    キャッシュされたグラフで利用可能な指標のリストを取得する
    
    Args:
        graph_id (str): グラフのID
        
    Returns:
        dict: 利用可能な指標のリストとメタデータ
    """
    try:
        cache = get_cache()
        metadata = cache.get_metadata(graph_id)
        
        if metadata is None:
            return {
                "success": False,
                "error": f"Graph not found in cache: {graph_id}"
            }
        
        return {
            "success": True,
            "graph_id": graph_id,
            "available_metrics": metadata.get("calculated_metrics", []),
            "graph_info": {
                "num_nodes": metadata.get("num_nodes"),
                "num_edges": metadata.get("num_edges"),
                "layout_type": metadata.get("layout_type"),
                "is_directed": metadata.get("is_directed")
            }
        }
        
    except Exception as e:
        logger.error(f"Error in get_available_metrics: {e}")
        return {
            "success": False,
            "error": str(e)
        }
