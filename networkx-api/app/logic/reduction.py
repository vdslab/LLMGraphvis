"""Ways to shrink a large network, measured before anything is created (ADR 0034).

Every candidate names the existing extraction tool and arguments that would
produce it, so applying one is an ordinary tool call and this module never
writes. "Large" is defined by layout cost: the size at which a default
ForceAtlas2 run no longer fits its iteration budget (ADR 0033).
"""

from collections import Counter
from typing import Any, Dict, List, Optional

import networkx as nx
from sqlalchemy.orm import Session

from app.logic.attribute_semantics import (
    CATEGORICAL,
    DISCRETE,
    ROLE_COMMUNITY,
    ROLE_DATA,
)
from app.logic.attributes import load_node_attribute_values
from app.logic.backbone import suggest_backbones
from app.logic.layouts.force_directed import fa2_budget_floor_nodes
from app.logic.reduction_impact import assess, assess_backbone, structural_groups
from app.logic.utils.graph_builder import build_graph_from_db
from common import models

# Default size to aim for, as a share of the "large" threshold. Half of it is
# about a quarter of the layout cost (cost grows with N^2).
_TARGET_SHARE = 0.5
# An attribute splits the network into usable groups only if it has at most
# this many values; more, and each group is a sliver.
_MAX_GROUPS = 12
# Groups listed per attribute, largest first; the rest are counted, not named.
_GROUPS_SHOWN = 5
# Attributes offered as group filters, at most.
_ATTRIBUTES_SHOWN = 3


def large_threshold_nodes() -> int:
    """Node count from which a network counts as large."""
    return fa2_budget_floor_nodes()


def is_large(node_count: int) -> bool:
    return node_count >= large_threshold_nodes()


def default_target_nodes() -> int:
    return int(large_threshold_nodes() * _TARGET_SHARE)


def suggest_reductions(
    network_id: int, db: Session, target_nodes: Optional[int] = None
) -> Dict[str, Any]:
    """Candidate reductions of `network_id`, each with the size it would leave."""
    G = build_graph_from_db(network_id, db)
    n, m = G.number_of_nodes(), G.number_of_edges()
    target = target_nodes or default_target_nodes()

    groups = structural_groups(G, network_id, db)
    candidates: List[Dict[str, Any]] = []
    for build in (_largest_component, _k_core, _min_degree):
        candidate = build(G, network_id, target)
        # A cut that keeps every node changes nothing (ADR 0049).
        if candidate and candidate["nodes"] < n:
            keep = candidate.pop("_keep")
            candidate["impact"] = assess(G, keep, groups)
            candidates.append(candidate)

    attribute_candidates, attributes_omitted = _attribute_groups(G, network_id, db)
    candidates.extend(attribute_candidates)
    # Dense networks: thin the edges instead of dropping nodes (ADR 0040).
    for backbone in suggest_backbones(network_id, db):
        backbone["impact"] = assess_backbone(
            G, backbone["connected_parts"], backbone["isolated_nodes"]
        )
        candidates.append(backbone)

    return {
        "network_id": network_id,
        "nodes": n,
        "edges": m,
        "large": is_large(n),
        "large_threshold_nodes": large_threshold_nodes(),
        "target_nodes": target,
        "candidates": candidates,
        "attributes_omitted": attributes_omitted,
        "groups_by": groups.source,
    }


def _size(G: nx.Graph, nodes) -> Dict[str, int]:
    sub = G.subgraph(nodes)
    return {"nodes": sub.number_of_nodes(), "edges": sub.number_of_edges()}


def _components(G: nx.Graph):
    if G.is_directed():
        return list(nx.weakly_connected_components(G))
    return list(nx.connected_components(G))


def _largest_component(G, network_id, target) -> Optional[Dict[str, Any]]:
    components = _components(G)
    if len(components) < 2:
        return None
    largest = max(components, key=len)
    isolates = sum(1 for c in components if len(c) == 1)
    return {
        "method": "largest_component",
        "tool": "subgraph_largest_component",
        "arguments": {"network_id": network_id},
        **_size(G, largest),
        "_keep": largest,
        "drops": (
            f"{len(components) - 1} smaller parts "
            f"({G.number_of_nodes() - len(largest)} nodes, {isolates} of them isolated)"
        ),
        "keeps": "the one connected part that holds most nodes",
    }


