"""The view channels that are not attribute encodings (ADR 0023).

Highlight and label visibility decide *which* elements stand out, not how a
value maps to a colour or a size. They are resolved here so the builder only
asks "is this node highlighted / labelled?".

A highlight config is stored already resolved: `node_ids` is the final set,
after any neighbourhood expansion, and `path` is the ordered route when one
was given. Re-rendering therefore never recomputes a graph query.
"""

import uuid
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

import networkx as nx

from .utils.graph_builder import build_graph_from_db

EDGE_MODES = ("induced", "path", "incident", "none")
LABEL_VISIBILITY = ("auto", "all", "hover", "top_n", "nodes", "highlighted")

DEFAULT_DIM_OPACITY = 0.12
# `auto` labels every node of a small graph and only the best-connected ones
# of a larger graph, where labelling everything is unreadable.
AUTO_LABEL_ALL_BELOW = 60
AUTO_LABEL_TOP_N = 25
DEFAULT_TOP_N = 20
DEFAULT_VIEWPORT_PADDING = 0.15


def _require_nodes(graph: nx.Graph, node_ids: Iterable[str]) -> None:
    missing = [n for n in node_ids if n not in graph]
    if missing:
        preview = ", ".join(missing[:10])
        more = f" (+{len(missing) - 10} more)" if len(missing) > 10 else ""
        raise ValueError(
            f"Unknown node ID(s): {preview}{more}. Use node_search to resolve "
            "labels to exact IDs."
        )


def resolve_highlight(
    network_id: int,
    db,
    node_ids: Sequence[str],
    edges: str = "induced",
    neighbor_hops: int = 0,
    dim_opacity: float = DEFAULT_DIM_OPACITY,
    color: Optional[str] = None,
) -> Dict[str, Any]:
    """Validate a highlight request and return the config to store."""
    if edges not in EDGE_MODES:
        raise ValueError(f"edges must be one of {', '.join(EDGE_MODES)}")
    if not node_ids:
        raise ValueError(
            "node_ids is empty. To remove a highlight use "
            "visualization_reset_style(targets=['highlight'])."
        )
    if not 0 <= dim_opacity <= 1:
        raise ValueError("dim_opacity must be between 0 and 1")
    if neighbor_hops < 0:
        raise ValueError("neighbor_hops must be zero or more")
    graph = build_graph_from_db(network_id, db)
    seeds = [str(n) for n in node_ids]
    _require_nodes(graph, seeds)

    path: Optional[List[str]] = None
    if edges == "path":
        if len(seeds) < 2:
            raise ValueError("A path needs at least two nodes, in route order")
        unlinked = [
            (a, b) for a, b in zip(seeds, seeds[1:]) if not graph.has_edge(a, b)
        ]
        if unlinked:
            a, b = unlinked[0]
            raise ValueError(
                f"No edge {a} -> {b}: path node_ids must be consecutive nodes of a "
                "route, e.g. the `path` returned by analysis_shortest_path."
            )
        path = seeds

    selected: Set[str] = set(seeds)
    if neighbor_hops:
        undirected = graph.to_undirected(as_view=True)
        for seed in seeds:
            selected |= set(
                nx.single_source_shortest_path_length(
                    undirected, seed, cutoff=neighbor_hops
                )
            )

    return {
        "node_ids": sorted(selected),
        "seed_node_ids": seeds,
        "edges": edges,
        "path": path,
        "neighbor_hops": neighbor_hops,
        "dim_opacity": dim_opacity,
        "color": color,
    }


class Highlight:
    """Membership tests for one stored highlight config."""

    def __init__(self, config: Optional[Dict[str, Any]], directed: bool):
        self.active = bool(config and config.get("node_ids"))
        config = config or {}
        self.nodes: Set[str] = set(config.get("node_ids") or [])
        self.mode: str = config.get("edges") or "induced"
        self.dim_opacity: float = config.get("dim_opacity", DEFAULT_DIM_OPACITY)
        self.color: Optional[str] = config.get("color")
        self.path_edges: Set[Tuple[str, str]] = set()
        path = config.get("path") or []
        for a, b in zip(path, path[1:]):
            self.path_edges.add((a, b))
            if not directed:
                self.path_edges.add((b, a))

    def node(self, node_id: str) -> bool:
        return node_id in self.nodes

    def edge(self, source: str, target: str) -> bool:
        if self.mode == "none":
            return False
        if self.mode == "path":
            return (source, target) in self.path_edges
        if self.mode == "incident":
            return source in self.nodes or target in self.nodes
        return source in self.nodes and target in self.nodes

    def summary(self, vis_nodes: List[Dict], vis_edges: List[Dict]) -> Dict[str, Any]:
        return {
            "node_count": sum(1 for n in vis_nodes if n.get("highlighted")),
            "edge_count": sum(1 for e in vis_edges if e.get("highlighted")),
            "edges": self.mode,
        }


def label_flags(
    config: Optional[Dict[str, Any]],
    vis_nodes: List[Dict],
    vis_edges: List[Dict],
    rank_values: Optional[Dict[str, float]] = None,
) -> Optional[Dict[str, bool]]:
    """Which nodes show a permanent label, or None to leave it to the viewer.

    Returns None when no label visibility was ever chosen, so the canvas's own
    label toggle keeps its old meaning for existing conversations.
    """
    if not config:
        return None
    visibility = config.get("visibility")
    if not visibility:
        visibility = "all" if config.get("show_all") else None
    if visibility is None:
        return None
    ids = [n["id"] for n in vis_nodes]
    if visibility == "all":
        return dict.fromkeys(ids, True)
    if visibility == "hover":
        return dict.fromkeys(ids, False)
    if visibility == "nodes":
        chosen = set(config.get("node_ids") or [])
        return {i: i in chosen for i in ids}
    if visibility == "highlighted":
        return {n["id"]: bool(n.get("highlighted")) for n in vis_nodes}

    if visibility == "auto" and len(ids) < AUTO_LABEL_ALL_BELOW:
        return dict.fromkeys(ids, True)
    top_n = config.get("top_n") or (
        AUTO_LABEL_TOP_N if visibility == "auto" else DEFAULT_TOP_N
    )
    if rank_values is None:
        rank_values = dict.fromkeys(ids, 0)
        for e in vis_edges:
            rank_values[e["source"]] = rank_values.get(e["source"], 0) + 1
            rank_values[e["target"]] = rank_values.get(e["target"], 0) + 1
    ranked = sorted(
        ids,
        key=lambda i: (rank_values.get(i) is None, -(rank_values.get(i) or 0), i),
    )
    chosen = set(ranked[:top_n])
    return {i: i in chosen for i in ids}


def viewport_directive(
    mode: str, node_ids: Optional[List[str]] = None, padding: float = DEFAULT_VIEWPORT_PADDING
) -> Dict[str, Any]:
    """A one-shot instruction for the canvas; `nonce` makes each one distinct."""
    return {
        "mode": mode,
        "node_ids": node_ids or [],
        "padding": padding,
        "nonce": uuid.uuid4().hex,
    }
