"""Edge backbones: keep every node, drop all but the strongest edges (ADR 0040).

A dense similarity network (every course similar to a dozen others) draws as one
hairball whatever the layout, because the layout sees a near-uniform graph. The
backbone keeps each node's few strongest ties, so groups of mutually similar
nodes separate and the drawing shows them.
"""

from collections import defaultdict
from typing import Any, Dict, List, Optional

import networkx as nx
from sqlalchemy.orm import Session

from common import models

from .layout_quality import THRESHOLDS
from .subgraph import create_subgraph_from_nodes

METHODS = ("top_k", "threshold")
# Edge strength when the network has no imported weights.
STRENGTH_WEIGHT = "weight"
STRENGTH_COMMON_NEIGHBORS = "common_neighbors"
# A backbone is offered where layout_quality reports `dense_edges`.
DENSE_MEAN_DEGREE = THRESHOLDS["dense_edges"]
# The k levels measured for the offer.
SUGGESTED_K = (1, 2, 3)


def _edges(network_id: int, db: Session) -> List[models.Edge]:
    return db.query(models.Edge).filter_by(network_id=network_id).all()


def edge_strengths(edges: List[models.Edge]) -> tuple[Dict[int, float], str]:
    """Strength of each edge (by primary key), and what it is measured by.

    Imported weights when they vary; otherwise the number of neighbours the two
    ends share, so ties inside a tight group outrank ties between groups.
    """
    weights = [edge.weight for edge in edges if edge.weight is not None]
    if weights and min(weights) != max(weights):
        return (
            {e.id: float(e.weight if e.weight is not None else 0.0) for e in edges},
            STRENGTH_WEIGHT,
        )
    G = nx.Graph()
    G.add_edges_from((e.source_node_id, e.target_node_id) for e in edges)
    adjacency = {node: set(G[node]) for node in G}
    return (
        {
            e.id: float(len(adjacency[e.source_node_id] & adjacency[e.target_node_id]))
            for e in edges
        },
        STRENGTH_COMMON_NEIGHBORS,
    )


def select_edges(
    edges: List[models.Edge],
    strengths: Dict[int, float],
    method: str,
    k: Optional[int] = None,
    min_strength: Optional[float] = None,
) -> set[int]:
    """Primary keys of the edges the backbone keeps."""
    if method == "threshold":
        if min_strength is None:
            raise ValueError("method='threshold' needs min_weight.")
        return {e.id for e in edges if strengths[e.id] >= min_strength}
    if method != "top_k":
        raise ValueError(f"method must be one of {METHODS}")
    if not k or k < 1:
        raise ValueError("method='top_k' needs k >= 1.")
    incident: Dict[int, List[models.Edge]] = defaultdict(list)
    for edge in edges:
        incident[edge.source_node_id].append(edge)
        if edge.target_node_id != edge.source_node_id:
            incident[edge.target_node_id].append(edge)
    kept: set[int] = set()
    for ties in incident.values():
        # Strongest first; the edge id breaks ties so the result is repeatable.
        ties.sort(key=lambda e: (-strengths[e.id], e.edge_id))
        kept.update(e.id for e in ties[:k])
    return kept


def measure(
    edges: List[models.Edge], kept: set[int], node_count: int
) -> Dict[str, Any]:
    """Size of a backbone: edges left, connected parts and isolated nodes."""
    G = nx.Graph()
    touched = set()
    for edge in edges:
        if edge.id in kept:
            G.add_edge(edge.source_node_id, edge.target_node_id)
            touched.update((edge.source_node_id, edge.target_node_id))
    isolated = node_count - len(touched)
    parts = nx.number_connected_components(G) + isolated
    largest = max((len(c) for c in nx.connected_components(G)), default=1)
    return {
        "edges": len(kept),
        "mean_degree": round(2 * len(kept) / node_count, 2) if node_count else 0.0,
        "connected_parts": parts,
        "largest_part_nodes": largest,
        "isolated_nodes": isolated,
    }


def suggest_backbones(network_id: int, db: Session) -> List[Dict[str, Any]]:
    """Measured top-k backbones for a dense network; [] for a sparse one."""
    node_count = db.query(models.Node).filter_by(network_id=network_id).count()
    edges = _edges(network_id, db)
    if not node_count or 2 * len(edges) / node_count < DENSE_MEAN_DEGREE:
        return []
    strengths, measured_by = edge_strengths(edges)
    candidates = []
    for k in SUGGESTED_K:
        kept = select_edges(edges, strengths, "top_k", k=k)
        candidates.append(
            {
                "method": "edge_backbone",
                "tool": "subgraph_edge_backbone",
                "arguments": {"network_id": network_id, "method": "top_k", "k": k},
                "nodes": node_count,
                **measure(edges, kept, node_count),
                "drops": f"all but each node's {k} strongest edges (by {measured_by})",
                "keeps": "every node; groups of mutually similar nodes separate",
            }
        )
    return candidates


def extract_backbone(
    network_id: int,
    db: Session,
    method: str = "top_k",
    k: Optional[int] = 3,
    min_weight: Optional[float] = None,
    description: Optional[str] = None,
) -> Dict[str, Any]:
    """Create the backbone as a child network; nothing is selected or drawn."""
    edges = _edges(network_id, db)
    if not edges:
        raise ValueError(f"Network {network_id} has no edges to thin out.")
    strengths, measured_by = edge_strengths(edges)
    if method == "threshold" and measured_by != STRENGTH_WEIGHT:
        raise ValueError(
            "This network has no varying edge weights, so a weight threshold "
            "keeps all or nothing. Use method='top_k'."
        )
    kept = select_edges(edges, strengths, method, k=k, min_strength=min_weight)
    if not kept:
        raise ValueError("No edge reaches that threshold; lower min_weight.")

    node_ids = [
        row.node_id
        for row in db.query(models.Node.node_id).filter_by(network_id=network_id)
    ]
    rule = f"top {k} per node" if method == "top_k" else f"weight >= {min_weight}"
    result = create_subgraph_from_nodes(
        network_id,
        node_ids,
        db,
        suffix=f"Backbone ({rule})",
        description=description or f"Edge backbone of network {network_id}: {rule}",
        initialize_layout=False,
        reuse_existing=False,
        edge_pks=kept,
    )
    stats = measure(edges, kept, len(node_ids))
    return {
        "created_network_id": result["new_network_id"],
        "source_network_id": network_id,
        "nodes": len(node_ids),
        "source_edges": len(edges),
        **stats,
        "strength": measured_by,
        "content": (
            f"Backbone created ({rule}, strength = {measured_by}): kept "
            f"{stats['edges']} of {len(edges)} edges and all {len(node_ids)} nodes; "
            f"{stats['connected_parts']} connected parts, the largest with "
            f"{stats['largest_part_nodes']} nodes. Degrees and centralities computed "
            "on it describe the thinned network. Select it with network_select, "
            "calculate a layout, then render."
        ),
    }
