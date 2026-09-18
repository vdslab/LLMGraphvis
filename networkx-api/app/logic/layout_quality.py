"""How readable a drawn layout is, measured in the space the user actually sees.

The agent cannot look at the canvas, and a screenshot would cost far more tokens
than it is worth. It does not need one: the frontend fits its viewBox to the
renderer-normalized coordinates and draws each node with radius
`sqrt(size * 10 / pi)` in those same units, so overlap, crossings and spread
computed here are what is on screen, whatever the size of the panel.

That only holds while both sides use one transform, so `normalize_like_renderer`
is the transform — `visualization_builder` calls it rather than keeping its own.

The metrics are deliberately cheap (nothing needs all-pairs shortest paths):
they run on every `visualization_generate`, and in a loop while
`layout_optimizer` scores candidates. See ADR 0017.
"""

import math
from dataclasses import dataclass, field
from typing import Dict, Hashable, Iterable, List, Mapping, Optional, Tuple, Union

import numpy as np
from scipy.spatial import cKDTree

# Half the side of the square every layout is drawn in.
TARGET_EXTENT = 1000.0

# Crossings are counted exactly up to this many edges (E^2/2 segment tests,
# chunked); above it a fixed number of random edge pairs is sampled.
EXACT_CROSSING_EDGE_LIMIT = 2000
CROSSING_SAMPLE_PAIRS = 200_000
_CROSSING_CHUNK = 500_000

# Neighbours examined per node for overlap. A node overlapping one that is not
# among its nearest few would need an extreme size difference.
_OVERLAP_NEIGHBOURS = 8

# Below this many nodes the percentile/grid metrics say nothing useful.
MIN_NODES_FOR_SPREAD = 20

# When a metric counts as a problem worth naming. `diagnose` reads these; the
# layout knobs (logic/layouts) name the same labels to say what fixes them.
THRESHOLDS = {
    "node_overlap": 0.05,           # share of nodes touching another node
    "outliers_compress_core": 0.15,  # core_extent below this
    "uneven_edge_lengths": 1.0,      # edge_length_cv above this
    "distorted_aspect": 3.0,         # aspect above this
    "many_crossings": 3.0,           # crossings_per_edge above this
    "clumped": 0.15,                 # occupancy below this
}

# Weights of the penalty `score` sums; lower is better. Overlap dominates
# because a hidden node is lost information, while crossings are partly
# inherent to the graph and only compared between candidates.
SCORE_WEIGHTS = {
    "node_overlap": 4.0,
    "crossings": 1.0,
    "edge_length_cv": 0.5,
    "core_compression": 2.0,
    "aspect": 0.5,
}

Position = Tuple[float, float]


def radius_from_size(size: float) -> float:
    """The drawn radius of a node of `size` (an area), as NetworkGraph.jsx draws it."""
    return math.sqrt(max(float(size), 0.0) * 10.0 / math.pi)


def normalize_like_renderer(
    pos: Mapping[Hashable, Position],
) -> Dict[Hashable, Position]:
    """Map positions onto [-1000, 1000] per axis, exactly as the renderer does.

    x and y are scaled independently, so the aspect ratio is *not* preserved;
    `evaluate` reports the resulting distortion as `aspect`. A degenerate axis
    (every node at one coordinate) keeps a range of 1 and so lands on -1000.
    """
    if not pos:
        return {}
    xs = [p[0] for p in pos.values()]
    ys = [p[1] for p in pos.values()]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    range_x = (max_x - min_x) if (max_x - min_x) > 0 else 1.0
    range_y = (max_y - min_y) if (max_y - min_y) > 0 else 1.0
    span = 2 * TARGET_EXTENT
    return {
        node: (
            ((x - min_x) / range_x - 0.5) * span,
            ((y - min_y) / range_y - 0.5) * span,
        )
        for node, (x, y) in pos.items()
    }


@dataclass
class QualityReport:
    node_count: int
    edge_count: int
    node_overlap: float
    crossings: int
    crossings_per_edge: float
    crossings_sampled: bool
    edge_length_cv: Optional[float]
    core_extent: Optional[float]
    aspect: float
    occupancy: Optional[float]
    issues: List[str] = field(default_factory=list)
    score: float = 0.0

    def as_dict(self) -> dict:
        """The compact form sent to the model (about 60 tokens)."""

        def r(value):
            return round(value, 3) if isinstance(value, float) else value

        return {
            "node_overlap": r(self.node_overlap),
            "crossings": self.crossings,
            "crossings_per_edge": r(self.crossings_per_edge),
            "crossings_sampled": self.crossings_sampled,
            "edge_length_cv": r(self.edge_length_cv),
            "core_extent": r(self.core_extent),
            "aspect": r(self.aspect),
            "occupancy": r(self.occupancy),
            "score": r(self.score),
            "issues": list(self.issues),
        }


