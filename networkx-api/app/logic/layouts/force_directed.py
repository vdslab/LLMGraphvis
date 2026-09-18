"""Force-directed layouts: spring, forceatlas2, arf.

Each function is the whole of that layout: its networkx call, the parameters it
accepts, how they are tuned to graph size, and what a weight means to it.
"""

import math

import networkx as nx
import numpy as np

from .base import WeightRole, register

# Graph attribute set by `prepare_forceatlas2`: `node_size` holds radii in drawn
# (renderer) units rather than in the layout's own coordinate units.
RENDERED_RADII = "node_size_in_rendered_units"


def tune_spring(G) -> dict:
    """Iterations and convergence threshold by graph size, plus node spacing.

    `k` is the optimal distance between nodes; 2.0/sqrt(N) is a little wider than
    networkx's own 1/sqrt(N), which reduces overlap on the graphs this app sees.
    """
    num_nodes = len(G.nodes)
    if num_nodes < 500:
        # High iterations, strict threshold for beautiful convergence
        iterations, threshold = 1000, 1e-6
    elif num_nodes < 2000:
        iterations, threshold = 500, 1e-5
    else:
        iterations, threshold = 200, 1e-4

    return {
        "k": 2.0 / math.sqrt(num_nodes) if num_nodes > 0 else None,
        "iterations": iterations,
        "threshold": threshold,
        "seed": 42,
    }


def tune_forceatlas2(G) -> dict:
    """Iteration count and repulsion, both derived from the graph's size/density.

    Each iteration computes dense pairwise repulsion (O(N^2), no Barnes-Hut
    approximation), so the iteration count directly dominates upload latency on
    large graphs. The floor/cap stay well above networkx's own default of 100 for
    layout quality, but far below the 1000-5000 range that made large uploads
    extremely slow.
    """
    num_nodes = len(G.nodes)
    num_edges = len(G.edges)
    avg_degree = (2 * num_edges) / num_nodes if num_nodes > 0 else 0

    return {
        "max_iter": max(200, min(2000, num_nodes)),
        # Average degree stands in for local clumping: the tighter the graph
        # pulls itself, the more repulsion it needs to stay readable.
        "scaling_ratio": max(2.0, min(10.0, avg_degree * 0.5)),
        "gravity": 1.0,
        "jitter_tolerance": 1.0,
        "seed": 42,
    }


def tune_arf(G) -> dict:
    """ARF is iterative like spring; nx's other defaults are reasonable as-is."""
    num_nodes = len(G.nodes)
    return {"max_iter": 1000 if num_nodes < 500 else (500 if num_nodes < 2000 else 200)}


@register(
    "spring",
    params={
        "k", "pos", "fixed", "iterations", "threshold", "weight",
        "scale", "center", "seed", "method", "gravity",
    },
    weight_role=WeightRole.STRENGTH,
    tune=tune_spring,
    aliases=("fruchterman_reingold",),
)
def spring(G, params):
    """Fruchterman-Reingold. Weights are attraction strength."""
    return nx.spring_layout(G, **params)


def prepare_forceatlas2(G, network_id, overrides, db):
    """Turn `size_aware=True` into `node_size`, from the sizes the nodes are drawn at.

    networkx wants one radius per node, which no caller can type out for a real
    graph, so the app fills it in from the saved node-size style.
    """
    from ..layout_quality import radius_from_size
    from ..visualization_builder import display_node_sizes

    if not overrides.pop("size_aware", None):
        return
    if overrides.get("node_size") is not None:
        raise ValueError("Choose size_aware or node_size, not both")
    sizes = display_node_sizes(db, network_id)
    overrides["node_size"] = {
        node: radius_from_size(sizes.get(node, 0.0)) for node in G.nodes
    }
    G.graph[RENDERED_RADII] = True


def _size_aware_forceatlas2(G, params):
    """ForceAtlas2 with radii given in drawn units.

    The radii have to be in the layout's own units, which are unknown until it
    has run (the renderer rescales to a 2000-unit square afterwards). So run
    once without sizes, convert the radii by that layout's extent, and continue
    from it with size-aware repulsion.
    """
    radii = params["node_size"]
    first = nx.forceatlas2_layout(G, **{**params, "node_size": None})
    coords = np.array(list(first.values()), dtype=float).reshape(-1, 2)
    extent = float(np.ptp(coords, axis=0).max()) if len(coords) > 1 else 0.0
    factor = (extent or 1.0) / 2000.0
    scaled = {node: radius * factor for node, radius in radii.items()}
    return nx.forceatlas2_layout(G, **{**params, "pos": first, "node_size": scaled})


@register(
    "forceatlas2",
    params={
        "pos", "max_iter", "jitter_tolerance", "scaling_ratio", "gravity",
        "distributed_action", "strong_gravity", "node_mass", "node_size",
        "weight", "linlog", "seed",
    },
    weight_role=WeightRole.STRENGTH,
    tune=tune_forceatlas2,
    prepare=prepare_forceatlas2,
    aliases=("forceatlas2_layout", "force-directed", "force_directed"),
)
def forceatlas2(G, params):
    """ForceAtlas2 (networkx native, 3.6+). Weights are attraction strength."""
    if G.graph.get(RENDERED_RADII) and params.get("node_size"):
        return _size_aware_forceatlas2(G, params)
    return nx.forceatlas2_layout(G, **params)


@register(
    "arf",
    params={"pos", "scaling", "a", "etol", "dt", "max_iter", "seed"},
    tune=tune_arf,
)
def arf(G, params):
    """Attractive-repulsive force layout. nx.arf_layout has no weight concept."""
    return nx.arf_layout(G, **params)
