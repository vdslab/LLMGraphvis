"""A drawing described in numbers, so the agent can read it without an image (ADR 0042).

Everything here is measured on the payload `build_visualization` sends to the
canvas: coordinates already mapped onto [-1000, 1000] by
`layout_quality.normalize_like_renderer`, the resolved colors and sizes, the
label flags and the highlight. y grows downward, as on the SVG canvas, so a
negative y is "top".

Results are bounded (ADR 0024): every list holds at most `limit` entries and
says how many it left out.
"""

from collections import Counter
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

import networkx as nx
import numpy as np
from scipy.spatial import cKDTree
from scipy.stats import spearmanr

from app.logic.layout_quality import TARGET_EXTENT

# A third of the canvas per axis: the 3x3 grid regions are named on.
REGION_EDGE = TARGET_EXTENT / 3
REGIONS = (
    "top-left",
    "top",
    "top-right",
    "left",
    "center",
    "right",
    "bottom-left",
    "bottom",
    "bottom-right",
)
# Neighbours a group's cohesion is measured over.
NEIGHBOURS = 5
# Distance from the canvas center, as a share of TARGET_EXTENT, that bounds the
# core and the middle ring; anything further out is periphery.
CORE_RADIUS = 0.35
MIDDLE_RADIUS = 0.7
# A node is an outlier when its nearest neighbour is this many times further
# away than the median node's nearest neighbour.
OUTLIER_FACTOR = 5.0
# A region a group occupies is listed once it holds this share of the group.
MAIN_REGION_SHARE = 0.25
# Share of nodes, by value, that count as "high" for a numeric channel.
HIGH_VALUE_SHARE = 0.1
# A categorical grouping with more distinct values than this is treated as
# numeric when its values are numbers.
MAX_CATEGORIES = 20

Point = Tuple[float, float]


def region_of(x: float, y: float) -> str:
    """The 3x3 grid cell of a canvas point, e.g. 'top-left' or 'center'."""
    col = "left" if x < -REGION_EDGE else "right" if x > REGION_EDGE else None
    row = "top" if y < -REGION_EDGE else "bottom" if y > REGION_EDGE else None
    if row and col:
        return f"{row}-{col}"
    return row or col or "center"


def placement_of(x: float, y: float) -> str:
    """'core', 'middle' or 'periphery', by distance from the canvas center."""
    r = float(np.hypot(x, y)) / TARGET_EXTENT
    if r < CORE_RADIUS:
        return "core"
    return "middle" if r < MIDDLE_RADIUS else "periphery"


def _round(value: Optional[float], digits: int = 3) -> Optional[float]:
    return None if value is None else round(float(value), digits)


def _point(points: np.ndarray) -> Dict[str, Any]:
    """Centroid of some points, with its region."""
    cx, cy = points.mean(axis=0)
    return {"center": [round(float(cx)), round(float(cy))], "region": region_of(cx, cy)}


def _main_regions(points: np.ndarray) -> List[str]:
    counts = Counter(region_of(x, y) for x, y in points)
    total = len(points)
    return [r for r, c in counts.most_common() if c / total >= MAIN_REGION_SHARE]


def _spread(points: np.ndarray) -> float:
    """Root-mean-square distance from the centroid, as a share of TARGET_EXTENT."""
    deviations = points - points.mean(axis=0)
    return round(float(np.sqrt((deviations**2).sum(axis=1).mean())) / TARGET_EXTENT, 3)


def _omitted(total: int, shown: int) -> Dict[str, int]:
    return {"omitted": total - shown} if total > shown else {}