def evaluate(
    pos: Mapping[Hashable, Position],
    edges: Iterable[Tuple[Hashable, Hashable]],
    sizes: Union[float, Mapping[Hashable, float]],
    seed: int = 0,
) -> QualityReport:
    """Measure a layout as drawn.

    Args:
        pos: Raw layout coordinates (before renderer normalization).
        edges: The drawn edges, as node-id pairs. Self-loops are ignored.
        sizes: Node size (an area, as stored in the visualization) for every
            node, or one size for all.
        seed: Seed for crossing sampling on large graphs.
    """
    nodes = list(pos)
    n = len(nodes)
    index = {node: i for i, node in enumerate(nodes)}
    edge_idx = np.array(
        [
            (index[u], index[v])
            for u, v in edges
            if u in index and v in index and u != v
        ],
        dtype=np.int64,
    ).reshape(-1, 2)

    raw = np.array([pos[node] for node in nodes], dtype=float).reshape(-1, 2)
    aspect = _aspect(raw)

    normalized = normalize_like_renderer(pos)
    points = np.array([normalized[node] for node in nodes], dtype=float).reshape(-1, 2)

    if isinstance(sizes, Mapping):
        radii = np.array([radius_from_size(sizes.get(node, 0.0)) for node in nodes])
    else:
        radii = np.full(n, radius_from_size(sizes))

    crossings, per_edge, sampled = _crossings(points, edge_idx, seed)
    report = QualityReport(
        node_count=n,
        edge_count=len(edge_idx),
        node_overlap=_node_overlap(points, radii),
        crossings=crossings,
        crossings_per_edge=per_edge,
        crossings_sampled=sampled,
        edge_length_cv=_edge_length_cv(points, edge_idx),
        core_extent=_core_extent(points),
        aspect=aspect,
        occupancy=_occupancy(points),
    )
    report.issues = diagnose(report)
    report.score = score(report)
    return report


def diagnose(report: QualityReport) -> List[str]:
    """Name the problems a reader would notice, most damaging first."""
    t = THRESHOLDS
    issues = []
    if report.node_overlap > t["node_overlap"]:
        issues.append("node_overlap")
    if report.core_extent is not None and report.core_extent < t["outliers_compress_core"]:
        issues.append("outliers_compress_core")
    if report.occupancy is not None and report.occupancy < t["clumped"]:
        issues.append("clumped")
    if report.crossings_per_edge > t["many_crossings"]:
        issues.append("many_crossings")
    if report.edge_length_cv is not None and report.edge_length_cv > t["uneven_edge_lengths"]:
        issues.append("uneven_edge_lengths")
    if report.aspect > t["distorted_aspect"]:
        issues.append("distorted_aspect")
    return issues


def score(report: QualityReport) -> float:
    """A single penalty for ranking layouts of the same graph; lower is better.

    Each term is squashed to roughly [0, 1] before weighting, so no metric can
    swamp the others by its units. It is only meaningful for comparing layouts
    of one graph, never across graphs.
    """
    w = SCORE_WEIGHTS
    total = w["node_overlap"] * report.node_overlap
    total += w["crossings"] * min(report.crossings_per_edge / 10.0, 1.0)
    if report.edge_length_cv is not None:
        total += w["edge_length_cv"] * min(report.edge_length_cv, 2.0) / 2.0
    if report.core_extent is not None:
        floor = 0.3
        total += w["core_compression"] * max(0.0, floor - report.core_extent) / floor
    total += w["aspect"] * min(max(report.aspect - 1.0, 0.0) / 4.0, 1.0)
    return total


# --- metrics -----------------------------------------------------------------


def _aspect(raw: np.ndarray) -> float:
    """Longer side over shorter side of the raw bounding box (1 = square).

    The renderer stretches both sides to the same length, so this is how much
    the drawing is distorted. Capped so a line layout reports a finite number.
    """
    if len(raw) < 2:
        return 1.0
    width, height = np.ptp(raw[:, 0]), np.ptp(raw[:, 1])
    longer, shorter = max(width, height), min(width, height)
    if longer == 0:
        return 1.0
    if shorter <= longer / 100.0:
        return 100.0
    return float(longer / shorter)


def _node_overlap(points: np.ndarray, radii: np.ndarray) -> float:
    """Share of nodes whose circle touches another node's circle."""
    n = len(points)
    if n < 2:
        return 0.0
    k = min(_OVERLAP_NEIGHBOURS + 1, n)
    distances, neighbours = cKDTree(points).query(points, k=k)
    # Column 0 is the node itself.
    distances, neighbours = distances[:, 1:], neighbours[:, 1:]
    touching = distances < (radii[:, None] + radii[neighbours])
    overlapping = touching.any(axis=1)
    return float(overlapping.mean())


