"""Read-only questions about nodes, routes and attribute groups.

Each function answers one question in a result whose size is bounded by its
arguments, not by the network (ADR 0024): they exist so the model can ask a
precise question instead of reading many nodes one by one.
"""

import itertools
import statistics
from collections import Counter
from typing import Any, Dict, List, Optional

import networkx as nx
from sqlalchemy.orm import Session

from common import models

from .attributes import load_node_attribute_values
from .paths import path_graph, require_node
from .result_shaping import summarize_values
from .utils.graph_builder import build_graph_from_db

MAX_ALTERNATIVE_PATHS = 10
MAX_COMPARED_NODES = 25


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def layout_attribute_names(network_id: int, db: Session) -> set:
    """Coordinate attributes, which describe a drawing rather than a node."""
    rows = (
        db.query(models.NodeAttribute.attribute_name)
        .filter(
            models.NodeAttribute.network_id == network_id,
            models.NodeAttribute.derived_from.like("layout:%"),
        )
        .all()
    )
    return {row[0] for row in rows}


def k_shortest_paths(
    network_id: int,
    db: Session,
    source: str,
    target: str,
    k: int = 3,
    weight: Optional[str] = None,
) -> Dict[str, Any]:
    """Up to k loopless routes, shortest first (Yen's algorithm)."""
    if not 1 <= k <= MAX_ALTERNATIVE_PATHS:
        raise ValueError(f"k must be between 1 and {MAX_ALTERNATIVE_PATHS}")
    graph, weight = path_graph(network_id, db, weight)
    require_node(graph, source)
    require_node(graph, target)
    if weight and any(d[weight] < 0 for _, _, d in graph.edges(data=True)):
        raise ValueError("Alternative paths require nonnegative costs")
    if source == target or not nx.has_path(graph, source, target):
        return {
            "source": source,
            "target": target,
            "reachable": source == target,
            "paths": [{"path": [source], "hops": 0, "length": 0}] if source == target else [],
            "is_directed": graph.is_directed(),
        }
    routes = []
    for path in itertools.islice(
        nx.shortest_simple_paths(graph, source, target, weight=weight), k
    ):
        length = (
            nx.path_weight(graph, path, weight) if weight else len(path) - 1
        )
        routes.append({"path": path, "hops": len(path) - 1, "length": length})
    return {
        "source": source,
        "target": target,
        "reachable": True,
        "paths": routes,
        "weight": weight,
        "is_directed": graph.is_directed(),
    }


def common_neighbors(
    network_id: int, db: Session, a: str, b: str, limit: int = 30
) -> Dict[str, Any]:
    """Nodes adjacent to both a and b, ignoring direction."""
    graph = build_graph_from_db(network_id, db).to_undirected(as_view=True)
    require_node(graph, a)
    require_node(graph, b)
    shared = sorted(
        set(graph[a]) & set(graph[b]) - {a, b},
        key=lambda n: (-graph.degree(n), n),
    )
    union = (set(graph[a]) | set(graph[b])) - {a, b}
    return {
        "a": a,
        "b": b,
        "adjacent": graph.has_edge(a, b),
        "common_count": len(shared),
        "common_neighbors": shared[:limit],
        "omitted": max(0, len(shared) - limit),
        "jaccard": round(len(shared) / len(union), 6) if union else 0.0,
    }


