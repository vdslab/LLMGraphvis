"""
グラフ作成モジュール
===================

ランダムネットワークやグラフを作成するためのモジュール
"""

import networkx as nx
import numpy as np
import logging
import random
from typing import Dict, List, Any, Optional, Union, Tuple

# ロギングの設定
logger = logging.getLogger("networkx_mcp.tools.graph_creation")

def create_random_network(num_nodes=20, edge_probability=0.2, seed=None):
    """
    ランダムネットワークを作成する
    
    Args:
        num_nodes (int, optional): ノード数
        edge_probability (float, optional): エッジ確率
        seed (int, optional): 乱数シード
        
    Returns:
        tuple: (NetworkXグラフ, ノードリスト, エッジリスト)
    """
    try:
        # 乱数シードの設定
        if seed is not None:
            random.seed(seed)
            np.random.seed(seed)
        
        # ランダムグラフを生成
        G = nx.gnp_random_graph(num_nodes, edge_probability, seed=seed)
        
        # 連結グラフを確保（孤立ノードがないようにする）
        if not nx.is_connected(G):
            # 連結成分を取得
            components = list(nx.connected_components(G))
            # 最大の連結成分以外の各成分から、最大成分へエッジを追加
            largest_component = max(components, key=len)
            for component in components:
                if component != largest_component:
                    # 各成分から最大成分へのエッジを追加
                    node_from = random.choice(list(component))
                    node_to = random.choice(list(largest_component))
                    G.add_edge(node_from, node_to)
        
        # ノードとエッジの情報を抽出
        nodes = []
        for node in G.nodes():
            # ノードごとに少し異なるサイズと色の変化をつける
            size_variation = random.uniform(4.5, 5.5)
            color_variation = random.randint(-15, 15)
            base_color = [29, 78, 216]  # #1d4ed8のRGB値
            
            # 色の変化を適用（範囲内に収める）
            r = max(0, min(255, base_color[0] + color_variation))
            g = max(0, min(255, base_color[1] + color_variation))
            b = max(0, min(255, base_color[2] + color_variation))
            
            nodes.append({
                "id": str(node),
                "label": f"Node {node}",
                "size": size_variation,
                "color": f"rgb({r}, {g}, {b})"
            })
        
        edges = []
        for edge in G.edges():
            edges.append({
                "source": str(edge[0]),
                "target": str(edge[1]),
                "width": 1,
                "color": "#94a3b8"
            })
        
        # スプリングレイアウトを適用
        pos = nx.spring_layout(G)
        
        # ノードの位置情報を追加
        for node in nodes:
            node_id = int(node["id"])
            if node_id in pos:
                node["x"] = float(pos[node_id][0])
                node["y"] = float(pos[node_id][1])
        
        return G, nodes, edges
    except Exception as e:
        logger.error(f"Error creating random network: {e}")
        return None, [], []