def _edge_length_cv(points: np.ndarray, edges: np.ndarray) -> Optional[float]:
    """Coefficient of variation of drawn edge lengths (0 = all equal)."""
    if len(edges) < 2:
        return None
    lengths = np.linalg.norm(points[edges[:, 0]] - points[edges[:, 1]], axis=1)
    mean = lengths.mean()
    if mean == 0:
        return None
    return float(lengths.std() / mean)


def _core_extent(points: np.ndarray) -> Optional[float]:
    """Area of the 5–95 percentile box over the drawing's area.

    A few far-away nodes (isolates, small components flung out by repulsion)
    set the bounding box, and the renderer fits that box — so everything else
    is squeezed into a corner. That shows up here as a small value; an even
    spread gives about 0.8.
    """
    if len(points) < MIN_NODES_FOR_SPREAD:
        return None
    low = np.percentile(points, 5, axis=0)
    high = np.percentile(points, 95, axis=0)
    full = np.ptp(points, axis=0)
    if full[0] == 0 or full[1] == 0:
        return 0.0
    return float(np.prod((high - low) / full))


def _occupancy(points: np.ndarray) -> Optional[float]:
    """Share of a sqrt(n) x sqrt(n) grid that holds at least one node.

    Nodes scattered uniformly fill about 63% of the cells; nodes piled into a
    few clumps fill far fewer.
    """
    n = len(points)
    if n < MIN_NODES_FOR_SPREAD:
        return None
    side = max(2, min(50, int(math.ceil(math.sqrt(n)))))
    span = np.ptp(points, axis=0)
    span[span == 0] = 1.0
    cells = np.floor((points - points.min(axis=0)) / span * side).astype(int)
    cells = np.clip(cells, 0, side - 1)
    occupied = len({(int(a), int(b)) for a, b in cells})
    return occupied / float(side * side)


def _crossings(
    points: np.ndarray, edges: np.ndarray, seed: int
) -> Tuple[int, float, bool]:
    """Proper crossings between edges that share no endpoint.

    Returns `(count, crossings_per_edge, sampled)`. Beyond
    EXACT_CROSSING_EDGE_LIMIT edges the count is extrapolated from a random
    sample of edge pairs, so it is an estimate.
    """
    m = len(edges)
    if m < 2:
        return 0, 0.0, False

    if m <= EXACT_CROSSING_EDGE_LIMIT:
        i, j = np.triu_indices(m, k=1)
        count = 0
        for start in range(0, len(i), _CROSSING_CHUNK):
            a, b = i[start : start + _CROSSING_CHUNK], j[start : start + _CROSSING_CHUNK]
            count += int(_crossing_mask(points, edges[a], edges[b]).sum())
        return count, 2.0 * count / m, False

    rng = np.random.default_rng(seed)
    a = rng.integers(0, m, CROSSING_SAMPLE_PAIRS)
    b = rng.integers(0, m, CROSSING_SAMPLE_PAIRS)
    keep = a != b
    a, b = a[keep], b[keep]
    ea, eb = edges[a], edges[b]
    disjoint = _disjoint(ea, eb)
    if not disjoint.any():
        return 0, 0.0, True
    crossing_rate = _crossing_mask(points, ea[disjoint], eb[disjoint]).mean()

    degrees = np.bincount(edges.ravel(), minlength=len(points))
    adjacent_pairs = int((degrees * (degrees - 1) // 2).sum())
    candidate_pairs = m * (m - 1) // 2 - adjacent_pairs
    count = int(round(crossing_rate * max(candidate_pairs, 0)))
    return count, 2.0 * count / m, True


def _disjoint(ea: np.ndarray, eb: np.ndarray) -> np.ndarray:
    return (
        (ea[:, 0] != eb[:, 0])
        & (ea[:, 0] != eb[:, 1])
        & (ea[:, 1] != eb[:, 0])
        & (ea[:, 1] != eb[:, 1])
    )


def _crossing_mask(points: np.ndarray, ea: np.ndarray, eb: np.ndarray) -> np.ndarray:
    """True where segment pairs cross properly and share no endpoint."""
    p1, p2 = points[ea[:, 0]], points[ea[:, 1]]
    q1, q2 = points[eb[:, 0]], points[eb[:, 1]]

    def orient(a, b, c):
        return (b[:, 0] - a[:, 0]) * (c[:, 1] - a[:, 1]) - (b[:, 1] - a[:, 1]) * (
            c[:, 0] - a[:, 0]
        )

    d1, d2 = orient(p1, p2, q1), orient(p1, p2, q2)
    d3, d4 = orient(q1, q2, p1), orient(q1, q2, p2)
    return _disjoint(ea, eb) & (d1 * d2 < 0) & (d3 * d4 < 0)
