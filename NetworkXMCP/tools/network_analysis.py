"""
ネットワーク分析モジュール
===================

ネットワークグラフの分析機能を提供するモジュール
"""

import networkx as nx
import logging
import traceback
from typing import Dict, Any, Optional

# ロギングの設定
logger = logging.getLogger("networkx_mcp.tools.network_analysis")

def get_network_info(G):
    """
    ネットワークの基本情報を取得する
    
    Args:
        G (nx.Graph): NetworkXグラフ
        
    Returns:
        dict: ネットワーク情報
    """
    try:
        # 基本的なネットワーク指標を計算
        num_nodes = G.number_of_nodes()
        num_edges = G.number_of_edges()
        density = nx.density(G)
        
        # 連結成分の計算
        is_connected = nx.is_connected(G)
        num_components = nx.number_connected_components(G) if not is_connected else 1
        
        # 次数の計算
        degrees = [d for _, d in G.degree()]
        avg_degree = sum(degrees) / len(degrees) if degrees else 0
        
        # クラスタリング係数の計算
        clustering = nx.average_clustering(G)
        
        return {
            "num_nodes": num_nodes,
            "num_edges": num_edges,
            "density": density,
            "is_connected": is_connected,
            "num_components": num_components,
            "avg_degree": avg_degree,
            "clustering_coefficient": clustering
        }
    except Exception as e:
        logger.error(f"Error getting network info: {e}")
        return {
            "error": f"Error getting network info: {str(e)}"
        }

def calculate_centrality(G, centrality_type="degree", **kwargs):
    """
    指定された中心性指標を計算し、グラフのノード属性として追加する

    Args:
        G (nx.Graph): NetworkXグラフ
        centrality_type (str): 計算する中心性の種類
            (degree, closeness, betweenness, eigenvector, pagerank)
        **kwargs: 各中心性計算関数に渡す追加の引数

    Returns:
        dict: 処理結果を含む辞書
    """
    try:
        centrality_calculators = {
            "degree": nx.degree_centrality,
            "closeness": nx.closeness_centrality,
            "betweenness": nx.betweenness_centrality,
            "eigenvector": nx.eigenvector_centrality,
            "pagerank": nx.pagerank
        }

        if centrality_type not in centrality_calculators:
            raise ValueError(f"Unsupported centrality type: {centrality_type}")

        # 固有ベクトル中心性の場合、max_iterのデフォルト値を設定
        if centrality_type == "eigenvector":
            kwargs.setdefault("max_iter", 1000)

        # 中心性を計算
        centrality = centrality_calculators[centrality_type](G, **kwargs)
        
        # 結果を標準化
        max_value = max(centrality.values()) if centrality else 1.0
        if max_value > 0:
            # 0で除算しないようにチェック
            centrality = {str(k): v / max_value for k, v in centrality.items()}
        else:
            centrality = {str(k): 0 for k, v in centrality.items()}

        # ノード属性として中心性を設定
        nx.set_node_attributes(G, centrality, centrality_type)

        return {
            "success": True,
            "graph": G,
            "centrality_type": centrality_type,
            "centrality": centrality
        }
    except Exception as e:
        logger.error(f"Error calculating {centrality_type} centrality: {e}")
        # エラー発生時にトレースバックをログに出力
        logger.error(traceback.format_exc())
        return {
            "success": False,
            "error": f"Error calculating {centrality_type} centrality: {str(e)}"
        }
