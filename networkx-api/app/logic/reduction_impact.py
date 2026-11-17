"""What a reduction loses, measured before and after it is applied (ADR 0049).

Counting the nodes a reduction leaves says nothing about whether it is safe.
On the 3,393-node syllabus network a 3-core kept 40% of the nodes but split
them into 201 pieces; on the embedded syllabus, a kNN graph where every node
has ten neighbours, the k-core removed nothing at all. Whether a loss matters
depends on the question, so this module only measures and names the losses;
the skill `network-reduction` says which ones each kind of question tolerates.
"""

from typing import Any, Dict, Hashable, Iterable, List, Set

import networkx as nx
from sqlalchemy.orm import Session

from app.logic.attribute_semantics import ROLE_COMMUNITY
from app.logic.attributes import load_node_attribute_values
from common import models

# A group is checked only if it holds at least this share of the network and
# this many nodes; smaller ones are slivers whose loss tells little.
GROUP_MIN_SHARE = 0.01
GROUP_MIN_NODES = 5
# A group counts as lost when less than this share of its nodes is kept.
LOST_SHARE = 0.1
# The best-kept group keeping this many times the share of the worst-kept one
# means the reduced network over-represents some groups: sizes and comparisons
# between groups no longer hold. On the embedded syllabus a degree cut kept
# 29% to 48% of each group (1.7x) and was still chosen for comparing groups.
SKEW_RATIO = 1.5
# New connected pieces beyond this share of the kept nodes mean the reduction
# cuts links the analysis may depend on (paths, distances, components).
FRAGMENT_SHARE = 0.01
# Lost groups named per result, largest first.
_GROUPS_NAMED = 5

FRAGMENTS = "fragments"
DROPS_GROUPS = "drops_groups"
SKEWS_GROUPS = "skews_groups"
ISSUES = (FRAGMENTS, DROPS_GROUPS, SKEWS_GROUPS)

LOUVAIN_SOURCE = "louvain (computed for this check, not stored)"


class Groups:
    """The partition a reduction is checked against, and where it came from."""

    def __init__(self, members: Dict[str, Set[Hashable]], source: str):
        self.members = members
        self.source = source


def structural_groups(G: nx.Graph, network_id: int, db: Session) -> Groups:
    """The network's most recent community attribute, else a Louvain partition.

    A recorded partition is what the user has seen coloured, so it is the one
    whose loss they would notice. Without one, Louvain (fixed seed) stands in.
    """
    attribute = (
        db.query(models.NodeAttribute.attribute_name)
        .filter(
            models.NodeAttribute.network_id == network_id,
            models.NodeAttribute.role == ROLE_COMMUNITY,
        )
        .order_by(models.NodeAttribute.id.desc())
        .first()
    )
    if attribute is not None:
        values = load_node_attribute_values(network_id, attribute[0], db)
        members: Dict[str, Set[Hashable]] = {}
        for node, value in values.items():
            if node in G and value is not None:
                members.setdefault(str(_plain(value)), set()).add(node)
        if len(members) >= 2:
            return Groups(members, f"attribute `{attribute[0]}`")
    U = G.to_undirected() if G.is_directed() else G
    if U.number_of_edges() == 0:
        return Groups({}, LOUVAIN_SOURCE)
    parts = nx.community.louvain_communities(U, seed=0)
    parts.sort(key=lambda c: (-len(c), min(map(str, c))))
    return Groups({str(i): set(c) for i, c in enumerate(parts)}, LOUVAIN_SOURCE)


def _components(G: nx.Graph) -> List[Set[Hashable]]:
    if G.is_directed():
        return list(nx.weakly_connected_components(G))
    return list(nx.connected_components(G))


