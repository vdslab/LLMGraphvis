"""Path semantics across persistence, weights, direction, and tool discovery."""

import json
from unittest.mock import MagicMock, patch

import networkx as nx
import pytest

from app.logic import paths
from app.logic.exporter import export_network_to_graphml
from app.logic.importer import parse_and_save_graphml
from app.logic.network_metadata import get_network_structure
from app.logic.utils.cache import compute_graph_state_hash
from app.logic.utils.graph_builder import build_graph_from_db
from common import models


@pytest.fixture
def network(db):
    net = models.Network(name="Path costs", is_directed=True)
    db.add(net)
    db.flush()
    nodes = {}
    for name in ("a", "b", "c", "isolated"):
        node = models.Node(network_id=net.id, node_id=name, label=name)
        db.add(node)
        db.flush()
        nodes[name] = node.id
    for source, target, cost in (("a", "b", 2), ("b", "c", 3), ("a", "c", 10)):
        db.add(
            models.Edge(
                network_id=net.id,
                edge_id=source + target,
                source_node_id=nodes[source],
                target_node_id=nodes[target],
                weight=cost,
            )
        )
    db.commit()
    return net


def test_weight_changes_path_and_reports_cost_and_hops(db, network):
    hops = paths.shortest_path(network.id, "a", "c", db)
    weighted = paths.shortest_path(network.id, "a", "c", db, weight="weight")
    assert hops["path"] == ["a", "c"]
    assert hops["length"] == 1
    assert weighted["path"] == ["a", "b", "c"]
    assert weighted["length"] == 5
    assert weighted["hops"] == 2
    assert paths.shortest_path(network.id, "c", "a", db)["reachable"] is False
    assert db.query(models.NodeAttribute).count() == 0


def test_distances_exclude_unreachable_and_apply_cutoff(db, network):
    result = paths.single_source_distances(network.id, "a", db, "weight", cutoff=3)
    assert result["distances"] == {"a": 0, "b": 2}
    assert result["node_count"] == 4
    assert paths.single_source_distances(network.id, "c", db)["distances"] == {"c": 0}


def test_negative_cost_requires_bellman_ford(db, network):
    edge = db.query(models.Edge).filter_by(edge_id="bc").one()
    edge.weight = -3
    db.commit()
    with pytest.raises(ValueError, match="bellman-ford"):
        paths.shortest_path(network.id, "a", "c", db, "weight")
    result = paths.shortest_path(network.id, "a", "c", db, "weight", "bellman-ford")
    assert result["length"] == -1
    # 'b' exceeds cutoff, but the path through it still reaches 'c' below cutoff.
    result = paths.single_source_distances(
        network.id, "a", db, "weight", "bellman-ford", cutoff=0
    )
    assert result["distances"] == {"a": 0, "c": -1}


def test_negative_cycle_is_not_reported_as_a_shortest_path(db, network):
    graph = build_graph_from_db(network.id, db, "weight")
    graph.add_edge("c", "a", weight=-20)
    with patch("app.logic.paths.build_graph_from_db", return_value=graph):
        with pytest.raises(nx.NetworkXUnbounded):
            paths.shortest_path(network.id, "a", "c", db, "weight", "bellman-ford")


def test_unknown_ids_and_invalid_costs_fail(db, network):
    with pytest.raises(ValueError, match="not found"):
        paths.shortest_path(network.id, "missing", "a", db)
    with pytest.raises(ValueError, match="cutoff"):
        paths.single_source_distances(network.id, "a", db, cutoff=-1)
    with pytest.raises(ValueError, match="no edge attribute"):
        paths.shortest_path(network.id, "a", "c", db, "missing")


def test_direction_affects_metadata_export_and_cache(db, network):
    before = compute_graph_state_hash(network.id, db)
    exported = nx.parse_graphml(export_network_to_graphml(network.id, db))
    assert exported.is_directed()
    assert not exported.has_edge("c", "a")
    assert get_network_structure(db, network.id)["density"] == 3 / 12
    network.is_directed = False
    db.commit()
    assert compute_graph_state_hash(network.id, db) != before
    assert paths.shortest_path(network.id, "c", "a", db)["path"] == ["c", "a"]


def test_graphml_import_preserves_direction(db):
    graph = nx.DiGraph()
    graph.add_edge("a", "b", weight=2)
    network_id = parse_and_save_graphml(900, "".join(nx.generate_graphml(graph)), db)
    restored = build_graph_from_db(network_id, db, "weight")
    assert restored.is_directed()
    assert set(restored.edges) == {("a", "b")}
    assert restored["a"]["b"]["weight"] == 2


def test_mcp_path_tools_execute_and_expose_choices(db, network):
    from app.core.mcp import mcp
    from app.mcp.tools.analysis.path import analysis_has_path, analysis_shortest_path

    session = MagicMock(wraps=db)
    session.close.return_value = None
    with patch("app.core.database.SessionLocal", return_value=session):
        assert analysis_has_path(network.id, "c", "a")["reachable"] is False
        result = json.loads(analysis_shortest_path(network.id, "a", "c", "weight"))
        assert result["length"] == 5
    tool = mcp._tool_manager.get_tool("analysis_single_source_distances")
    assert tool.parameters["properties"]["method"]["enum"] == [
        "dijkstra",
        "bellman-ford",
    ]
