"""Push overlapping nodes apart after a force layout (ADR 0048).

No layout parameter can make room for every node: the renderer stretches any
layout back to the same square (ADR 0017), so spring's `k` at 4x left a
3,383-node graph exactly as overlapped (93%). The fix has to work in the space
the user sees, with the radii the nodes are drawn at. Each round finds the pairs
that touch and moves both halves apart; renormalizing after every round keeps
the result inside the drawn square, as the renderer would.
"""

from typing import Dict, Hashable, Mapping, Tuple, Union

import numpy as np
from scipy.spatial import cKDTree

from ..layout_quality import (
    TARGET_EXTENT,
    normalize_points_like_renderer,
    radius_from_size,
)

Position = Tuple[float, float]

# Upper bound on rounds; the loop stops as soon as nothing touches. On the
# 3,383-node syllabus kNN graph under spring, overlap fell 0.93 -> 0.47 at 60
# rounds, 0.30 at 150, 0.13 at 400 (2 s on the host), while edge locality moved
# only 0.092 -> 0.104: the groups keep their place and shape.
MAX_ROUNDS = 400
# Nodes are pushed until their circles are this much further apart than
# touching, so a pair does not re-touch after the next renormalization.
_PADDING = 1.05
# Share of the remaining gap closed per round. Moving all the way overshoots in
# crowded regions, where one node is pushed by many neighbours at once.
_STEP = 0.5


def separate_overlaps(
    pos: Mapping[Hashable, Position],
    sizes: Union[float, Mapping[Hashable, float]],
    max_rounds: int = MAX_ROUNDS,
) -> Dict[Hashable, Position]:
    """Move nodes apart until their drawn circles stop touching, or rounds run out.

    Args:
        pos: Layout coordinates, in the layout's own units.
        sizes: Node size (an area, as drawn) per node, or one size for all.
        max_rounds: Upper bound on push rounds.

    Returns:
        New positions in the same coordinate frame (same bounding box) as `pos`,
        so the layout's own scale is kept for warm starts and caches.
    """
    nodes = list(pos)
    if len(nodes) < 2:
        return dict(pos)
    points = np.array([pos[v] for v in nodes], dtype=float)
    low = points.min(axis=0)
    span = points.max(axis=0) - low
    span[span <= 0] = 1.0

    if isinstance(sizes, Mapping):
        radii = np.array([radius_from_size(sizes.get(v, 0.0)) for v in nodes])
    else:
        radii = np.full(len(nodes), radius_from_size(sizes))
    if not radii.any():
        return dict(pos)
    reach = 2.0 * radii.max() * _PADDING

    drawn = normalize_points_like_renderer(points)
    for _ in range(max_rounds):
        pairs = cKDTree(drawn).query_pairs(reach, output_type="ndarray")
        if len(pairs) == 0:
            break
        a, b = pairs[:, 0], pairs[:, 1]
        delta = drawn[b] - drawn[a]
        dist = np.linalg.norm(delta, axis=1)
        gap = (radii[a] + radii[b]) * _PADDING - dist
        touching = gap > 0
        if not touching.any():
            break
        a, b, delta, dist, gap = (
            a[touching],
            b[touching],
            delta[touching],
            dist[touching],
            gap[touching],
        )
        # Coincident nodes have no direction to move in; give each pair a fixed
        # one so the result stays deterministic.
        stacked = dist < 1e-9
        if stacked.any():
            angle = (a[stacked] * 0.618034 + b[stacked]) * 2.0 * np.pi
            delta[stacked] = np.column_stack((np.cos(angle), np.sin(angle)))
            dist[stacked] = 1.0
        push = (gap * _STEP / 2.0 / dist)[:, None] * delta
        np.add.at(drawn, a, -push)
        np.add.at(drawn, b, push)
        drawn = normalize_points_like_renderer(drawn)

    unit = (drawn + TARGET_EXTENT) / (2.0 * TARGET_EXTENT)
    restored = low + unit * span
    return {v: (float(x), float(y)) for v, (x, y) in zip(nodes, restored)}
