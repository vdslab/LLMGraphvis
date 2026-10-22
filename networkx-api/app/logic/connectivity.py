"""Connectivity calculations shared by API and MCP adapters; never mutate graphs."""

from collections import Counter

import networkx as nx

from .utils.graph_builder import build_graph_from_db

_COMPONENTS = {
    "connected_components": (nx.connected_components, False),
    "weakly_connected_components": (nx.weakly_connected_components, True),
    "strongly_connected_components": (nx.strongly_connected_components, True),
}


def components(network_id, db, kind, limit=10, node_limit=50):
    """The largest `limit` components, each listing at most `node_limit` IDs.

    Results do not grow with the network (ADR 0024): `size_distribution` maps
    component size -> number of components and always covers every component,
    so "how fragmented is it" is answered without listing thousands of IDs.
    """
    function, directed = _COMPONENTS[kind]
    graph = build_graph_from_db(network_id, db)
    if graph.is_directed() != directed:
        choices = (
            "analysis_weakly_connected_components or "
            "analysis_strongly_connected_components"
            if graph.is_directed() else "analysis_connected_components"
        )
        raise ValueError(f"Incompatible graph direction. Use {choices}.")
    groups = sorted(
        (sorted(group) for group in function(graph)),
        key=lambda group: (-len(group), group),
    )
    listed = [
        {
            "size": len(group),
            "node_ids": group[:node_limit],
            "omitted_nodes": max(0, len(group) - node_limit),
        }
        for group in groups[:limit]
    ]
    sizes = Counter(len(group) for group in groups)
    return {
        "components": listed,
        "count": len(groups),
        "omitted": len(groups) - len(listed),
        "size_distribution": {str(size): sizes[size] for size in sorted(sizes, reverse=True)},
        "is_directed": directed,
    }


def _undirected_graph(network_id, db):
    graph = build_graph_from_db(network_id, db)
    if graph.is_directed():
        raise ValueError(
            "This operation requires an undirected graph; no conversion was made."
        )
    return graph


def bridges(network_id, db, limit=50):
    graph = _undirected_graph(network_id, db)
    edges = sorted(sorted(edge) for edge in nx.bridges(graph))
    return {"bridges": edges[:limit], "count": len(edges), "omitted": max(0, len(edges) - limit)}


def articulation_points(network_id, db, limit=50):
    """Cut vertices, those whose removal leaves the most extra pieces first.

    Removing a cut vertex adds one piece per biconnected component it belongs
    to, minus one, so one linear pass ranks them all.
    """
    graph = _undirected_graph(network_id, db)
    membership = Counter(
        node for block in nx.biconnected_components(graph) for node in block
    )
    points = [node for node, blocks in membership.items() if blocks > 1]
    ranked = sorted(points, key=lambda node: (-membership[node], node))
    return {
        "node_ids": ranked[:limit],
        "pieces_added": {node: membership[node] - 1 for node in ranked[:limit]},
        "count": len(points),
        "omitted": max(0, len(points) - limit),
    }


def transitivity(network_id, db):
    graph = _undirected_graph(network_id, db)
    return {"transitivity": nx.transitivity(graph)}