def describe_drawing(
    vis_data: Mapping[str, Any],
    groups: Optional[Tuple[str, Mapping[str, Any]]] = None,
    numeric: Sequence[Tuple[str, str, Mapping[str, float]]] = (),
    limit: int = 5,
) -> Dict[str, Any]:
    """Describe what a rendered payload shows and where.

    Args:
        vis_data: the payload of `build_visualization` (nodes, links, legend,
            optionally layout_quality and label_style).
        groups: `(name, {node_id: value})` to describe categorical groups by;
            None groups by drawn color when only a few colors are drawn.
        numeric: `(channel, attribute, {node_id: value})` for each numeric
            encoding whose placement is worth describing.
        limit: the most entries any list returns.
    """
    nodes = list(vis_data.get("nodes") or [])
    links = list(vis_data.get("links") or [])
    legend = dict(vis_data.get("legend") or {})
    ids = [n["id"] for n in nodes]
    points = np.array([[n["x"], n["y"]] for n in nodes], dtype=float).reshape(-1, 2)

    result: Dict[str, Any] = {
        "layout": legend.pop("layout", None),
        "canvas": {
            "node_count": len(nodes),
            "edge_count": len(links),
            "dimmed_nodes": sum(1 for n in nodes if (n.get("opacity") or 1) < 1),
            "coordinates": (
                "x grows right and y grows down, both in [-1000, 1000]; regions "
                "name a 3x3 grid of the whole drawing, whatever the current zoom."
            ),
        },
    }
    highlight = legend.pop("highlight", None)
    result["encodings"] = legend
    if not nodes:
        result["note"] = "Nothing is drawn."
        return result

    result["regions"] = _regions(points)
    result["labels"] = _labels(nodes, vis_data.get("label_style") or {}, limit)
    if highlight:
        marked = np.array([n.get("highlighted", False) for n in nodes])
        if marked.any():
            highlight.update(_point(points[marked]))
            highlight["main_regions"] = _main_regions(points[marked])
        result["highlight"] = highlight

    tree = cKDTree(points)
    result["groups"] = _groups(ids, nodes, points, tree, groups, limit)
    if numeric:
        result["numeric_placement"] = [
            entry
            for channel, attribute, values in numeric
            if (entry := _numeric(nodes, points, channel, attribute, values, limit))
        ]
    degree = Counter()
    for link in links:
        degree[link["source"]] += 1
        degree[link["target"]] += 1
    result["prominent_nodes"] = _prominent(nodes, degree, limit)
    result["components"] = _components(ids, points, links, limit)
    result["outliers"] = _outliers(nodes, points, tree, limit)
    if vis_data.get("layout_quality"):
        result["layout_quality"] = vis_data["layout_quality"]
    return result


def _regions(points: np.ndarray) -> Dict[str, Any]:
    counts = Counter(region_of(x, y) for x, y in points)
    total = len(points)
    share = {r: round(counts[r] / total, 3) for r in REGIONS}
    densest = max(REGIONS, key=lambda r: counts[r])
    return {
        "node_share": share,
        "densest": densest,
        "empty": [r for r in REGIONS if counts[r] == 0],
    }


def _labels(nodes: List[Dict], style: Mapping[str, Any], limit: int) -> Dict:
    flagged = [n for n in nodes if "show_label" in n]
    if not flagged:
        return {"visibility": "all", "shown_count": len(nodes)}
    shown = [n for n in flagged if n["show_label"]]
    shown.sort(key=lambda n: -(n.get("size") or 0))
    return {
        "visibility": style.get("visibility", "all"),
        "shown_count": len(shown),
        "shown": [n["label"] for n in shown[:limit]],
        **_omitted(len(shown), limit),
    }


def _groups(
    ids: List[str],
    nodes: List[Dict],
    points: np.ndarray,
    tree: cKDTree,
    groups: Optional[Tuple[str, Mapping[str, Any]]],
    limit: int,
) -> Optional[Dict[str, Any]]:
    if groups is not None:
        by, values = groups
        labels = [values.get(i) for i in ids]
        labels = ["(missing)" if v is None else v for v in labels]
    else:
        labels = [n.get("color") for n in nodes]
        if len(set(labels)) > MAX_CATEGORIES:
            return None
        by = "drawn color"
    distinct = Counter(labels)
    if len(distinct) < 2:
        return None

    n = len(ids)
    k = min(NEIGHBOURS, n - 1)
    _, neighbours = tree.query(points, k=k + 1)
    neighbours = np.asarray(neighbours).reshape(n, -1)[:, 1:]
    label_arr = np.array([str(v) for v in labels], dtype=object)
    same = (label_arr[neighbours] == label_arr[:, None]).mean(axis=1)

    colors: Dict[str, Counter] = {}
    for label, node in zip(label_arr, nodes):
        colors.setdefault(label, Counter())[node.get("color")] += 1

    items = []
    for value, count in distinct.most_common():
        mask = label_arr == str(value)
        members = points[mask]
        items.append(
            {
                "value": value,
                "color": colors[str(value)].most_common(1)[0][0],
                "node_count": count,
                "share": round(count / n, 3),
                **_point(members),
                "main_regions": _main_regions(members),
                "spread": _spread(members),
                "cohesion": round(float(same[mask].mean()), 3),
                "chance": round((count - 1) / (n - 1), 3),
            }
        )

    expected = sum(c * (c - 1) for c in distinct.values()) / (n * (n - 1))
    observed = float(same.mean())
    separation = (observed - expected) / (1 - expected) if expected < 1 else 0.0
    return {
        "by": by,
        "count": len(distinct),
        "separation": round(separation, 3),
        "items": items[:limit],
        **_omitted(len(items), limit),
    }


