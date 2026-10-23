"""Edge backbones keep every node and only the strongest edges (ADR 0040)."""

import itertools

from app.logic import backbone, reduction
from common import models


def _network(db, groups=2, size=5, bridge_weight=0.1, inner_weight=0.9):
    """`groups` cliques of `size` nodes, every pair of groups fully linked weakly."""
    network = models.Network(name="dense")
    db.add(network)
    db.flush()
    nodes = {}
    for g in range(groups):
        for i in range(size):
            node = models.Node(network_id=network.id, node_id=f"g{g}n{i}")
            db.add(node)
            db.flush()
            nodes[(g, i)] = node.id
    count = 0
    for a, b in itertools.combinations(nodes, 2):
        weight = inner_weight if a[0] == b[0] else bridge_weight
        db.add(
            models.Edge(
                network_id=network.id,
                edge_id=f"e{count}",
                source_node_id=nodes[a],
                target_node_id=nodes[b],
                weight=weight,
            )
        )
        count += 1
    db.commit()
    return network


def test_top_k_keeps_every_node_and_separates_groups(db):
    network = _network(db)
    result = backbone.extract_backbone(network.id, db, "top_k", k=2)
    child = db.get(models.Network, result["created_network_id"])

    assert child.parent_network_id == network.id
    assert db.query(models.Node).filter_by(network_id=child.id).count() == 10
    edges = db.query(models.Edge).filter_by(network_id=child.id).all()
    assert edges and all(edge.weight == 0.9 for edge in edges)
    assert result["connected_parts"] == 2
    assert result["strength"] == "weight"


def test_threshold_keeps_edges_at_or_above_the_weight(db):
    network = _network(db)
    result = backbone.extract_backbone(
        network.id, db, "threshold", k=None, min_weight=0.5
    )
    assert result["edges"] == 20  # two 5-cliques


def test_unweighted_network_uses_shared_neighbours(db):
    network = _network(db, bridge_weight=1.0, inner_weight=1.0)
    edges = db.query(models.Edge).filter_by(network_id=network.id).all()
    _, measured_by = backbone.edge_strengths(edges)
    assert measured_by == "common_neighbors"


def test_dense_network_gets_measured_backbone_candidates(db):
    network = _network(db, groups=3, size=6)
    candidates = [
        c
        for c in reduction.suggest_reductions(network.id, db)["candidates"]
        if c["method"] == "edge_backbone"
    ]
    assert [c["arguments"]["k"] for c in candidates] == list(backbone.SUGGESTED_K)
    assert all(c["nodes"] == 18 for c in candidates)
    assert candidates[0]["edges"] <= candidates[-1]["edges"]


def test_sparse_network_gets_no_backbone_candidate(db):
    network = _network(db, groups=1, size=3)
    assert backbone.suggest_backbones(network.id, db) == []
