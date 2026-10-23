"""Reduction candidates are measured, never created (ADR 0034)."""

from tests.test_subgraph_features_comprehensive import create_source_network

from app.logic import network_metadata, reduction, subgraph
from common import models


def _by_method(result):
    return {c["method"]: c for c in result["candidates"]}


def test_candidates_report_the_size_each_tool_would_leave(db):
    # Star (5) + path (4) + 4-clique + isolated node; see create_source_network.
    network = create_source_network(db)

    result = reduction.suggest_reductions(network.id, db, target_nodes=3)
    by = _by_method(result)

    assert (result["nodes"], result["edges"]) == (14, 13)
    assert by["largest_component"]["nodes"] == 5
    assert by["largest_component"]["tool"] == "subgraph_largest_component"
    # Only the 4-clique reaches k=2 and k=3; neither fits 3 nodes, so the
    # innermost core is offered.
    assert by["k_core"]["arguments"]["k"] == 3
    assert (by["k_core"]["nodes"], by["k_core"]["edges"]) == (4, 6)
    assert by["min_degree"]["arguments"]["min_degree"] == 4
    assert by["min_degree"]["nodes"] == 1


def test_suggesting_creates_no_network(db):
    network = create_source_network(db)
    before = db.query(models.Network).count()

    reduction.suggest_reductions(network.id, db)

    assert db.query(models.Network).count() == before


def test_categorical_attribute_lists_its_group_sizes(db):
    network = create_source_network(db)
    attr = (
        db.query(models.NodeAttribute)
        .filter_by(network_id=network.id, attribute_name="group")
        .one()
    )
    attr.measurement = "categorical"
    db.commit()

    by = _by_method(reduction.suggest_reductions(network.id, db))

    group = by["attribute_group"]
    assert group["attribute"] == "group"
    assert group["tool"] == "subgraph_extract_filter"
    assert sorted((g["value"], g["nodes"]) for g in group["groups"]) == [
        ("A", 5),
        ("B", 4),
        ("C", 5),
    ]


def test_largest_component_also_works_on_a_directed_network(db):
    network = create_source_network(db)
    network.is_directed = True
    db.commit()

    by = _by_method(reduction.suggest_reductions(network.id, db))
    created = subgraph.create_largest_component_subgraph(network.id, db)

    child = created["new_network_id"]
    assert db.query(models.Node).filter_by(network_id=child).count() == 5
    assert by["largest_component"]["nodes"] == 5


def test_structure_says_whether_the_network_is_large(db):
    network = create_source_network(db)

    structure = network_metadata.get_network_structure(db, network.id)

    assert structure["large"] is False
    threshold = structure["large_threshold_nodes"]
    assert reduction.is_large(threshold) and not reduction.is_large(threshold - 1)
