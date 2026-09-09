"""Read-only path queries with explicit cost semantics."""

import math

import networkx as nx

from .utils.graph_builder import build_graph_from_db


def path_graph(network_id, db, weight=None, method="dijkstra"):
    """Load edge costs; reject invalid costs before algorithms misinterpret them."""
    if method not in {"dijkstra", "bellman-ford"}:
        raise ValueError("method must be 'dijkstra' or 'bellman-ford'")
    if weight == "none":
        weight = None
    graph = build_graph_from_db(network_id, db, weight_attribute=weight)
    if weight is not None:
        for _, _, attributes in graph.edges(data=True):
            cost = attributes[weight]
            if not math.isfinite(cost):
                raise ValueError("Path costs must be finite numbers")
            if cost < 0 and method == "dijkstra":
                raise ValueError("Negative costs require method='bellman-ford'")
    return graph, weight


def require_node(graph, node_id):
    if node_id not in graph:
        raise ValueError(f"Node '{node_id}' not found. Use node_search to find its ID.")


def shortest_path(network_id, source, target, db, weight=None, method="dijkstra"):
    graph, weight = path_graph(network_id, db, weight, method)
    require_node(graph, source)
    require_node(graph, target)
    try:
        path = nx.shortest_path(graph, source, target, weight=weight, method=method)
    except nx.NetworkXNoPath:
        return {
            "error": f"No path exists between '{source}' and '{target}'.",
            "reachable": False,
        }
    distance = nx.path_weight(graph, path, weight) if weight else len(path) - 1
    return {
        "path": path,
        "length": distance,
        "hops": len(path) - 1,
        "source": source,
        "target": target,
        "weight": weight,
        "method": method if weight else "unweighted",
        "is_directed": graph.is_directed(),
    }


def single_source_distances(
    network_id, source, db, weight=None, method="dijkstra", cutoff=None
):
    if cutoff is not None and (not math.isfinite(cutoff) or cutoff < 0):
        raise ValueError("cutoff must be a finite nonnegative distance")
    graph, weight = path_graph(network_id, db, weight, method)
    require_node(graph, source)
    if weight is None:
        distances = nx.single_source_shortest_path_length(graph, source, cutoff=cutoff)
    elif method == "bellman-ford":
        # Filter only after convergence: negative edges can reduce a path cost.
        distances = nx.single_source_bellman_ford_path_length(graph, source, weight)
    else:
        distances = nx.single_source_dijkstra_path_length(
            graph, source, cutoff=cutoff, weight=weight
        )
    if cutoff is not None:
        distances = {
            node: value for node, value in distances.items() if value <= cutoff
        }
    return {
        "source": source,
        "distances": distances,
        "returned_count": len(distances),
        "node_count": len(graph),
        "cutoff": cutoff,
        "weight": weight,
        "method": method if weight else "unweighted",
        "is_directed": graph.is_directed(),
    }


def has_path(network_id, source, target, db):
    graph, _ = path_graph(network_id, db)
    require_node(graph, source)
    require_node(graph, target)
    return {
        "source": source,
        "target": target,
        "reachable": nx.has_path(graph, source, target),
        "is_directed": graph.is_directed(),
    }