def _k_core(G, network_id, target) -> Optional[Dict[str, Any]]:
    """The smallest k whose k-core fits `target`, or the innermost core."""
    # Self-loops are dropped, as subgraph_k_core does before nx.k_core.
    H = G.copy()
    H.remove_edges_from(nx.selfloop_edges(H))
    if H.number_of_edges() == 0:
        return None
    core = nx.core_number(H)
    max_k = max(core.values())
    if max_k < 2:
        return None
    # Size of each k-core: nodes whose core number is at least k.
    counts = Counter(core.values())
    sizes, running = {}, 0
    for k in range(max_k, 0, -1):
        running += counts.get(k, 0)
        sizes[k] = running
    k = next((k for k in range(2, max_k + 1) if sizes[k] <= target), max_k)
    nodes = [node for node, c in core.items() if c >= k]
    return {
        "method": "k_core",
        "tool": "subgraph_k_core",
        "arguments": {"network_id": network_id, "k": k},
        **_size(G, nodes),
        "_keep": nodes,
        "drops": (
            f"nodes outside every group whose members each have {k}+ links inside it"
        ),
        "keeps": f"the densely knit core (k={k}; the innermost core is k={max_k})",
        "other_k": {str(kk): sizes[kk] for kk in range(2, max_k + 1) if kk != k},
    }


def _min_degree(G, network_id, target) -> Optional[Dict[str, Any]]:
    """The smallest degree cut-off leaving at most `target` nodes.

    Degrees count self-loops, as subgraph_high_degree_nodes does.
    """
    degrees = sorted((d for _, d in G.degree()), reverse=True)
    if not degrees or degrees[0] < 2:
        return None
    # Nodes with degree >= d, for each candidate d, descending.
    cutoff = None
    for d in sorted(set(degrees)):
        if d < 2:
            continue
        if sum(1 for x in degrees if x >= d) <= target:
            cutoff = d
            break
    if cutoff is None:
        return None
    nodes = [node for node, d in G.degree() if d >= cutoff]
    return {
        "method": "min_degree",
        "tool": "subgraph_high_degree_nodes",
        "arguments": {"network_id": network_id, "min_degree": cutoff},
        **_size(G, nodes),
        "_keep": nodes,
        "drops": f"every node with fewer than {cutoff} links, and their edges",
        "keeps": "the most connected nodes (hubs), even if they end up disconnected",
    }


def _attribute_groups(G, network_id, db):
    """Categorical attributes that split the network into a few groups."""
    rows = (
        db.query(models.NodeAttribute.attribute_name)
        .filter(
            models.NodeAttribute.network_id == network_id,
            models.NodeAttribute.role.in_((ROLE_DATA, ROLE_COMMUNITY)),
            models.NodeAttribute.measurement.in_((CATEGORICAL, DISCRETE)),
        )
        .order_by(models.NodeAttribute.attribute_name)
        .all()
    )
    found = []
    for (name,) in rows:
        values = load_node_attribute_values(network_id, name, db)
        counts = Counter(v for node, v in values.items() if node in G and v is not None)
        if not 2 <= len(counts) <= _MAX_GROUPS:
            continue
        groups = counts.most_common()
        found.append(
            {
                "method": "attribute_group",
                "tool": "subgraph_extract_filter",
                "arguments": {
                    "network_id": network_id,
                    "conditions": [{"attribute_name": name, "categories": ["<value>"]}],
                },
                "attribute": name,
                "groups": [
                    {"value": _plain(value), "nodes": count}
                    for value, count in groups[:_GROUPS_SHOWN]
                ],
                "groups_omitted": max(0, len(groups) - _GROUPS_SHOWN),
                "keeps": f"only the nodes whose `{name}` is one of the chosen values",
            }
        )
    found.sort(key=lambda c: -c["groups"][0]["nodes"])
    return found[:_ATTRIBUTES_SHOWN], max(0, len(found) - _ATTRIBUTES_SHOWN)


def _plain(value):
    """Whole floats as ints, so a group code reads 3, not 3.0."""
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value