def compare_nodes(
    network_id: int,
    db: Session,
    node_ids: List[str],
    attributes: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """One row per node with the chosen attributes, plus its degree."""
    if not node_ids:
        raise ValueError("node_ids is empty")
    if len(node_ids) > MAX_COMPARED_NODES:
        raise ValueError(f"Compare at most {MAX_COMPARED_NODES} nodes at once")
    graph = build_graph_from_db(network_id, db)
    for node in node_ids:
        require_node(graph, node)

    known = [
        row[0]
        for row in db.query(models.NodeAttribute.attribute_name)
        .filter(models.NodeAttribute.network_id == network_id)
        .order_by(models.NodeAttribute.attribute_name)
        .all()
    ]
    if attributes:
        missing = [a for a in attributes if a not in known]
        if missing:
            raise ValueError(f"Unknown attribute(s): {', '.join(missing)}")
        names = list(attributes)
    else:
        coordinates = layout_attribute_names(network_id, db)
        names = [a for a in known if a not in coordinates]

    labels = dict(
        db.query(models.Node.node_id, models.Node.label)
        .filter(
            models.Node.network_id == network_id,
            models.Node.node_id.in_(node_ids),
        )
        .all()
    )
    values = {name: load_node_attribute_values(network_id, name, db) for name in names}
    rows = {}
    for node in node_ids:
        row = {"label": labels.get(node), "degree": graph.degree(node)}
        for name in names:
            row[name] = values[name].get(node)
        rows[node] = row
    return {"attributes": names, "nodes": rows}


def _numeric_histogram(numbers: List[float], bins: int) -> List[Dict[str, Any]]:
    low, high = min(numbers), max(numbers)
    if low == high:
        return [{"from": low, "to": high, "count": len(numbers)}]
    step = (high - low) / bins
    counts = [0] * bins
    for v in numbers:
        counts[min(int((v - low) / step), bins - 1)] += 1
    return [
        {"from": round(low + i * step, 6), "to": round(low + (i + 1) * step, 6), "count": c}
        for i, c in enumerate(counts)
    ]


def attribute_distribution(
    network_id: int,
    db: Session,
    attribute: str,
    group_by: Optional[str] = None,
    bins: int = 10,
    top: int = 15,
) -> Dict[str, Any]:
    """The shape of one node attribute, optionally per group of another."""
    values = load_node_attribute_values(network_id, attribute, db)
    if not values:
        raise ValueError(
            f"Node attribute '{attribute}' has no values; check "
            "network_list_node_attributes or compute it first."
        )
    node_count = db.query(models.Node).filter(models.Node.network_id == network_id).count()
    numeric = all(_is_number(v) for v in values.values())
    result: Dict[str, Any] = {
        "attribute": attribute,
        "kind": "numeric" if numeric else "categorical",
        "with_value": len(values),
        "missing": node_count - len(values),
    }
    if numeric:
        numbers = [float(v) for v in values.values()]
        result["summary"] = summarize_values(values)
        result["histogram"] = _numeric_histogram(numbers, bins)
    else:
        counts = Counter(str(v) for v in values.values())
        result["distinct"] = len(counts)
        result["counts"] = dict(counts.most_common(top))
        result["other_count"] = sum(counts.values()) - sum(result["counts"].values())

    if group_by:
        groups_of = load_node_attribute_values(network_id, group_by, db)
        if not groups_of:
            raise ValueError(f"Group attribute '{group_by}' has no values")
        members: Dict[str, List[Any]] = {}
        for node, value in values.items():
            if node in groups_of:
                members.setdefault(str(groups_of[node]), []).append(value)
        ordered = sorted(members.items(), key=lambda kv: -len(kv[1]))
        by_group = {}
        for name, vals in ordered[:top]:
            if numeric:
                nums = [float(v) for v in vals]
                by_group[name] = {
                    "count": len(nums),
                    "mean": round(statistics.fmean(nums), 6),
                    "median": statistics.median(nums),
                    "min": min(nums),
                    "max": max(nums),
                }
            else:
                by_group[name] = dict(Counter(str(v) for v in vals).most_common(5))
        result["group_by"] = group_by
        result["by_group"] = by_group
        result["groups_omitted"] = max(0, len(ordered) - top)
    return result


def group_connectivity(
    network_id: int, db: Session, attribute: str, top: int = 20
) -> Dict[str, Any]:
    """Edges inside each group and between pairs of groups."""
    groups_of = load_node_attribute_values(network_id, attribute, db)
    if not groups_of:
        raise ValueError(f"Node attribute '{attribute}' has no values")
    graph = build_graph_from_db(network_id, db)
    within: Counter = Counter()
    between: Counter = Counter()
    sizes = Counter(str(v) for v in groups_of.values())
    unassigned = 0
    for u, v in graph.edges():
        if u not in groups_of or v not in groups_of:
            unassigned += 1
            continue
        gu, gv = str(groups_of[u]), str(groups_of[v])
        if gu == gv:
            within[gu] += 1
        else:
            pair = (gu, gv) if graph.is_directed() else tuple(sorted((gu, gv)))
            between[pair] += 1
    edge_total = sum(within.values()) + sum(between.values())
    return {
        "attribute": attribute,
        "group_count": len(sizes),
        "edges_within": sum(within.values()),
        "edges_between": sum(between.values()),
        "within_share": round(sum(within.values()) / edge_total, 6) if edge_total else None,
        "groups": {
            g: {"nodes": sizes[g], "internal_edges": within.get(g, 0)}
            for g, _ in sizes.most_common(top)
        },
        "strongest_links": [
            {"groups": list(pair), "edges": n} for pair, n in between.most_common(top)
        ],
        "links_omitted": max(0, len(between) - top),
        "edges_without_group": unassigned,
        "is_directed": graph.is_directed(),
    }
