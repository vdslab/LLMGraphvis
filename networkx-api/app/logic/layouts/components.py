"""Lay out each connected part on its own, then pack the parts around the largest.

A force layout of a graph in many parts decides where the parts go only by the
balance of gravity and repulsion: small parts end up between the branches of
the largest one, or flung to the edges. Packing gives the familiar picture
instead — the largest part in the middle, the others around it, each readable
as a group of its own (ADR 0041).

Distances here are in units of a part's median drawn edge length, so every part
is drawn at the same edge length whatever scale its layout came out at.
"""

import math
from typing import Callable, Dict, Hashable, List, Tuple

import networkx as nx
import numpy as np
from scipy import ndimage
from scipy.signal import fftconvolve

# Clearance between two parts, in edge lengths. With 1 the small parts of the
# syllabus backbone (ADR 0040) ran together into one band; 2 kept each apart.
PART_GAP = 2.0
# Each part reserves its outline with concavities narrower than this share of
# its radius filled in. Without it, small parts settled between the branches of
# the largest one (the whole read as one even disc), and parts interlocked so
# that their edges crossed.
OUTLINE_CLOSING = 0.2
# Grid resolution, in edge lengths. Finer only slows the packing down.
_CELL = 0.5
# Parts whose outline covers at most this many cells look for room by walking
# the candidate offsets; larger ones correlate with the whole grid at once.
# With a correlation each, 1000 two-node parts took 15 seconds to pack.
_SCAN_MAX_CELLS = 256
_SCAN_BATCH = 1024

Part = Tuple[List[Hashable], np.ndarray]


def connected_parts(G) -> List[List[Hashable]]:
    """Node lists of the (weakly) connected parts, largest first.

    Nodes keep the graph's own order, and parts of equal size keep the order of
    their first node, so the result does not depend on set or hash order.
    """
    U = G.to_undirected(as_view=True) if G.is_directed() else G
    rank = {node: i for i, node in enumerate(G)}
    parts = [sorted(c, key=rank.__getitem__) for c in nx.connected_components(U)]
    parts.sort(key=lambda nodes: (-len(nodes), rank[nodes[0]]))
    return parts


def _part_graph(G, nodes):
    """The part as its own graph, with nodes in `nodes` order.

    A subgraph view would iterate its nodes in set order, and a force layout's
    random start is assigned in iteration order.
    """
    H = G.__class__()
    H.add_nodes_from((node, G.nodes[node]) for node in nodes)
    members = set(nodes)
    H.add_edges_from(
        (u, v, data) for u, v, data in G.edges(nodes, data=True) if v in members
    )
    return H


def layout_by_part(
    G, lay_out: Callable[[nx.Graph], Dict[Hashable, np.ndarray]]
) -> Dict[Hashable, np.ndarray]:
    """Lay out each part of `G` with `lay_out(part graph)` and pack the results."""
    placed: List[Part] = []
    for nodes in connected_parts(G):
        if len(nodes) == 1:
            xy = np.zeros((1, 2))
        else:
            H = _part_graph(G, nodes)
            pos = lay_out(H)
            xy = np.array([pos[node] for node in nodes], dtype=float).reshape(-1, 2)
            index = {node: i for i, node in enumerate(nodes)}
            xy = xy / _median_edge_length(xy, H, index)
        placed.append((nodes, xy - xy.mean(axis=0)))
    return pack(placed)


def _median_edge_length(xy: np.ndarray, H, index) -> float:
    edges = np.array(
        [(index[u], index[v]) for u, v in H.edges() if u != v], dtype=np.int64
    ).reshape(-1, 2)
    if len(edges) == 0:
        return 1.0
    lengths = np.linalg.norm(xy[edges[:, 0]] - xy[edges[:, 1]], axis=1)
    lengths = lengths[lengths > 0]
    return float(np.median(lengths)) if len(lengths) else 1.0


def _disc(radius_cells: float) -> np.ndarray:
    r = int(math.ceil(radius_cells))
    grid = np.mgrid[-r : r + 1, -r : r + 1]
    return np.hypot(*grid) <= radius_cells


