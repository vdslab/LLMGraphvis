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


def test_undirected_bottlenecks_and_closure_do_not_mutate(db, graph):
    assert analysis_connected_components(graph.id)["components"] == [
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
    assert analysis_strongly_connected_components(graph.id)["components"] == [
        ["a", "b", "c"],
        ["d"],
        ["e"],
    ]
    assert analysis_weakly_connected_components(graph.id)["components"] == [
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
