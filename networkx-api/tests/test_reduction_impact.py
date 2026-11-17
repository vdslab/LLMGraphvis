"""What a reduction loses, measured before and after it is applied (ADR 0049)."""

import networkx as nx
from tests.test_subgraph_features_comprehensive import create_source_network

from app.logic import reduction, subgraph
from app.logic.reduction_impact import (
    DROPS_GROUPS,
    FRAGMENTS,
    LOUVAIN_SOURCE,
    SKEWS_GROUPS,
    Groups,
    assess,
    describe,
    describe_extraction,
    structural_groups,
)
from common import models


def _groups(*members):
    return Groups({str(i): set(m) for i, m in enumerate(members)}, "test")


def test_cutting_a_path_in_the_middle_fragments_it():
    G = nx.path_graph(200)
    keep = [v for v in G if v % 10 != 5]  # remove every tenth node

    impact = assess(G, keep, _groups(range(100), range(100, 200)))

    assert impact["new_pieces"] == 20  # 20 cuts, 21 pieces
    assert FRAGMENTS in impact["issues"]


def test_dropping_a_group_is_named_with_its_size():
    G = nx.disjoint_union(nx.complete_graph(10), nx.complete_graph(30))
    keep = range(10, 40)

    impact = assess(G, keep, _groups(range(10), range(10, 40)))

    assert impact["issues"] == [DROPS_GROUPS]
    assert impact["groups_lost"] == [{"group": "0", "nodes": 10}]
    assert impact["new_pieces"] == 0


def test_uneven_shares_skew_the_groups():
    G = nx.disjoint_union(nx.complete_graph(10), nx.complete_graph(10))
    keep = list(range(3)) + list(range(10, 20))

    impact = assess(G, keep, _groups(range(10), range(10, 20)))

    assert impact["issues"] == [SKEWS_GROUPS]
    assert impact["group_kept_share_range"] == [0.3, 1.0]


def test_dropping_an_existing_island_is_not_fragmentation():
    G = nx.disjoint_union(nx.complete_graph(20), nx.complete_graph(20))

    impact = assess(G, range(20), _groups(range(20), range(20, 40)))

    assert impact["new_pieces"] == 0
    assert FRAGMENTS not in impact["issues"]


def test_trimming_leaves_loses_nothing_named():
    G = nx.complete_graph(30)
    G.add_edges_from((i, 100 + i) for i in range(30))  # one leaf per node

    impact = assess(G, range(30), _groups(range(30)))

    assert impact["issues"] == []
    assert impact["isolated_created"] == 0
    assert "Issues: none" in describe(impact)


def _cycle_network(db, n=8):
    network = models.Network(name="cycle")
    db.add(network)
    db.commit()
    nodes = [models.Node(network_id=network.id, node_id=str(i)) for i in range(n)]
    db.add_all(nodes)
    db.commit()
    db.add_all(
        models.Edge(
            network_id=network.id,
            edge_id=f"{i}",
            source_node_id=nodes[i].id,
            target_node_id=nodes[(i + 1) % n].id,
        )
        for i in range(n)
    )
    db.commit()
    return network


def test_cuts_that_keep_every_node_are_not_offered(db):
    # A ring: one component, 2-core and degree >= 2 are the whole network.
    network = _cycle_network(db)

    result = reduction.suggest_reductions(network.id, db, target_nodes=3)

    assert [c["method"] for c in result["candidates"]] == []


def test_every_node_dropping_candidate_carries_its_impact(db):
    network = create_source_network(db)

    result = reduction.suggest_reductions(network.id, db, target_nodes=3)

    for candidate in result["candidates"]:
        if candidate["method"] in ("largest_component", "k_core", "min_degree"):
            assert set(candidate["impact"]["issues"]) <= {
                FRAGMENTS,
                DROPS_GROUPS,
                SKEWS_GROUPS,
            }
            assert "_keep" not in candidate
    assert result["groups_by"] == LOUVAIN_SOURCE


def test_a_recorded_community_attribute_is_preferred(db):
    network = create_source_network(db)
    db.query(models.NodeAttribute).filter_by(
        network_id=network.id, attribute_name="group"
    ).one().role = "community"
    db.commit()

    from app.logic.utils.graph_builder import build_graph_from_db

    groups = structural_groups(build_graph_from_db(network.id, db), network.id, db)

    assert groups.source == "attribute `group`"
    assert sorted(len(m) for m in groups.members.values()) == [4, 5, 5]


def test_an_extraction_reports_what_it_lost(db):
    network = create_source_network(db)
    child = subgraph.create_k_core_subgraph(network.id, 3, db)["new_network_id"]

    note = describe_extraction(network.id, child, db)

    assert note.startswith(" Reduction impact: kept 29% of nodes")


def test_an_unmeasurable_extraction_adds_nothing(db):
    assert describe_extraction(10**6, 10**6 + 1, db) == ""


def test_a_moderate_but_uneven_cut_still_skews():
    """29% vs 48% kept (the embedded syllabus degree cut) is a skew."""
    G = nx.disjoint_union(nx.complete_graph(100), nx.complete_graph(100))
    keep = list(range(29)) + list(range(100, 148))

    impact = assess(G, keep, _groups(range(100), range(100, 200)))

    assert impact["issues"] == [SKEWS_GROUPS]


def test_nearly_even_shares_do_not_skew():
    G = nx.disjoint_union(nx.complete_graph(100), nx.complete_graph(100))
    keep = list(range(76)) + list(range(100, 197))

    assert assess(G, keep, _groups(range(100), range(100, 200)))["issues"] == []
