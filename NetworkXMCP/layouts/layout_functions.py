"""
NetworkX Layout Functions.

This module provides a set of functions for calculating graph layouts using
different algorithms from the NetworkX library.
"""

import networkx as nx
import numpy as np
import logging
import random

# ロギングの設定
logger = logging.getLogger("networkx_mcp.layouts.layout")

def calculate_spring_layout(G, k=None, pos=None, fixed=None, iterations=50, threshold=1e-4, weight='weight', scale=1.0, center=None, dim=2, seed=None):
    """
    Calculates the spring layout of a graph.

    Args:
        G: The NetworkX graph.
        k: The optimal distance between nodes.
        pos: Initial positions for nodes.
        fixed: Nodes to keep fixed at their initial positions.
        iterations: The number of iterations of the algorithm.
        threshold: The threshold for stopping the algorithm.
        weight: The edge attribute that holds the numerical value used for
            the edge weight.
        scale: The scale factor for the layout.
        center: The center of the layout.
        dim: The dimension of the layout.
        seed: The random seed.

    Returns:
        A dictionary of positions keyed by node.
    """
    try:
        return nx.spring_layout(G, k=k, pos=pos, fixed=fixed, iterations=iterations, threshold=threshold, weight=weight, scale=scale, center=center, dim=dim, seed=seed)
    except Exception as e:
        logger.error(f"Error calculating spring layout: {e}")
        # フォールバック: ランダムレイアウト
        return nx.random_layout(G, center=center, dim=dim, seed=seed)

def calculate_circular_layout(G, scale=1, center=None, dim=2):
    """
    Calculates the circular layout of a graph.

    Args:
        G: The NetworkX graph.
        scale: The scale factor for the layout.
        center: The center of the layout.
        dim: The dimension of the layout.

    Returns:
        A dictionary of positions keyed by node.
    """
    try:
        return nx.circular_layout(G, scale=scale, center=center, dim=dim)
    except Exception as e:
        logger.error(f"Error calculating circular layout: {e}")
        # フォールバック: ランダムレイアウト
        return nx.random_layout(G, center=center, dim=dim)

def calculate_random_layout(G, center=None, dim=2, seed=None):
    """
    Calculates the random layout of a graph.

    Args:
        G: The NetworkX graph.
        center: The center of the layout.
        dim: The dimension of the layout.
        seed: The random seed.

    Returns:
        A dictionary of positions keyed by node.
    """
    try:
        return nx.random_layout(G, center=center, dim=dim, seed=seed)
    except Exception as e:
        logger.error(f"Error calculating random layout: {e}")
        # フォールバック: 手動でランダムレイアウトを生成
        pos = {}
        for node in G.nodes():
            pos[node] = np.array([random.uniform(-1, 1), random.uniform(-1, 1)])
        return pos

def calculate_spectral_layout(G, weight='weight', scale=1, center=None, dim=2):
    """
    Calculates the spectral layout of a graph.

    Args:
        G: The NetworkX graph.
        weight: The edge attribute that holds the numerical value used for
            the edge weight.
        scale: The scale factor for the layout.
        center: The center of the layout.
        dim: The dimension of the layout.

    Returns:
        A dictionary of positions keyed by node.
    """
    try:
        return nx.spectral_layout(G, weight=weight, scale=scale, center=center, dim=dim)
    except Exception as e:
        logger.error(f"Error calculating spectral layout: {e}")
        # フォールバック: スプリングレイアウト
        return nx.spring_layout(G, scale=scale, center=center, dim=dim)

def calculate_shell_layout(G, nlist=None, scale=1, center=None, dim=2):
    """
    Calculates the shell layout of a graph.

    Args:
        G: The NetworkX graph.
        nlist: A list of lists of nodes, representing the shells.
        scale: The scale factor for the layout.
        center: The center of the layout.
        dim: The dimension of the layout.

    Returns:
        A dictionary of positions keyed by node.
    """
    try:
        # nlistが指定されていない場合は、連結成分ごとにノードをグループ化
        if nlist is None:
            components = list(nx.connected_components(G))
            if not components:
                # 連結成分がない場合は全ノードを1つのグループとする
                nlist = [list(G.nodes())]
            else:
                nlist = components
        
        return nx.shell_layout(G, nlist=nlist, scale=scale, center=center, dim=dim)
    except Exception as e:
        logger.error(f"Error calculating shell layout: {e}")
        # フォールバック: 円形レイアウト
        return nx.circular_layout(G, scale=scale, center=center, dim=dim)

def calculate_kamada_kawai_layout(G, dist=None, pos=None, weight='weight', scale=1, center=None, dim=2):
    """
    Calculates the Kamada-Kawai layout of a graph.

    Args:
        G: The NetworkX graph.
        dist: A dictionary of distances between nodes.
        pos: Initial positions for nodes.
        weight: The edge attribute that holds the numerical value used for
            the edge weight.
        scale: The scale factor for the layout.
        center: The center of the layout.
        dim: The dimension of the layout.

    Returns:
        A dictionary of positions keyed by node.
    """
    try:
        return nx.kamada_kawai_layout(G, dist=dist, pos=pos, weight=weight, scale=scale, center=center, dim=dim)
    except Exception as e:
        logger.error(f"Error calculating Kamada-Kawai layout: {e}")
        # フォールバック: スプリングレイアウト
        return nx.spring_layout(G, pos=pos, weight=weight, scale=scale, center=center, dim=dim)

