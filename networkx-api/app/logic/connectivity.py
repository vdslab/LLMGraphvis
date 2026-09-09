"""Connectivity calculations shared by API and MCP adapters; never mutate graphs."""

import networkx as nx

from .utils.graph_builder import build_graph_from_db

_COMPONENTS = {
    "connected_components": (nx.connected_components, False),
    "weakly_connected_components": (nx.weakly_connected_components, True),
    "strongly_connected_components": (nx.strongly_connected_components, True),
}


def components(network_id, db, kind):
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
    return {"components": groups, "count": len(groups), "is_directed": directed}


def _undirected_graph(network_id, db):
    graph = build_graph_from_db(network_id, db)
    if graph.is_directed():
        raise ValueError(
            "This operation requires an undirected graph; no conversion was made."
        )
    return graph


def bridges(network_id, db):
    graph = _undirected_graph(network_id, db)
    edges = sorted(sorted(edge) for edge in nx.bridges(graph))
    return {"bridges": edges, "count": len(edges)}


def articulation_points(network_id, db):
    graph = _undirected_graph(network_id, db)
    nodes = sorted(nx.articulation_points(graph))
    return {"node_ids": nodes, "count": len(nodes)}


def transitivity(network_id, db):
    graph = _undirected_graph(network_id, db)
    return {"transitivity": nx.transitivity(graph)}
