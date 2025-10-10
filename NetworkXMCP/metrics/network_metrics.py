"""
ネットワーク指標計算関数モジュール
===================

NetworkXを使用したグラフの各種ネットワーク指標計算関数を提供します。
中心性以外の指標（コミュニティ検出、クラスタリング係数など）を含みます。
"""

import networkx as nx
import logging
from typing import Dict, Any, Optional

# ロギングの設定
logger = logging.getLogger("networkx_mcp.metrics.network_metrics")

def calculate_clustering_coefficient(G):
    """
    クラスタリング係数を計算する
    
    Args:
        G (nx.Graph): NetworkXグラフ
        
    Returns:
        dict: ノードIDをキー、クラスタリング係数を値とする辞書
    """
    try:
        return nx.clustering(G)
    except Exception as e:
        logger.error(f"Error calculating clustering coefficient: {e}")
        return {}

def calculate_average_clustering(G):
    """
    平均クラスタリング係数を計算する
    
    Args:
        G (nx.Graph): NetworkXグラフ
        
    Returns:
        float: 平均クラスタリング係数
    """
    try:
        return nx.average_clustering(G)
    except Exception as e:
        logger.error(f"Error calculating average clustering: {e}")
        return 0.0

def detect_communities_louvain(G, resolution=1.0, seed=None):
    """
    Louvain法を使用してコミュニティを検出する
    
    Args:
        G (nx.Graph): NetworkXグラフ
        resolution (float, optional): 解像度パラメータ
        seed (int, optional): 乱数シード
        
    Returns:
        dict: ノードIDをキー、コミュニティIDを値とする辞書
    """
    try:
        # NetworkX 2.5以降ではcommunity.louvain_communitiesを使用
        from networkx.algorithms import community
        communities = community.louvain_communities(G, resolution=resolution, seed=seed)
        
        # コミュニティIDをノードにマッピング
        node_to_community = {}
        for community_id, community_nodes in enumerate(communities):
            for node in community_nodes:
                node_to_community[node] = community_id
        
        return node_to_community
    except Exception as e:
        logger.error(f"Error detecting communities with Louvain: {e}")
        return {}

def detect_communities_label_propagation(G):
    """
    ラベル伝播法を使用してコミュニティを検出する
    
    Args:
        G (nx.Graph): NetworkXグラフ
        
    Returns:
        dict: ノードIDをキー、コミュニティIDを値とする辞書
    """
    try:
        from networkx.algorithms import community
        communities = community.label_propagation_communities(G)
        
        # コミュニティIDをノードにマッピング
        node_to_community = {}
        for community_id, community_nodes in enumerate(communities):
            for node in community_nodes:
                node_to_community[node] = community_id
        
        return node_to_community
    except Exception as e:
        logger.error(f"Error detecting communities with label propagation: {e}")
        return {}

def detect_communities_greedy_modularity(G):
    """
    貪欲モジュラリティ最適化を使用してコミュニティを検出する
    
    Args:
        G (nx.Graph): NetworkXグラフ
        
    Returns:
        dict: ノードIDをキー、コミュニティIDを値とする辞書
    """
    try:
        from networkx.algorithms import community
        communities = community.greedy_modularity_communities(G)
        
        # コミュニティIDをノードにマッピング
        node_to_community = {}
        for community_id, community_nodes in enumerate(communities):
            for node in community_nodes:
                node_to_community[node] = community_id
        
        return node_to_community
    except Exception as e:
        logger.error(f"Error detecting communities with greedy modularity: {e}")
        return {}

def calculate_modularity(G, communities):
    """
    モジュラリティを計算する
    
    Args:
        G (nx.Graph): NetworkXグラフ
        communities (list): コミュニティのリスト（各コミュニティはノードのセット）
        
    Returns:
        float: モジュラリティ値
    """
    try:
        from networkx.algorithms import community
        return community.modularity(G, communities)
    except Exception as e:
        logger.error(f"Error calculating modularity: {e}")
        return 0.0