def assess(G: nx.Graph, keep: Iterable[Hashable], groups: Groups) -> Dict[str, Any]:
    """Measure what keeping only `keep` (and the edges among it) loses."""
    keep = set(keep) & set(G)
    n, m = G.number_of_nodes(), G.number_of_edges()
    sub = G.subgraph(keep)

    # Pieces the reduction creates: kept pieces beyond the original components
    # they came from. Isolating a node counts as one.
    component_of = {}
    for i, component in enumerate(_components(G)):
        for node in component:
            component_of[node] = i
    pieces = _components(sub)
    touched = {component_of[node] for node in keep}
    new_pieces = len(pieces) - len(touched)
    isolated = sum(1 for v in keep if sub.degree(v) == 0 and G.degree(v) > 0)
    largest = max((len(p) for p in pieces), default=0)

    checked = [
        (label, members)
        for label, members in groups.members.items()
        if len(members) >= max(GROUP_MIN_NODES, GROUP_MIN_SHARE * n)
    ]
    shares = [
        (label, len(members), len(members & keep) / len(members))
        for label, members in checked
    ]
    lost = sorted(
        ((label, size) for label, size, share in shares if share < LOST_SHARE),
        key=lambda item: -item[1],
    )

    issues = []
    if new_pieces > max(1, FRAGMENT_SHARE * len(keep)):
        issues.append(FRAGMENTS)
    if lost:
        issues.append(DROPS_GROUPS)
    kept_shares = [share for _, _, share in shares]
    if (
        len(kept_shares) >= 2
        and max(kept_shares) >= SKEW_RATIO * min(kept_shares)
        and not lost
    ):
        issues.append(SKEWS_GROUPS)

    return {
        "kept_node_share": _share(len(keep), n),
        "kept_edge_share": _share(sub.number_of_edges(), m),
        "new_pieces": max(0, new_pieces),
        "isolated_created": isolated,
        "largest_piece_nodes": largest,
        "groups_by": groups.source,
        "groups_checked": len(checked),
        "groups_lost": [
            {"group": label, "nodes": size} for label, size in lost[:_GROUPS_NAMED]
        ],
        "groups_lost_count": len(lost),
        "group_kept_share_range": (
            [round(min(kept_shares), 2), round(max(kept_shares), 2)]
            if kept_shares
            else None
        ),
        "issues": issues,
    }


def assess_backbone(
    G: nx.Graph, connected_parts: int, isolated_nodes: int
) -> Dict[str, Any]:
    """The fragmentation check for an edge backbone, which keeps every node."""
    new_pieces = connected_parts - len(_components(G))
    issues = [FRAGMENTS] if new_pieces > max(1, FRAGMENT_SHARE * len(G)) else []
    return {"new_pieces": max(0, new_pieces), "issues": issues}


def describe_extraction(
    source_network_id: int, kept_network_id: int, db: Session
) -> str:
    """`describe` for a created child network; empty if it cannot be measured.

    Fails open: the extraction already happened, and a missing note must not
    turn it into an error.
    """
    try:
        impact = assess_extraction(source_network_id, kept_network_id, db)
    except Exception:  # noqa: BLE001 - see docstring
        return ""
    return " " + describe(impact)


def assess_extraction(
    source_network_id: int, kept_network_id: int, db: Session
) -> Dict[str, Any]:
    """What a child network created by a reduction lost against its source."""
    from app.logic.utils.graph_builder import build_graph_from_db

    G = build_graph_from_db(source_network_id, db)
    kept = [
        row.node_id
        for row in db.query(models.Node.node_id).filter_by(network_id=kept_network_id)
    ]
    return assess(G, kept, structural_groups(G, source_network_id, db))


def describe(impact: Dict[str, Any]) -> str:
    """One sentence on what a reduction lost, for a tool's return message."""
    parts = [
        f"kept {impact['kept_node_share']:.0%} of nodes and "
        f"{impact['kept_edge_share']:.0%} of edges"
    ]
    if impact["new_pieces"]:
        isolated = impact["isolated_created"]
        parts.append(
            f"{impact['new_pieces']} new disconnected pieces"
            + (f" ({isolated} nodes left with no link)" if isolated else "")
        )
    if impact["groups_lost_count"]:
        parts.append(
            f"{impact['groups_lost_count']} of {impact['groups_checked']} groups "
            f"({impact['groups_by']}) almost entirely dropped"
        )
    elif SKEWS_GROUPS in impact["issues"]:
        low, high = impact["group_kept_share_range"]
        parts.append(
            f"groups kept unevenly ({low:.0%} to {high:.0%} of their nodes, "
            f"{impact['groups_by']})"
        )
    issues = ", ".join(impact["issues"]) or "none"
    return f"Reduction impact: {'; '.join(parts)}. Issues: {issues}."


def _share(part: int, whole: int) -> float:
    return round(part / whole, 3) if whole else 0.0


def _plain(value):
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value
