from unittest.mock import patch

import networkx as nx
import pytest
from app.logic.centrality import calculate_centrality, get_top_nodes
from app.logic.utils.graph_builder import build_graph_from_db

from common import models


@pytest.fixture
def graph(db):
    net = models.Network(name="directed ranks", is_directed=True)
    db.add(net)
    db.flush()
    nodes = {}
    for name in "abc":
        node = models.Node(network_id=net.id, node_id=name)
        db.add(node)
        db.flush()
        nodes[name] = node.id
    for source, target, weight in [("a", "b", 1), ("a", "c", 4), ("b", "c", 2)]:
        db.add(
            models.Edge(
                network_id=net.id,
                edge_id=source + target,
                source_node_id=nodes[source],
                target_node_id=nodes[target],
                weight=weight,
            )
        )
    db.commit()
    return net.id


def test_pagerank_options_reach_networkx_and_saved_name_matches_tool(db, graph):
    G = build_graph_from_db(graph, db, "weight")
    options = dict(
        weight="weight",
        personalization={"a": 1},
        dangling={"b": 1},
        nstart={"a": 1, "b": 1, "c": 1},
        max_iter=500,
        tol=1e-9,
    )
    expected = nx.pagerank(G, alpha=0.7, **options)
    actual = calculate_centrality(graph, "pagerank", db, damping_factor=0.7, **options)
    assert actual == pytest.approx(expected)
    assert get_top_nodes(graph, "pagerank", 3, "desc", db)
    with patch("networkx.pagerank", side_effect=AssertionError("cache was missed")):
        assert (
            calculate_centrality(graph, "pagerank", db, damping_factor=0.7, **options)
            == actual
        )
    changed = calculate_centrality(graph, "pagerank", db, damping_factor=0.4, **options)
    assert changed != actual


def test_betweenness_and_closeness_options_match_networkx(db, graph):
    G = build_graph_from_db(graph, db)
    result = calculate_centrality(graph, "betweenness", db, k=2, seed=3, endpoints=True)
    assert result == nx.betweenness_centrality(G, k=2, seed=3, endpoints=True)
    assert calculate_centrality(
        graph, "closeness", db, wf_improved=False
    ) == nx.closeness_centrality(G, wf_improved=False)


def test_incoming_and_outgoing_degree_are_distinct(db, graph):
    assert calculate_centrality(graph, "in_degree", db, normalized=False) == {
        "a": 0,
        "b": 1,
        "c": 2,
    }
    assert calculate_centrality(graph, "out_degree", db, normalized=False) == {
        "a": 2,
        "b": 1,
        "c": 0,
    }


def test_bad_distribution_and_nonconvergence_do_not_cache(db, graph):
    with pytest.raises(ValueError, match="unknown node"):
        calculate_centrality(graph, "pagerank", db, personalization={"typo": 1})
    with pytest.raises(nx.PowerIterationFailedConvergence):
        calculate_centrality(graph, "pagerank", db, max_iter=1, tol=1e-20)
    assert db.query(models.NodeAttribute).count() == 0
