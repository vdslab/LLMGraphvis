from unittest.mock import patch

import networkx as nx
import pytest
from app.logic.community import calculate_community
from app.logic.layout import calculate_layout
from app.logic.utils.cache import compute_graph_state_hash
from test_layout_parameters import add_edge_attribute, setup_graph

from common import models


def test_source_weight_change_invalidates_result_but_derived_values_do_not(db):
    setup_graph(db)
    add_edge_attribute(db, 1, "strength", [1, 2, 3, 4, 5])
    before = compute_graph_state_hash(1, db)
    calculate_layout(1, "spring", db, overrides={"weight": "strength"})
    assert compute_graph_state_hash(1, db) == before
    with patch("networkx.spring_layout") as compute:
        calculate_layout(1, "spring", db, overrides={"weight": "strength"})
    compute.assert_not_called()
    value = db.query(models.EdgeFloatAttributeValue).first()
    value.float_value = 100
    db.commit()
    assert compute_graph_state_hash(1, db) != before
    with patch("networkx.spring_layout", wraps=nx.spring_layout) as compute:
        calculate_layout(1, "spring", db, overrides={"weight": "strength"})
    compute.assert_called_once()


@pytest.mark.parametrize(
    "algorithm,function,options",
    [
        (
            "louvain",
            "louvain_communities",
            dict(resolution=0.7, threshold=1e-5, max_level=2, seed=3, weight="weight"),
        ),
        (
            "greedy_modularity",
            "greedy_modularity_communities",
            dict(resolution=0.7, cutoff=2, best_n=2, weight="weight"),
        ),
    ],
)
def test_community_parameters_reach_networkx_and_cache(
    db, algorithm, function, options
):
    setup_graph(db, weighted=True)
    original = getattr(nx.community, function)
    with patch(f"networkx.community.{function}", wraps=original) as compute:
        calculate_community(1, algorithm, db, **options)
        assert compute.call_args.kwargs == options
        calculate_community(1, algorithm, db, **options)
        compute.assert_called_once()


def test_community_rejects_irrelevant_options_before_saving(db):
    setup_graph(db)
    with pytest.raises(ValueError, match="Unsupported parameters"):
        calculate_community(1, "label_propagation", db, resolution=2)
    assert db.query(models.NodeAttribute).count() == 0


@pytest.mark.parametrize(
    "options",
    [
        {"pos": {"missing": [0, 0]}},
        {"pos": {"n0": [float("nan"), 0]}},
        {"pos": {"n0": [0, 0]}, "fixed": ["n1"]},
        {"pos": {"n0": [0, 0]}, "init_from_layout": "circular"},
    ],
)
def test_bad_initial_positions_do_not_save_layout(db, options):
    setup_graph(db)
    with pytest.raises(ValueError):
        calculate_layout(1, "spring", db, overrides=options)
    assert db.query(models.NodeAttribute).count() == 0
