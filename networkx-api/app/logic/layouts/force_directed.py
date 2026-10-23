"""Force-directed layouts: spring, forceatlas2, arf.

Each function is the whole of that layout: its networkx call, the parameters it
accepts, how they are tuned to graph size, and what a weight means to it.
"""

import math

import networkx as nx
import numpy as np

from .base import Knob, WeightRole, register
from .components import layout_by_part

# Graph attribute set by `prepare_forceatlas2`: `node_size` holds radii in drawn
# (renderer) units rather than in the layout's own coordinate units.
RENDERED_RADII = "node_size_in_rendered_units"


# How far gravity is raised for a graph in several parts. Calibrated with
# layout_quality on sample graphs (ADR 0017): on 25 components plus isolates,
# ForceAtlas2 at gravity 1 left 92% of nodes overlapping in a clump while
# repulsion flung the small parts outwards; gravity 10 brought it to 16%.
_FA2_FRAGMENTED_GRAVITY = (2.0, 10.0)  # clamp for 2 * log2(components)
# N^2 x iterations allowed by default; at the measured 50-80 ns per N^2 per
# iteration, about half a minute. Quality gained little beyond it (ADR 0033).
_FA2_ITERATION_BUDGET = 500_000_000
# Floor, so a very large graph still settles instead of staying near its
# random start; past the size where it binds the budget no longer holds.
_FA2_MIN_ITER = 50
# A graph in several parts is laid out part by part and packed (ADR 0041).
# Each part is solved alone, so the largest part's size, not the graph's, sets
# the work: N^2 x iterations for it is capped like ForceAtlas2's (ADR 0033).
# At about 40 ns per N^2 per iteration on the energy method, some 20 seconds.
_SPRING_PART_ITERATION_BUDGET = 500_000_000
# Parts solved by the energy method stop here first, and keep this state when
# it measures better than the full run. On the largest part of the syllabus
# backbone (ADR 0040) 50 iterations scored 3.0, 100 scored 3.9, 500 4.2: a
# converged run stretches its long strands and crushes the dense middle. On
# a dense part (concert, mean degree 15) the full run was better.
_SPRING_SHORT_ITERATIONS = 50
# networkx's method='auto' switches from 'force' to 'energy' at this size.
_SPRING_ENERGY_FROM = 500
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
    """Iterations by size, node spacing, and part-by-part packing for split graphs.

    `k` is the optimal distance between nodes; 2.0/sqrt(N) is a little wider than
    networkx's own 1/sqrt(N), which reduces overlap on the graphs this app sees.
    """
    n = profile.nodes
    packed = profile.fragmented
    # Packed, every part is solved alone and the largest one is the work.
    sized_by = round(profile.largest_component_share * n) if packed else n
    iterations, threshold = _iterations_by_size(sized_by)
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
    if packed:
        params["pack_components"] = True
        notes.append(
            f"`pack_components` on, because the graph has {profile.components} "
            "separate parts: each is laid out on its own and placed around the "
            "largest, so the parts stay apart and each reads as a group."
        )
        cap = max(
            _SPRING_SHORT_ITERATIONS,
            _SPRING_PART_ITERATION_BUDGET // max(sized_by * sized_by, 1),
        )
        if params["iterations"] > cap:
            params["iterations"] = cap
            notes.append(
                f"`iterations` {cap}, fewer than usual: the largest part has "
                f"{sized_by} nodes and each iteration compares every pair of them."
            )
        if sized_by >= _SPRING_ENERGY_FROM and params["iterations"] > (
            _SPRING_SHORT_ITERATIONS
        ):
            notes.append(
                f"`iterations` is an upper bound for parts of {_SPRING_ENERGY_FROM}+ "
                f"nodes: such a part keeps its state after {_SPRING_SHORT_ITERATIONS} "
                "iterations when that measures more readable than the full run."
            )
    return params, notes


