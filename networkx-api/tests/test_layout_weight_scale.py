"""Strength weights are unit-free, and size-aware ForceAtlas2 (ADR 0017)."""

from unittest.mock import patch

import networkx as nx
import pytest

from app.logic.layout import calculate_layout, load_layout_positions
from tests.test_layout_parameters import setup_graph


def _positions(db, network_id, layout):
    return load_layout_positions(network_id, layout, db)


@pytest.mark.parametrize("layout", ["forceatlas2", "spring"])
def test_scaling_every_weight_leaves_the_layout_unchanged(db, layout):
    base = [1.0, 2.0, 5.0, 1.0, 3.0, 8.0, 2.0]
    setup_graph(db, network_id=1, n=8, weights=base)
    setup_graph(db, network_id=2, n=8, weights=[w * 10 for w in base])

    calculate_layout(1, layout, db)
    calculate_layout(2, layout, db)

    one, ten = _positions(db, 1, layout), _positions(db, 2, layout)
    for node, (x, y) in one.items():
        assert ten[node] == pytest.approx((x, y), abs=1e-6)


def test_note_reports_the_normalization(db):
    setup_graph(db, n=6, weights=[10.0, 20.0, 30.0, 40.0, 50.0])
    info = calculate_layout(1, "forceatlas2", db)
    assert "divided by their median (30)" in info["weight_note"]
    assert "weight_normalization" not in info["parameters"]


def test_distance_weights_are_not_normalized(db):
    setup_graph(db, n=6, weights=[10.0, 20.0, 30.0, 40.0, 50.0])
    info = calculate_layout(1, "kamada_kawai", db, overrides={"weight": "weight"})
    assert "median" not in info["weight_note"]


def test_unweighted_opt_out_is_untouched(db):
    setup_graph(db, n=6, weights=[10.0, 20.0, 30.0, 40.0, 50.0])
    info = calculate_layout(1, "forceatlas2", db, overrides={"weight": "none"})
    assert info["weight"] is None
    assert "median" not in info["weight_note"]


class TestSizeAware:
    def test_node_size_is_filled_from_the_drawn_sizes(self, db):
        setup_graph(db, n=6)
        calls = []
        real = nx.forceatlas2_layout

        def spy(G, **kwargs):
            calls.append(kwargs.get("node_size"))
            return real(G, **kwargs)

        with patch("networkx.forceatlas2_layout", side_effect=spy):
            info = calculate_layout(1, "forceatlas2", db, overrides={"size_aware": True})

        # First pass without sizes, second with radii for every node.
        assert calls[0] is None
        assert set(calls[1]) == {f"n{i}" for i in range(6)}
        assert all(r > 0 for r in calls[1].values())
        assert "size_aware" not in info["parameters"]
        assert str(info["parameters"]["node_size"]).startswith("digest:")

    def test_cannot_combine_with_explicit_node_size(self, db):
        setup_graph(db, n=4)
        with pytest.raises(ValueError, match="size_aware or node_size"):
            calculate_layout(
                1,
                "forceatlas2",
                db,
                overrides={"size_aware": True, "node_size": {"n0": 1.0}},
            )

    def test_changes_the_cache_key(self, db):
        setup_graph(db, n=6)
        calculate_layout(1, "forceatlas2", db)
        info = calculate_layout(1, "forceatlas2", db, overrides={"size_aware": True})
        assert info["cached"] is False
