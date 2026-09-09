"""Read-only structure and partition measurements."""

import math

import networkx as nx

from .attributes import load_node_attribute_values
from .paths import path_graph, require_node
from .utils.graph_builder import build_graph_from_db


def core_numbers(network_id, db):
    graph = build_graph_from_db(network_id, db)
    if nx.number_of_selfloops(graph):
        raise ValueError("Core numbers require a graph without self-loops")
    values = nx.core_number(graph)
    return {"core_numbers": values, "is_directed": graph.is_directed()}


def triangle_counts(network_id, db, nodes=None):
    graph = build_graph_from_db(network_id, db)
    if graph.is_directed():
        raise ValueError("Triangle counts require an undirected graph")
    if nodes is not None:
        for node in nodes:
            require_node(graph, node)
    values = nx.triangles(graph, nodes=nodes)
    result = {"triangles_by_node": values}
    if nodes is None:
        result["total_triangles"] = sum(values.values()) // 3
    return result


def edge_betweenness(network_id, db, k=None, normalized=True, weight=None, seed=42):
    graph, weight = path_graph(network_id, db, weight)
    if weight and any(data[weight] <= 0 for _, _, data in graph.edges(data=True)):
        raise ValueError("Weighted betweenness requires strictly positive distances")
    if k is not None and (not isinstance(k, int) or not 1 <= k <= len(graph)):
        raise ValueError("k must be an integer between 1 and the node count")
    values = nx.edge_betweenness_centrality(
        graph, k=k, normalized=normalized, weight=weight, seed=seed
    )
    return {
        "edges": [
            {"source": source, "target": target, "value": value}
            for (source, target), value in sorted(values.items())
        ],
        "parameters": {
            "k": k,
            "normalized": normalized,
            "weight": weight,
            "seed": seed,
        },
        "is_directed": graph.is_directed(),
    }


def partition_modularity(network_id, db, attribute, weight=None, resolution=1.0):
    if not math.isfinite(resolution) or resolution <= 0:
        raise ValueError("resolution must be finite and positive")
    weight = None if weight == "none" else weight
    graph = build_graph_from_db(network_id, db, weight_attribute=weight)
    labels = load_node_attribute_values(network_id, attribute, db)
    missing = set(graph) - set(labels)
    if missing:
        raise ValueError(
            f"Every node needs a partition value; missing: {sorted(missing)}"
        )
    groups = {}
    for node in graph:
        groups.setdefault(labels[node], set()).add(node)
    if weight:
        values = [data[weight] for _, _, data in graph.edges(data=True)]
        if any(not math.isfinite(value) or value < 0 for value in values):
            raise ValueError("Modularity weights must be finite nonnegative strengths")
    if graph.size(weight=weight) == 0:
        raise ValueError("Modularity is undefined when total edge strength is zero")
    score = nx.community.modularity(
        graph, groups.values(), weight=weight, resolution=resolution
    )
    return {
        "modularity": score,
        "community_count": len(groups),
        "attribute": attribute,
        "weight": weight,
        "resolution": resolution,
        "is_directed": graph.is_directed(),
    }