def fa2_iterations(n):
    """Default ForceAtlas2 iteration count for `n` nodes, and whether the budget cut it.

    Each iteration computes dense pairwise repulsion (O(N^2), no Barnes-Hut
    approximation), so the total cost is about N^2 x iterations. Below the size
    where `_FA2_ITERATION_BUDGET` binds, the size rule stands; above it the
    count shrinks so the first layout of a large upload takes tens of seconds,
    not tens of minutes (ADR 0033).
    """
    by_size = max(200, min(2000, n))
    by_budget = max(_FA2_MIN_ITER, _FA2_ITERATION_BUDGET // max(n * n, 1))
    return min(by_size, by_budget), by_budget < by_size


def fa2_budget_floor_nodes():
    """Smallest node count at which even `_FA2_MIN_ITER` iterations exceed the budget.

    From here on a default ForceAtlas2 run costs more than the budget allows,
    which is what makes a network "large" (ADR 0034).
    """
    return math.isqrt(_FA2_ITERATION_BUDGET // _FA2_MIN_ITER) + 1


def tune_forceatlas2(G, profile):
    """Iteration count, repulsion and gravity from the graph's profile."""
    n = profile.nodes
    # Average degree stands in for local clumping: the tighter the graph pulls
    # itself, the more repulsion it needs to stay readable. With weights the
    # pull is the weighted degree (weights arrive median-normalized).
    pull = profile.avg_strength if profile.weighted else profile.avg_degree
    max_iter, budgeted = fa2_iterations(n)
    params = {
        "max_iter": max_iter,
        "scaling_ratio": max(2.0, min(10.0, pull * 0.5)),
        "gravity": 1.0,
        "jitter_tolerance": 1.0,
        "seed": 42,
    }
    notes = []
    if budgeted:
        notes.append(
            f"`max_iter` {max_iter}, fewer than usual: each iteration compares "
            f"every pair of the {n} nodes, and on graphs this size more "
            "iterations add minutes without improving the drawing."
        )
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
        "k",
        "pos",
        "fixed",
        "iterations",
        "threshold",
        "weight",
        "scale",
        "center",
        "seed",
        "method",
        "gravity",
    },
    app_params={"pack_components"},
    weight_role=WeightRole.STRENGTH,
    tune=tune_spring,
    aliases=("fruchterman_reingold",),
    knobs=(
        # Direction 0: try both ways. Spacing interacts with the renderer's
        # rescaling, and on a 300-node tree 1000 iterations left 88% of nodes
        # overlapping where 50 left 12%, so neither knob has one right way.
        Knob(
            "k",
            0.25,
            4.0,
            relative=True,
            fixes={"node_overlap": 0, "outliers_compress_core": +1},
        ),
        Knob(
            "gravity",
            0.5,
            20.0,
            requires={"method": "energy"},
            fixes={"outliers_compress_core": +1, "clumped": +1, "node_overlap": +1},
        ),
        Knob(
            "iterations",
            50,
            3000,
            integer=True,
            fixes={"node_overlap": 0, "uneven_edge_lengths": +1},
        ),
    ),
)
def spring(G, params):
    """Fruchterman-Reingold. Weights are attraction strength.

    With `pack_components`, each connected part is laid out on its own and the
    parts are packed around the largest (ADR 0041), unless starting positions
    were given: then they decide where everything goes.
    """
    params = dict(params)
    if params.pop("pack_components", False) and params.get("pos") is None:
        total = G.number_of_nodes()
        return layout_by_part(G, lambda part: _spring_part(part, params, total))
    return nx.spring_layout(G, **params)


def _spring_part(H, params, total):
    """Spring on one part of a packed graph of `total` nodes.

    `k` is meant for the whole graph, whose layout spans the same unit square
    as each part's, so it is scaled up by sqrt(total / part size). A part solved
    by the energy method runs `_SPRING_SHORT_ITERATIONS` first, continues to
    `iterations`, and keeps whichever state `layout_quality` scores better.
    """
    from ..common_utils import calculate_smart_node_size
    from ..layout_quality import evaluate

    m = H.number_of_nodes()
    params = dict(params)
    if params.get("k") is not None:
        params["k"] = params["k"] * math.sqrt(total / m)
    method = params.get("method") or "auto"
    energy = method == "energy" or (method == "auto" and m >= _SPRING_ENERGY_FROM)
    iterations = params.get("iterations", _SPRING_SHORT_ITERATIONS)
    if not energy or iterations <= _SPRING_SHORT_ITERATIONS:
        return nx.spring_layout(H, **params)

    # Unscaled, so the continued run starts exactly where the short one stopped.
    params.update(method="energy", scale=None, center=None)
    short = nx.spring_layout(H, **{**params, "iterations": _SPRING_SHORT_ITERATIONS})
    full = nx.spring_layout(
        H,
        **{**params, "iterations": iterations - _SPRING_SHORT_ITERATIONS, "pos": short},
    )
    size = calculate_smart_node_size(total)["default"]
    return min((short, full), key=lambda pos: evaluate(pos, H.edges(), size).score)


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
        "pos",
        "max_iter",
        "jitter_tolerance",
        "scaling_ratio",
        "gravity",
        "distributed_action",
        "strong_gravity",
        "node_mass",
        "node_size",
        "weight",
        "linlog",
        "seed",
    },
    weight_role=WeightRole.STRENGTH,
    tune=tune_forceatlas2,
    prepare=prepare_forceatlas2,
    aliases=("forceatlas2_layout", "force-directed", "force_directed"),
    knobs=(
        Knob(
            "gravity",
            0.1,
            30.0,
            fixes={"node_overlap": +1, "clumped": +1, "outliers_compress_core": +1},
        ),
        Knob(
            "scaling_ratio",
            1.0,
            100.0,
            fixes={"node_overlap": 0, "outliers_compress_core": -1},
        ),
        Knob(
            "strong_gravity",
            toggle=True,
            fixes={"outliers_compress_core": +1, "clumped": +1},
        ),
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
