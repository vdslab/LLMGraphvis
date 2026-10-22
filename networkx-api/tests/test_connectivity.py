from unittest.mock import MagicMock, patch

import pytest

from app.mcp.tools.analysis.connectivity import (
    analysis_articulation_points,
    analysis_bridges,
    analysis_connected_components,
    analysis_strongly_connected_components,
    analysis_transitivity,
    analysis_weakly_connected_components,
)
from common import models


@pytest.fixture
def graph(db):
    network = models.Network(name="triangle with tail")
    db.add(network)
    db.flush()
    nodes = {}
    for name in "abcde":
        node = models.Node(network_id=network.id, node_id=name)
        db.add(node)
        db.flush()
        nodes[name] = node.id
    for source, target in [("a", "b"), ("b", "c"), ("c", "a"), ("c", "d")]:
        db.add(
            models.Edge(
                network_id=network.id,
                edge_id=source + target,
                source_node_id=nodes[source],
                target_node_id=nodes[target],
            )
        )
    db.commit()
    session = MagicMock(wraps=db)
    session.close.return_value = None
    with patch("app.core.database.SessionLocal", return_value=session):
        yield network


def _members(result):
    return [component["node_ids"] for component in result["components"]]


def test_undirected_bottlenecks_and_closure_do_not_mutate(db, graph):
    assert _members(analysis_connected_components(graph.id)) == [
        ["a", "b", "c", "d"],
        ["e"],
    ]
    assert analysis_bridges(graph.id)["bridges"] == [["c", "d"]]
    assert analysis_articulation_points(graph.id)["node_ids"] == ["c"]
    assert analysis_transitivity(graph.id)["transitivity"] == pytest.approx(0.6)
    assert db.query(models.Network).count() == 1
    assert db.query(models.NodeAttribute).count() == 0
    assert db.query(models.Edge).count() == 4


def test_strong_and_weak_components_are_different(db, graph):
    graph.is_directed = True
    db.commit()
    assert _members(analysis_strongly_connected_components(graph.id)) == [
        ["a", "b", "c"],
        ["d"],
        ["e"],
    ]
    assert _members(analysis_weakly_connected_components(graph.id)) == [
        ["a", "b", "c", "d"],
        ["e"],
    ]
    with pytest.raises(RuntimeError, match="Incompatible graph direction"):
        analysis_connected_components(graph.id)
    with pytest.raises(RuntimeError, match="requires an undirected"):
        analysis_bridges(graph.id)


def test_empty_graph(db, graph):
    db.query(models.Edge).delete()
    db.query(models.Node).delete()
    db.commit()
    assert analysis_connected_components(graph.id)["components"] == []
    assert analysis_articulation_points(graph.id)["node_ids"] == []
    assert analysis_transitivity(graph.id)["transitivity"] == 0


def test_results_are_bounded_but_totals_cover_everything(db, graph):
    """ADR 0024: a large graph must not produce a proportionally large result."""
    result = analysis_connected_components(graph.id, limit=1, node_limit=2)
    assert result["count"] == 2
    assert result["omitted"] == 1
    assert result["size_distribution"] == {"4": 1, "1": 1}
    assert result["components"] == [
        {"size": 4, "node_ids": ["a", "b"], "omitted_nodes": 2}
    ]
    points = analysis_articulation_points(graph.id, limit=1)
    assert points["count"] == 1 and points["pieces_added"] == {"c": 1}
