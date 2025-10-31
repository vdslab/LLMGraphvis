"""
NetworkX Centrality Functions.

This module provides a set of functions for calculating various centrality
metrics using the NetworkX library.
"""

import networkx as nx
import numpy as np
import logging

# ロギングの設定
logger = logging.getLogger("networkx_mcp.metrics.centrality")

def calculate_degree_centrality(G):
    """
    Calculates the degree centrality of a graph.

    Args:
        G: The NetworkX graph.

    Returns:
        A dictionary of nodes with degree centrality as the value.
    """
    try:
        return nx.degree_centrality(G)
    except Exception as e:
        logger.error(f"Error calculating degree centrality: {e}")
        return {}

def calculate_closeness_centrality(G):
    """
    Calculates the closeness centrality of a graph.

    Args:
        G: The NetworkX graph.

    Returns:
        A dictionary of nodes with closeness centrality as the value.
    """
    try:
        return nx.closeness_centrality(G)
    except Exception as e:
        logger.error(f"Error calculating closeness centrality: {e}")
        return {}

def calculate_betweenness_centrality(G, k=None, normalized=True, weight=None, endpoints=False, seed=None):
    """
    Calculates the betweenness centrality of a graph.

    Args:
        G: The NetworkX graph.
        k: The number of nodes to use for sampling.
        normalized: Whether to normalize the centrality values.
        weight: The edge attribute that holds the numerical value used for
            the edge weight.
        endpoints: Whether to include endpoints in the calculation.
        seed: The random seed.

    Returns:
        A dictionary of nodes with betweenness centrality as the value.
    """
    try:
        return nx.betweenness_centrality(G, k=k, normalized=normalized, weight=weight, endpoints=endpoints, seed=seed)
    except Exception as e:
        logger.error(f"Error calculating betweenness centrality: {e}")
        return {}

def calculate_eigenvector_centrality(G, max_iter=100, tol=1.0e-6, nstart=None, weight=None):
    """
    Calculates the eigenvector centrality of a graph.

    Args:
        G: The NetworkX graph.
        max_iter: The maximum number of iterations.
        tol: The tolerance for convergence.
        nstart: The starting vector for power iteration.
        weight: The edge attribute that holds the numerical value used for
            the edge weight.

    Returns:
        A dictionary of nodes with eigenvector centrality as the value.
    """
    try:
        # 通常の固有ベクトル中心性計算を試みる
        try:
            return nx.eigenvector_centrality(G, max_iter=max_iter, tol=tol, nstart=nstart, weight=weight)
        except nx.PowerIterationFailedConvergence:
            # 収束しない場合はNumPy実装を使用
            logger.warning("Eigenvector centrality failed to converge, using NumPy implementation")
            return nx.eigenvector_centrality_numpy(G, weight=weight)
    except Exception as e:
        logger.error(f"Error calculating eigenvector centrality: {e}")
        return {}

def calculate_pagerank(G, alpha=0.85, personalization=None, max_iter=100, tol=1.0e-6, nstart=None, weight=None, dangling=None):
    """
    Calculates the PageRank of a graph.

    Args:
        G: The NetworkX graph.
        alpha: The damping parameter for PageRank.
        personalization: The personalization vector.
        max_iter: The maximum number of iterations.
        tol: The tolerance for convergence.
        nstart: The starting vector for power iteration.
        weight: The edge attribute that holds the numerical value used for
            the edge weight.
        dangling: The dangling node handling strategy.

    Returns:
        A dictionary of nodes with PageRank as the value.
    """
    try:
        return nx.pagerank(G, alpha=alpha, personalization=personalization, max_iter=max_iter, tol=tol, nstart=nstart, weight=weight, dangling=dangling)
    except Exception as e:
        logger.error(f"Error calculating PageRank: {e}")
        return {}

