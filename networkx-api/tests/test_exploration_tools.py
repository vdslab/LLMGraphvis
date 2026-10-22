"""Bounded exploration tools: routes, shared neighbours, node tables, groups."""

import json

import pytest
from app.core import database
from app.mcp import tools

from common import models


@pytest.fixture
def square(db, monkeypatch):
    """a-b-d and a-c-d (two equal routes), plus e hanging off d; groups X/Y."""
    monkeypatch.setattr(db, "close", lambda: None)
    monkeypatch.setattr(database, "SessionLocal", lambda: db)
    net = models.Network(name="square")
    db.add(net)
    db.flush()
    ids = {}
    for name in "abcde":
        node = models.Node(network_id=net.id, node_id=name, label=name.upper())
        db.add(node)
        db.flush()
        ids[name] = node.id
    for i, (s, t) in enumerate([("a", "b"), ("b", "d"), ("a", "c"), ("c", "d"), ("d", "e")]):
        db.add(models.Edge(network_id=net.id, edge_id=f"e{i}",
                           source_node_id=ids[s], target_node_id=ids[t]))
    db.commit()

    from app.logic.attributes import bulk_save_node_attributes

    bulk_save_node_attributes(net.id, "group", "string",
                              {ids[n]: g for n, g in zip("abcde", "XXYYY")}, db)
    bulk_save_node_attributes(net.id, "score", "float",
                              {ids[n]: float(i) for i, n in enumerate("abcde")}, db)
    db.commit()
    return net.id


def test_k_shortest_paths_returns_alternatives_shortest_first(square):
    result = tools.analysis_k_shortest_paths(square, "a", "e", k=3)

    assert [p["hops"] for p in result["paths"]] == [3, 3]
    assert {tuple(p["path"]) for p in result["paths"]} == {
        ("a", "b", "d", "e"), ("a", "c", "d", "e"),
    }


def test_common_neighbors_and_overlap(square):
    result = tools.node_common_neighbors(square, "b", "c")

    assert result["common_neighbors"] == ["d", "a"]  # best-connected first
    assert result["adjacent"] is False
    assert result["jaccard"] == 1.0


def test_node_compare_builds_one_table(square):
    result = tools.node_compare(square, ["a", "d"], attributes=["score"])

    assert result["nodes"]["d"] == {"label": "D", "degree": 3, "score": 3.0}
    with pytest.raises(RuntimeError, match="Unknown attribute"):
        tools.node_compare(square, ["a"], attributes=["nope"])


def test_neighbors_are_limited_but_degree_is_complete(square):
    result = json.loads(tools.node_get_neighbors(square, "d", limit=1))

    assert result["degree"] == 3
    assert len(result["neighbors"]) == 1 and result["omitted"] == 2


def test_attribute_distribution_numeric_and_grouped(square):
    result = tools.analysis_attribute_distribution(square, "score", group_by="group")

    assert result["kind"] == "numeric"
    assert result["summary"]["max"] == 4.0
    assert sum(b["count"] for b in result["histogram"]) == 5
    assert result["by_group"]["X"]["mean"] == 0.5
    assert result["by_group"]["Y"]["count"] == 3


def test_group_connectivity_counts_within_and_between(square):
    result = tools.analysis_group_connectivity(square, "group")

    assert result["edges_within"] == 3  # a-b, c-d, d-e
    assert result["edges_between"] == 2  # b-d, a-c
    assert result["strongest_links"] == [{"groups": ["X", "Y"], "edges": 2}]