def pack(parts: List[Part]) -> Dict[Hashable, np.ndarray]:
    """Place parts, largest first, each at the free spot nearest the centre.

    `parts` are (nodes, centred coordinates in edge lengths). Occupancy is kept
    on a grid: each placed part fills its outline (see `_outline`) plus
    `PART_GAP` around it. A large part finds every free offset at once, by
    correlating its outline with the occupancy; a small one walks the offsets
    in order of distance.
    """
    radii = [float(np.hypot(*xy.T).max()) if len(xy) > 1 else 0.0 for _, xy in parts]
    # Generous bound on the packed radius: room for every part's bounding circle.
    total = math.sqrt(sum((r + PART_GAP) ** 2 for r in radii))
    gap_disc = _disc(PART_GAP / _CELL)
    g = gap_disc.shape[0] // 2
    half = int(math.ceil((2.0 * total + 2.0 * PART_GAP) / _CELL)) + g + 1
    size = 2 * half + 1
    occupied = np.zeros((size, size), dtype=bool)

    # Candidate offsets nearest the centre first. Occupancy only grows, so the
    # first one whose cell is free only moves outwards (`frontier`).
    inner = half - g  # keep the clearance disc on the grid
    grid = np.mgrid[-inner : inner + 1, -inner : inner + 1].reshape(2, -1).T
    by_distance = grid[np.argsort(np.hypot(*grid.T), kind="stable")]
    frontier = 0

    out: Dict[Hashable, np.ndarray] = {}
    for i, ((nodes, xy), radius) in enumerate(zip(parts, radii)):
        cells = np.round(xy / _CELL).astype(int)
        outline, lo = _outline(cells, radius)
        if i == 0:
            offset = np.zeros(2, dtype=int)
        else:
            while occupied[tuple(by_distance[frontier] + half)]:
                frontier += 1
            if outline.sum() <= _SCAN_MAX_CELLS:
                offset = _scan_free_offset(
                    occupied, outline, lo, half, g, by_distance[frontier:]
                )
            else:
                offset = _nearest_free_offset(occupied, outline, lo, half, g)
        # Reserve the outline and the clearance around it.
        reserved = ndimage.binary_dilation(np.pad(outline, g), structure=gap_disc)
        a, b = lo + offset + half - g
        h, w = reserved.shape
        occupied[a : a + h, b : b + w] |= reserved
        shift = offset * _CELL
        for node, point in zip(nodes, xy):
            out[node] = point + shift
    return out


def _outline(cells: np.ndarray, radius: float):
    """A part's grid cells with its narrow concavities filled in.

    Returns a boolean mask over the part's own box and the box's low corner.
    """
    closing = max(1.0, OUTLINE_CLOSING * radius / _CELL)
    pad = int(math.ceil(closing)) + 1
    lo = cells.min(axis=0) - pad
    hi = cells.max(axis=0) + pad
    mask = np.zeros(tuple(hi - lo + 1), dtype=bool)
    mask[cells[:, 0] - lo[0], cells[:, 1] - lo[1]] = True
    return ndimage.binary_closing(mask, structure=_disc(closing)), lo


def _scan_free_offset(
    occupied: np.ndarray,
    outline: np.ndarray,
    lo: np.ndarray,
    half: int,
    margin: int,
    candidates: np.ndarray,
):
    """The first of `candidates` at which the outline meets nothing placed.

    Cheaper than a correlation over the whole grid for a small part, which
    usually fits within the first few batches. Offsets whose own cell is taken
    were dropped from `candidates`, a small part's outline covers its centre.
    """
    size = occupied.shape[0]
    rel = np.argwhere(outline) + lo + half
    box_lo = lo + half - margin
    box_hi = lo + np.array(outline.shape) - 1 + half + margin
    for start in range(0, len(candidates), _SCAN_BATCH):
        batch = candidates[start : start + _SCAN_BATCH]
        inside = ((batch + box_lo) >= 0).all(axis=1) & ((batch + box_hi) < size).all(
            axis=1
        )
        at = np.clip(batch[:, None, :] + rel[None], 0, size - 1)
        free = inside & ~occupied[at[..., 0], at[..., 1]].any(axis=1)
        if free.any():
            return batch[np.argmax(free)]
    raise ValueError("No room left to place a part")


def _nearest_free_offset(
    occupied: np.ndarray, outline: np.ndarray, lo: np.ndarray, half: int, margin: int
):
    """The grid offset nearest the centre at which the outline meets nothing placed.

    Only offsets that keep the outline `margin` cells inside the grid count, so
    its clearance can be written around it.
    """
    size = occupied.shape[0]
    hi = lo + np.array(outline.shape) - 1
    footprint = outline.astype(np.float32)
    # hits[k] = sum over the footprint of occupied[k - (shape - 1) + f]
    hits = fftconvolve(occupied.astype(np.float32), footprint[::-1, ::-1], mode="full")
    free = np.argwhere(hits < 0.5)
    offsets = free - (np.array(footprint.shape) - 1) - lo - half
    inside = ((offsets + lo + half) >= margin).all(axis=1) & (
        (offsets + hi + half) < size - margin
    ).all(axis=1)
    offsets = offsets[inside]
    return offsets[np.argmin(np.hypot(offsets[:, 0], offsets[:, 1]))]
