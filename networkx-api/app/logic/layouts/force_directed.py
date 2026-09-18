"""Force-directed layouts: spring, forceatlas2, arf.

Each function is the whole of that layout: its networkx call, the parameters it
accepts, how they are tuned to graph size, and what a weight means to it.
"""

import math

import networkx as nx
import numpy as np

from .base import Knob, WeightRole, register

# Graph attribute set by `prepare_forceatlas2`: `node_size` holds radii in drawn
# (renderer) units rather than in the layout's own coordinate units.
RENDERED_RADII = "node_size_in_rendered_units"


# How far gravity is raised for a graph in several parts. Calibrated with
# layout_quality on sample graphs (ADR 0017): on 25 components plus isolates,
# ForceAtlas2 at gravity 1 left 92% of nodes overlapping in a clump while
# repulsion flung the small parts outwards; gravity 10 brought it to 16%.
_FA2_FRAGMENTED_GRAVITY = (2.0, 10.0)   # clamp for 2 * log2(components)
# Spring's 'energy' method is the one whose gravity holds components together;
# on the same graph it took overlap from 92% to 0% at gravity 3.
_SPRING_FRAGMENTED_GRAVITY = 3.0
# On trees, long spring runs fold the branches onto each other: on five
# trees of 120-500 nodes, 1000 iterations left 65-93% of nodes overlapping and
# 50 iterations 7-77%, always better. networkx's own default is 50.
_SPRING_FOREST_ITERATIONS = 50


def _iterations_by_size(n):
    if n < 500:
        return 1000, 1e-6  # high iterations, strict threshold
    if n < 2000:
        return 500, 1e-5
    return 200, 1e-4


def tune_spring(G, profile):
    """Iterations by graph size, node spacing, and gravity for split graphs.

    `k` is the optimal distance between nodes; 2.0/sqrt(N) is a little wider than
    networkx's own 1/sqrt(N), which reduces overlap on the graphs this app sees.
    """
    n = profile.nodes
    iterations, threshold = _iterations_by_size(n)
    params = {
        "k": 2.0 / math.sqrt(n) if n > 0 else None,
        "iterations": iterations,
        "threshold": threshold,
        "seed": 42,
    }
    notes = []
    if profile.is_forest and n > 2:
        params["iterations"] = _SPRING_FOREST_ITERATIONS
        notes.append(
            f"`iterations` {iterations} -> {_SPRING_FOREST_ITERATIONS}, because the "
            "graph is a tree; longer runs fold its branches onto each other."
        )
    if profile.fragmented:
        params["method"] = "energy"
        params["gravity"] = _SPRING_FRAGMENTED_GRAVITY
        notes.append(
            f"`method`='energy' with `gravity` {_SPRING_FRAGMENTED_GRAVITY:g}, because "
            f"the graph has {profile.components} separate parts that would otherwise "
            "drift apart and squeeze the rest together."
        )
    return params, notes


def tune_forceatlas2(G, profile):
    """Iteration count, repulsion and gravity from the graph's profile.

    Each iteration computes dense pairwise repulsion (O(N^2), no Barnes-Hut
    approximation), so the iteration count directly dominates upload latency on
    large graphs. The floor/cap stay well above networkx's own default of 100 for
    layout quality, but far below the 1000-5000 range that made large uploads
    extremely slow.
    """
    n = profile.nodes
    # Average degree stands in for local clumping: the tighter the graph pulls
    # itself, the more repulsion it needs to stay readable. With weights the
    # pull is the weighted degree (weights arrive median-normalized).
    pull = profile.avg_strength if profile.weighted else profile.avg_degree
    params = {
        "max_iter": max(200, min(2000, n)),
        "scaling_ratio": max(2.0, min(10.0, pull * 0.5)),
        "gravity": 1.0,
        "jitter_tolerance": 1.0,
        "seed": 42,
    }
    notes = []
    if profile.weighted and abs(profile.avg_strength - profile.avg_degree) > 0.5:
        notes.append(
            f"`scaling_ratio` {params['scaling_ratio']:.3g} from the weighted degree "
            f"({profile.avg_strength:.3g}) rather than the plain degree."
        )
    if profile.fragmented:
        low, high = _FA2_FRAGMENTED_GRAVITY
        params["gravity"] = max(low, min(high, 2.0 * math.log2(profile.components)))
        notes.append(
            f"`gravity` 1 -> {params['gravity']:.3g}, because the graph has "
            f"{profile.components} separate parts ({profile.isolates} isolated "
            "nodes) that repulsion would push to the edges."
        )
    return params, notes


def tune_arf(G, profile):
    """ARF is iterative like spring; nx's other defaults are reasonable as-is."""
    # Seeded like the tool's default, so a search baseline reproduces the layout.
    return {"max_iter": _iterations_by_size(profile.nodes)[0], "seed": 42}, []


@register(
    "spring",
    params={
        "k", "pos", "fixed", "iterations", "threshold", "weight",
        "scale", "center", "seed", "method", "gravity",
    },
    weight_role=WeightRole.STRENGTH,
    tune=tune_spring,
    aliases=("fruchterman_reingold",),
    knobs=(
        # Direction 0: try both ways. Spacing interacts with the renderer's
        # rescaling, and on a 300-node tree 1000 iterations left 88% of nodes
        # overlapping where 50 left 12%, so neither knob has one right way.
        Knob("k", 0.25, 4.0, relative=True,
             fixes={"node_overlap": 0, "outliers_compress_core": +1}),
        Knob("gravity", 0.5, 20.0, requires={"method": "energy"},
             fixes={"outliers_compress_core": +1, "clumped": +1, "node_overlap": +1}),
        Knob("iterations", 50, 3000, integer=True,
             fixes={"node_overlap": 0, "uneven_edge_lengths": +1}),
    ),
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
    knobs=(
        Knob("gravity", 0.1, 30.0,
             fixes={"node_overlap": +1, "clumped": +1, "outliers_compress_core": +1}),
        Knob("scaling_ratio", 1.0, 100.0,
             fixes={"node_overlap": 0, "outliers_compress_core": -1}),
        Knob("strong_gravity", toggle=True,
             fixes={"outliers_compress_core": +1, "clumped": +1}),
        # Halving max_iter on a 500-node BA graph cut overlap from 17% to 7%:
        # longer runs keep contracting dense regions.
        Knob("max_iter", 100, 3000, integer=True, fixes={"node_overlap": 0}),
    ),
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
    knobs=(
        Knob("scaling", 0.2, 20.0, fixes={"node_overlap": +1, "clumped": +1}),
        Knob("a", 1.1, 10.0, fixes={"outliers_compress_core": +1}),
    ),
)
def arf(G, params):
    """Attractive-repulsive force layout. nx.arf_layout has no weight concept."""
    return nx.arf_layout(G, **params)