def _numeric(
    nodes: List[Dict],
    points: np.ndarray,
    channel: str,
    attribute: str,
    values: Mapping[str, float],
    limit: int,
) -> Optional[Dict[str, Any]]:
    present = [
        (i, float(values[n["id"]]))
        for i, n in enumerate(nodes)
        if isinstance(values.get(n["id"]), (int, float))
        and not isinstance(values.get(n["id"]), bool)
    ]
    if len(present) < 3:
        return None
    idx = np.array([i for i, _ in present])
    vals = np.array([v for _, v in present])
    if np.ptp(vals) == 0:
        return None
    closeness = -np.hypot(points[idx, 0], points[idx, 1])
    corr = spearmanr(vals, closeness)[0]
    top_n = max(1, int(round(len(vals) * HIGH_VALUE_SHARE)))
    order = idx[np.argsort(-vals, kind="stable")[:top_n]]
    top = points[order]
    return {
        "channel": channel,
        "attribute": attribute,
        "center_correlation": None if np.isnan(corr) else _round(corr),
        "high_values": {
            "node_count": top_n,
            **_point(top),
            "main_regions": _main_regions(top),
            "placement": dict(Counter(placement_of(x, y) for x, y in top)),
            "nodes": [
                {
                    "id": nodes[i]["id"],
                    "label": nodes[i]["label"],
                    "value": _round(values[nodes[i]["id"]], 4),
                    "region": region_of(*points[i]),
                    "placement": placement_of(*points[i]),
                }
                for i in order[:limit]
            ],
            **_omitted(top_n, min(top_n, limit)),
        },
    }


def _prominent(nodes: List[Dict], degree: Counter, limit: int) -> Dict[str, Any]:
    sizes = [n.get("size") or 0 for n in nodes]
    if max(sizes) == min(sizes):
        return {"note": "All nodes are drawn at the same size."}
    ranked = sorted(nodes, key=lambda n: -(n.get("size") or 0))[:limit]
    return {
        "by": "drawn size",
        "items": [
            {
                "id": n["id"],
                "label": n["label"],
                "size": _round(n.get("size"), 2),
                "degree": degree[n["id"]],
                "region": region_of(n["x"], n["y"]),
                "placement": placement_of(n["x"], n["y"]),
            }
            for n in ranked
        ],
    }


def _components(
    ids: List[str], points: np.ndarray, links: List[Dict], limit: int
) -> Dict[str, Any]:
    graph = nx.Graph()
    graph.add_nodes_from(range(len(ids)))
    index = {node_id: i for i, node_id in enumerate(ids)}
    graph.add_edges_from(
        (index[e["source"]], index[e["target"]])
        for e in links
        if e["source"] in index and e["target"] in index
    )
    parts = sorted(nx.connected_components(graph), key=len, reverse=True)
    connected = [p for p in parts if len(p) > 1]
    items = []
    for part in connected[:limit]:
        members = points[sorted(part)]
        extent = (np.ptp(members, axis=0) / (2 * TARGET_EXTENT)).round(3)
        items.append(
            {
                "node_count": len(part),
                **_point(members),
                "extent": [float(extent[0]), float(extent[1])],
            }
        )
    return {
        "count": len(parts),
        "isolated_nodes": len(parts) - len(connected),
        "largest": items,
        **_omitted(len(connected), len(items)),
    }


def _outliers(
    nodes: List[Dict], points: np.ndarray, tree: cKDTree, limit: int
) -> Dict[str, Any]:
    if len(nodes) < 3:
        return {"count": 0, "items": []}
    distances, _ = tree.query(points, k=2)
    nearest = distances[:, 1]
    median = float(np.median(nearest))
    if median <= 0:
        return {"count": 0, "items": []}
    ratio = nearest / median
    flagged = [i for i in np.argsort(-ratio) if ratio[i] >= OUTLIER_FACTOR]
    return {
        "count": len(flagged),
        "items": [
            {
                "id": nodes[i]["id"],
                "label": nodes[i]["label"],
                "region": region_of(*points[i]),
                "isolation": round(float(ratio[i]), 1),
            }
            for i in flagged[:limit]
        ],
        **_omitted(len(flagged), limit),
    }