def calculate_core_number(G):
    """
    k-coreのコア番号を計算する
    
    Args:
        G (nx.Graph): NetworkXグラフ
        
    Returns:
        dict: ノードIDをキー、コア番号を値とする辞書
    """
    try:
        return nx.core_number(G)
    except Exception as e:
        logger.error(f"Error calculating core number: {e}")
        return {}

def calculate_eccentricity(G):
    """
    離心率を計算する（連結グラフのみ）
    
    Args:
        G (nx.Graph): NetworkXグラフ
        
    Returns:
        dict: ノードIDをキー、離心率を値とする辞書
    """
    try:
        if nx.is_connected(G):
            return nx.eccentricity(G)
        else:
            logger.warning("Graph is not connected, calculating eccentricity for largest component")
            # 最大連結成分のみで計算
            largest_cc = max(nx.connected_components(G), key=len)
            subgraph = G.subgraph(largest_cc)
            return nx.eccentricity(subgraph)
    except Exception as e:
        logger.error(f"Error calculating eccentricity: {e}")
        return {}

def calculate_triangles(G):
    """
    各ノードが含まれる三角形の数を計算する
    
    Args:
        G (nx.Graph): NetworkXグラフ
        
    Returns:
        dict: ノードIDをキー、三角形の数を値とする辞書
    """
    try:
        return nx.triangles(G)
    except Exception as e:
        logger.error(f"Error calculating triangles: {e}")
        return {}

def calculate_square_clustering(G):
    """
    正方形クラスタリング係数を計算する
    
    Args:
        G (nx.Graph): NetworkXグラフ
        
    Returns:
        dict: ノードIDをキー、正方形クラスタリング係数を値とする辞書
    """
    try:
        return nx.square_clustering(G)
    except Exception as e:
        logger.error(f"Error calculating square clustering: {e}")
        return {}

def get_metric_function(metric_type):
    """
    指標タイプに基づいて指標計算関数を取得する
    
    Args:
        metric_type (str): 指標タイプ
        
    Returns:
        function: 指標計算関数
    """
    metric_functions = {
        "clustering": calculate_clustering_coefficient,
        "community_louvain": detect_communities_louvain,
        "community_label_propagation": detect_communities_label_propagation,
        "community_greedy_modularity": detect_communities_greedy_modularity,
        "core_number": calculate_core_number,
        "eccentricity": calculate_eccentricity,
        "triangles": calculate_triangles,
        "square_clustering": calculate_square_clustering,
    }
    
    return metric_functions.get(metric_type, calculate_clustering_coefficient)

def calculate_all_metrics(G, include_centrality=True):
    """
    すべての利用可能な指標を計算する
    
    Args:
        G (nx.Graph): NetworkXグラフ
        include_centrality (bool): 中心性指標も含めるかどうか
        
    Returns:
        dict: 各指標名をキー、計算結果を値とする辞書
    """
    results = {}
    
    try:
        # ネットワーク指標
        results["clustering"] = calculate_clustering_coefficient(G)
        results["community_louvain"] = detect_communities_louvain(G)
        results["core_number"] = calculate_core_number(G)
        results["triangles"] = calculate_triangles(G)
        
        # 連結グラフの場合のみ計算
        if nx.is_connected(G):
            results["eccentricity"] = calculate_eccentricity(G)
        
        # 中心性指標も含める場合
        if include_centrality:
            from .centrality_functions import (
                calculate_degree_centrality,
                calculate_closeness_centrality,
                calculate_betweenness_centrality,
                calculate_eigenvector_centrality,
                calculate_pagerank
            )
            
            results["degree_centrality"] = calculate_degree_centrality(G)
            results["closeness_centrality"] = calculate_closeness_centrality(G)
            results["betweenness_centrality"] = calculate_betweenness_centrality(G)
            results["eigenvector_centrality"] = calculate_eigenvector_centrality(G)
            results["pagerank"] = calculate_pagerank(G)
        
        logger.info(f"Successfully calculated {len(results)} metrics")
        return results
        
    except Exception as e:
        logger.error(f"Error calculating all metrics: {e}")
        return results