def calculate_katz_centrality(G, alpha=0.1, beta=1.0, max_iter=1000, tol=1.0e-6, nstart=None, normalized=True, weight=None):
    """
    Calculates the Katz centrality of a graph.

    Args:
        G: The NetworkX graph.
        alpha: The attenuation factor.
        beta: The constant scaling factor.
        max_iter: The maximum number of iterations.
        tol: The tolerance for convergence.
        nstart: The starting vector for power iteration.
        normalized: Whether to normalize the centrality values.
        weight: The edge attribute that holds the numerical value used for
            the edge weight.

    Returns:
        A dictionary of nodes with Katz centrality as the value.
    """
    try:
        return nx.katz_centrality(G, alpha=alpha, beta=beta, max_iter=max_iter, tol=tol, nstart=nstart, normalized=normalized, weight=weight)
    except Exception as e:
        logger.error(f"Error calculating Katz centrality: {e}")
        return {}

def calculate_load_centrality(G, v=None, cutoff=None, normalized=True, weight=None):
    """
    Calculates the load centrality of a graph.

    Args:
        G: The NetworkX graph.
        v: The node for which to calculate the centrality.
        cutoff: The maximum path length to consider.
        normalized: Whether to normalize the centrality values.
        weight: The edge attribute that holds the numerical value used for
            the edge weight.

    Returns:
        A dictionary of nodes with load centrality as the value.
    """
    try:
        return nx.load_centrality(G, v=v, cutoff=cutoff, normalized=normalized, weight=weight)
    except Exception as e:
        logger.error(f"Error calculating load centrality: {e}")
        return {}

def calculate_harmonic_centrality(G, nbunch=None, distance=None, weight=None):
    """
    Calculates the harmonic centrality of a graph.

    Args:
        G: The NetworkX graph.
        nbunch: A container of nodes for which to calculate the centrality.
        distance: The edge attribute that holds the numerical value used for
            the edge weight.
        weight: The edge attribute that holds the numerical value used for
            the edge weight.

    Returns:
        A dictionary of nodes with harmonic centrality as the value.
    """
    try:
        return nx.harmonic_centrality(G, nbunch=nbunch, distance=distance)
    except Exception as e:
        logger.error(f"Error calculating harmonic centrality: {e}")
        return {}

def calculate_subgraph_centrality(G):
    """
    Calculates the subgraph centrality of a graph.

    Args:
        G: The NetworkX graph.

    Returns:
        A dictionary of nodes with subgraph centrality as the value.
    """
    try:
        return nx.subgraph_centrality(G)
    except Exception as e:
        logger.error(f"Error calculating subgraph centrality: {e}")
        return {}

def calculate_communicability_betweenness_centrality(G, normalized=True):
    """
    Calculates the communicability betweenness centrality of a graph.

    Args:
        G: The NetworkX graph.
        normalized: Whether to normalize the centrality values.

    Returns:
        A dictionary of nodes with communicability betweenness centrality as
        the value.
    """
    try:
        return nx.communicability_betweenness_centrality(G, normalized=normalized)
    except Exception as e:
        logger.error(f"Error calculating communicability betweenness centrality: {e}")
        return {}

def get_centrality_function(centrality_type):
    """
    Returns the centrality function for a given centrality type.

    Args:
        centrality_type: The name of the centrality type.

    Returns:
        The centrality function.
    """
    centrality_functions = {
        "degree": calculate_degree_centrality,
        "closeness": calculate_closeness_centrality,
        "betweenness": calculate_betweenness_centrality,
        "eigenvector": calculate_eigenvector_centrality,
        "pagerank": calculate_pagerank,
        "katz": calculate_katz_centrality,
        "load": calculate_load_centrality,
        "harmonic": calculate_harmonic_centrality,
        "subgraph": calculate_subgraph_centrality,
        "communicability_betweenness": calculate_communicability_betweenness_centrality
    }
    
    return centrality_functions.get(centrality_type, calculate_degree_centrality)
