from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from typing import Any


def _finite_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(value)
    )


def _top_values(values: list[Any], limit: int = 12) -> list[dict[str, Any]]:
    counts = Counter(str(value) for value in values if value is not None)
    return [
        {"value": value, "count": count} for value, count in counts.most_common(limit)
    ]


def summarize_visualization(state: Any) -> dict[str, Any]:
    if not isinstance(state, dict):
        return {
            "available": False,
            "node_count": 0,
            "link_count": 0,
            "issues": ["Visualization state is not an object."],
        }

    snapshot = state
    render = snapshot.get("render")
    if isinstance(render, dict):
        state = render
    metadata = (
        snapshot.get("metadata") if isinstance(snapshot.get("metadata"), dict) else {}
    )
    node_attributes = snapshot.get("node_attributes", [])
    edge_attributes = snapshot.get("edge_attributes", [])

    nodes = state.get("nodes") if isinstance(state.get("nodes"), list) else []
    links = state.get("links") if isinstance(state.get("links"), list) else []
    issues: list[str] = []

    invalid_coordinates = 0
    invalid_colors = 0
    sizes: list[float] = []
    colors: list[Any] = []
    labels = 0

    for node in nodes:
        if not isinstance(node, dict):
            issues.append("A node is not an object.")
            continue
        if not _finite_number(node.get("x")) or not _finite_number(node.get("y")):
            invalid_coordinates += 1
        color = node.get("color")
        if color is not None:
            colors.append(color)
            if not isinstance(color, str) or not color.strip():
                invalid_colors += 1
        size = node.get("size")
        if _finite_number(size):
            sizes.append(float(size))
        elif size is not None:
            issues.append(f"Node {node.get('id', '?')} has a non-numeric size.")
        if node.get("label") not in (None, ""):
            labels += 1

    invalid_links = 0
    node_ids = {str(node.get("id")) for node in nodes if isinstance(node, dict)}
    for link in links:
        if not isinstance(link, dict):
            invalid_links += 1
            continue
        source = link.get("source")
        target = link.get("target")
        if isinstance(source, dict):
            source = source.get("id")
        if isinstance(target, dict):
            target = target.get("id")
        if str(source) not in node_ids or str(target) not in node_ids:
            invalid_links += 1

    if invalid_coordinates:
        issues.append(f"{invalid_coordinates} nodes have invalid coordinates.")
    if invalid_colors:
        issues.append(f"{invalid_colors} nodes have invalid colors.")
    if invalid_links:
        issues.append(f"{invalid_links} links reference missing or invalid nodes.")

    positions = [
        [node.get("id"), node.get("x"), node.get("y")]
        for node in nodes
        if isinstance(node, dict)
    ]
    position_hash = hashlib.sha256(
        json.dumps(positions, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()[:16]

    return {
        "available": True,
        "network_id": snapshot.get("network_id") or metadata.get("id"),
        "node_count": len(nodes),
        "link_count": len(links),
        "node_attributes": [
            item.get("name", item.get("attribute"))
            for item in node_attributes
            if isinstance(item, dict)
        ],
        "edge_attributes": [
            item.get("name", item.get("attribute"))
            for item in edge_attributes
            if isinstance(item, dict)
        ],
        "layout": metadata.get("last_layout_name"),
        "node_color_config": metadata.get("last_node_color_config"),
        "node_size_config": metadata.get("last_node_size_config"),
        "label_count": labels,
        "node_colors": _top_values(colors),
        "distinct_node_colors": len({str(color) for color in colors}),
        "node_size": {
            "min": min(sizes) if sizes else None,
            "max": max(sizes) if sizes else None,
            "distinct": len(set(sizes)),
        },
        "position_hash": position_hash,
        "legend": state.get("legend"),
        "issues": issues,
    }


def diff_visualizations(before: Any, after: Any) -> dict[str, Any]:
    before_summary = summarize_visualization(before)
    after_summary = summarize_visualization(after)
    tracked = (
        "network_id",
        "node_count",
        "link_count",
        "node_attributes",
        "edge_attributes",
        "layout",
        "node_color_config",
        "node_size_config",
        "label_count",
        "distinct_node_colors",
        "node_size",
        "position_hash",
        "legend",
        "issues",
    )
    changed = {
        key: {"before": before_summary.get(key), "after": after_summary.get(key)}
        for key in tracked
        if before_summary.get(key) != after_summary.get(key)
    }
    return {
        "changed": bool(changed),
        "changes": changed,
        "before": before_summary,
        "after": after_summary,
    }