def calculate_fruchterman_reingold_layout(G, k=None, pos=None, fixed=None, iterations=50, threshold=1e-4, weight='weight', scale=1, center=None, dim=2, seed=None):
    """
    Calculates the Fruchterman-Reingold layout of a graph.

    Args:
        G: The NetworkX graph.
        k: The optimal distance between nodes.
        pos: Initial positions for nodes.
        fixed: Nodes to keep fixed at their initial positions.
        iterations: The number of iterations of the algorithm.
        threshold: The threshold for stopping the algorithm.
        weight: The edge attribute that holds the numerical value used for
            the edge weight.
        scale: The scale factor for the layout.
        center: The center of the layout.
        dim: The dimension of the layout.
        seed: The random seed.

    Returns:
        A dictionary of positions keyed by node.
    """
    try:
        return nx.fruchterman_reingold_layout(G, k=k, pos=pos, fixed=fixed, iterations=iterations, threshold=threshold, weight=weight, scale=scale, center=center, dim=dim, seed=seed)
    except Exception as e:
        logger.error(f"Error calculating Fruchterman-Reingold layout: {e}")
        # フォールバック: スプリングレイアウト
        return nx.spring_layout(G, k=k, pos=pos, fixed=fixed, iterations=iterations, threshold=threshold, weight=weight, scale=scale, center=center, dim=dim, seed=seed)

def calculate_spiral_layout(G, scale=1, center=None, dim=2, resolution=0.35, equidistant=False):
    """
    Calculates the spiral layout of a graph.

    Args:
        G: The NetworkX graph.
        scale: The scale factor for the layout.
        center: The center of the layout.
        dim: The dimension of the layout.
        resolution: The tightness of the spiral.
        equidistant: Whether to space the nodes equidistantly.

    Returns:
        A dictionary of positions keyed by node.
    """
    try:
        return nx.spiral_layout(G, scale=scale, center=center, dim=dim, resolution=resolution, equidistant=equidistant)
    except Exception as e:
        logger.error(f"Error calculating spiral layout: {e}")
        # フォールバック: 円形レイアウト
        return nx.circular_layout(G, scale=scale, center=center, dim=dim)

def calculate_multipartite_layout(G, subset_key='subset', align='vertical', scale=1, center=None):
    """
    Calculates the multipartite layout of a graph.

    Args:
        G: The NetworkX graph.
        subset_key: The node attribute key that identifies the subset.
        align: The alignment of the subsets.
        scale: The scale factor for the layout.
        center: The center of the layout.

    Returns:
        A dictionary of positions keyed by node.
    """
    try:
        # ノードに部分集合属性がない場合は、次数に基づいて割り当て
        for node in G.nodes():
            if subset_key not in G.nodes[node]:
                G.nodes[node][subset_key] = G.degree(node) % 3
        
        return nx.multipartite_layout(G, subset_key=subset_key, align=align, scale=scale, center=center)
    except Exception as e:
        logger.error(f"Error calculating multipartite layout: {e}")
        # フォールバック: シェルレイアウト
        return nx.shell_layout(G, scale=scale, center=center)

def calculate_bipartite_layout(G, nodes, align='vertical', scale=1, center=None):
    """
    Calculates the bipartite layout of a graph.

    Args:
        G: The NetworkX graph.
        nodes: The nodes in one partition of the graph.
        align: The alignment of the partitions.
        scale: The scale factor for the layout.
        center: The center of the layout.

    Returns:
        A dictionary of positions keyed by node.
    """
    try:
        return nx.bipartite_layout(G, nodes, align=align, scale=scale, center=center)
    except Exception as e:
        logger.error(f"Error calculating bipartite layout: {e}")
        # フォールバック: シェルレイアウト
        return nx.shell_layout(G, scale=scale, center=center)

def get_layout_function(layout_type):
    """
    Returns the layout function for a given layout type.

    Args:
        layout_type: The name of the layout type.

    Returns:
        The layout function.
    """
    layout_functions = {
        "spring": calculate_spring_layout,
        "circular": calculate_circular_layout,
        "random": calculate_random_layout,
        "spectral": calculate_spectral_layout,
        "shell": calculate_shell_layout,
        "kamada_kawai": calculate_kamada_kawai_layout,
        "fruchterman_reingold": calculate_fruchterman_reingold_layout,
        "spiral": calculate_spiral_layout,
        "multipartite": calculate_multipartite_layout,
        "bipartite": calculate_bipartite_layout
    }
    
    return layout_functions.get(layout_type, calculate_spring_layout)
