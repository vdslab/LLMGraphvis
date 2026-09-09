import networkx as nx
import pytest
from app.logic import structure_metrics as metrics
from app.logic.utils.graph_builder import build_graph_from_db
from test_layout_parameters import setup_graph

from common import models


def test_core_numbers_and_triangles_are_read_only(db):
    setup_graph(db)
    graph = build_graph_from_db(1, db)
    assert metrics.core_numbers(1, db)["core_numbers"] == nx.core_number(graph)
    assert metrics.triangle_counts(1, db)["total_triangles"] == 0
    assert metrics.triangle_counts(1, db, ["n1"]) == {"triangles_by_node": {"n1": 0}}
    assert db.query(models.NodeAttribute).count() == 0


def test_edge_betweenness_matches_networkx_sampling_and_weights(db):
    setup_graph(db, weighted=True)
    graph = build_graph_from_db(1, db, "weight")
    result = metrics.edge_betweenness(1, db, k=3, weight="weight", seed=7)
    actual = {(row["source"], row["target"]): row["value"] for row in result["edges"]}
    assert actual == nx.edge_betweenness_centrality(graph, k=3, weight="weight", seed=7)
    with pytest.raises(ValueError, match="node count"):
        metrics.edge_betweenness(1, db, k=999)


def test_partition_evaluation_matches_networkx_without_detecting(db):
    setup_graph(db, attrs={"group": {f"n{i}": "A" if i < 3 else "B" for i in range(6)}})
    graph = build_graph_from_db(1, db)
    expected = nx.community.modularity(
        graph, [{"n0", "n1", "n2"}, {"n3", "n4", "n5"}], weight=None, resolution=0.5
    )
    result = metrics.partition_modularity(1, db, "group", resolution=0.5)
    assert result["modularity"] == pytest.approx(expected)
    assert db.query(models.NodeAttribute).count() == 1
    with pytest.raises(ValueError, match="Every node"):
        metrics.partition_modularity(1, db, "missing")


def test_directed_triangles_rejected_without_conversion(db):
    setup_graph(db)
    db.get(models.Network, 1).is_directed = True
    db.commit()
    with pytest.raises(ValueError, match="undirected"):
        metrics.triangle_counts(1, db)
