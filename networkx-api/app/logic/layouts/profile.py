"""What a graph looks like to a layout, computed once before tuning.

`tune` used to see only the node count (and, for ForceAtlas2, the average
degree). The properties that decide how a layout goes wrong — disconnected
parts flung to the edges, a hub-dominated degree spread, the scale of the
weights — were invisible to it. `GraphProfile` collects them in one pass so each
layout's `tune` can say which of them moved a parameter (ADR 0017).

The structural flags (planar, bipartite, forest) feed `layout_profile`, which
names the layouts that fit this graph.
"""

import statistics
from dataclasses import asdict, dataclass
from typing import Optional

import networkx as nx

# Planarity and bipartiteness are linear-time, but not free; above this size
# they are reported as unknown rather than slowing every layout run.
STRUCTURE_CHECK_LIMIT = 5_000


@dataclass(frozen=True)
class GraphProfile:
    nodes: int
    edges: int
    density: float
    avg_degree: float
    degree_cv: float                # spread of degrees; high = hub-dominated
    components: int                 # weakly connected, for directed graphs
    largest_component_share: float  # nodes in the largest component / nodes
    isolates: int
    weighted: bool                  # the layout will read a weight
    avg_strength: Optional[float]   # average weighted degree (weights as read)
    weight_ratio: Optional[float]   # max / min positive weight
    is_forest: bool
    is_planar: Optional[bool]
    is_bipartite: Optional[bool]

    @property
    def fragmented(self) -> bool:
        """Several parts, or isolates, that repulsion will push to the edges."""
        return self.components > 1

    def as_dict(self) -> dict:
        data = asdict(self)
        for key, value in data.items():
            if isinstance(value, float):
                data[key] = round(value, 3)
        return data


def profile_graph(G, weight: Optional[str] = None) -> GraphProfile:
    """Profile `G` as a layout will see it (weighted by `weight`, if given)."""
    n = G.number_of_nodes()
    m = G.number_of_edges()
    U = G.to_undirected(as_view=True) if G.is_directed() else G

    degrees = [d for _node, d in U.degree()]
    avg_degree = (2.0 * m / n) if n else 0.0
    degree_cv = (
        statistics.pstdev(degrees) / avg_degree if n > 1 and avg_degree > 0 else 0.0
    )

    component_sizes = [len(c) for c in nx.connected_components(U)] if n else []
    positive = (
        [w for _u, _v, w in U.edges(data=weight) if w is not None and w > 0]
        if weight
        else []
    )

    small_enough = n <= STRUCTURE_CHECK_LIMIT
    return GraphProfile(
        nodes=n,
        edges=m,
        density=nx.density(U) if n > 1 else 0.0,
        avg_degree=avg_degree,
        degree_cv=degree_cv,
        components=len(component_sizes),
        largest_component_share=(max(component_sizes) / n) if n else 0.0,
        isolates=sum(1 for d in degrees if d == 0),
        weighted=bool(positive),
        avg_strength=(2.0 * sum(positive) / n) if positive and n else None,
        weight_ratio=(max(positive) / min(positive)) if positive else None,
        is_forest=nx.is_forest(U) if n else False,
        is_planar=nx.check_planarity(U)[0] if small_enough and n else None,
        is_bipartite=nx.is_bipartite(U) if small_enough and n else None,
    )


# Kamada-Kawai holds an n x n distance matrix and solves an O(n^2) problem
# per step; above this it is slow enough to be the wrong default.
KAMADA_KAWAI_LIMIT = 300


def recommend_layouts(profile: GraphProfile) -> list:
    """Layouts that suit this graph, best first, each with its reason.

    Rules over the profile only. Which layout the user *wants* is still theirs
    to say; this says which ones the structure supports and why.
    """
    fits = []
    if profile.is_forest and profile.nodes > 1:
        fits.append(
            ("bfs", "the graph is a tree/forest, so BFS levels show its hierarchy "
             "(pass the root as `start`)")
        )
    fits.append(
        ("forceatlas2", "general-purpose; separates communities and scales to large graphs")
    )
    if profile.nodes <= KAMADA_KAWAI_LIMIT and profile.components == 1:
        fits.append(
            ("kamada_kawai", f"small and connected ({profile.nodes} nodes), so its "
             "O(n^2) cost is affordable and it keeps graph distances faithfully")
        )
    fits.append(("spring", "even spacing with milder clustering than ForceAtlas2"))
    if profile.is_bipartite and profile.edges > 0:
        fits.append(
            ("bipartite", "the graph is two-colourable; a node attribute naming the "
             "two sides is needed as `partition_attribute`")
        )
    if profile.is_planar and not profile.is_forest and profile.edges > 0:
        fits.append(("planar", "the graph is planar, so it can be drawn with no crossings"))
    return [{"layout": name, "reason": reason} for name, reason in fits]


def unsuitable_layouts(profile: GraphProfile) -> list:
    """Layouts that will fail or mislead on this graph, with the reason."""
    bad = []
    if profile.is_planar is False:
        bad.append({"layout": "planar", "reason": "the graph is not planar; it will fail"})
    if profile.nodes > KAMADA_KAWAI_LIMIT:
        bad.append(
            {"layout": "kamada_kawai", "reason": f"{profile.nodes} nodes; O(n^2) makes it slow"}
        )
    if profile.components > 1:
        bad.append(
            {"layout": "kamada_kawai", "reason": "disconnected graphs have no distance "
             "between components, so parts are placed arbitrarily"}
        )
    if profile.density > 0.3 and profile.nodes > 30:
        bad.append(
            {"layout": "spectral", "reason": "dense graphs tend to collapse onto a line"}
        )
    return bad
