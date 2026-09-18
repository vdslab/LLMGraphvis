"""Layout readability metrics (logic/layout_quality.py, ADR 0017)."""

import time

import networkx as nx
import numpy as np
import pytest

from app.logic import layout_quality as lq


def _square_with_diagonals():
    pos = {0: (0, 0), 1: (1, 0), 2: (1, 1), 3: (0, 1)}
    edges = [(0, 1), (1, 2), (2, 3), (3, 0), (0, 2), (1, 3)]
    return pos, edges


class TestNormalization:
    def test_axes_are_scaled_independently(self):
        out = lq.normalize_like_renderer({"a": (0, 0), "b": (10, 1)})
        assert out["a"] == (-1000.0, -1000.0)
        assert out["b"] == (1000.0, 1000.0)

    def test_degenerate_axis_lands_on_the_lower_bound(self):
        out = lq.normalize_like_renderer({"a": (0, 5), "b": (2, 5)})
        assert out["a"][1] == out["b"][1] == -1000.0

    def test_renderer_uses_the_same_transform(self):
        """visualization_builder must not keep a second copy of the transform."""
        import inspect

        from app.logic import visualization_builder

        source = inspect.getsource(visualization_builder)
        assert "normalize_like_renderer" in source
        assert "TARGET_EXTENT" not in source


class TestCrossings:
    def test_square_with_both_diagonals_has_one_crossing(self):
        pos, edges = _square_with_diagonals()
        report = lq.evaluate(pos, edges, sizes=1)
        assert report.crossings == 1
        assert report.crossings_sampled is False

    def test_edges_sharing_an_endpoint_never_cross(self):
        pos = {0: (0, 0), 1: (1, 0), 2: (0, 1), 3: (1, 1)}
        report = lq.evaluate(pos, [(0, 1), (0, 2), (0, 3)], sizes=1)
        assert report.crossings == 0

    def test_sampled_estimate_is_close_to_the_exact_count(self, monkeypatch):
        G = nx.gnm_random_graph(300, 900, seed=1)
        pos = nx.random_layout(G, seed=1)
        exact = lq.evaluate(pos, G.edges, sizes=1)
        monkeypatch.setattr(lq, "EXACT_CROSSING_EDGE_LIMIT", 10)
        sampled = lq.evaluate(pos, G.edges, sizes=1)
        assert sampled.crossings_sampled is True
        assert sampled.crossings == pytest.approx(exact.crossings, rel=0.1)


class TestOverlap:
    def test_detects_touching_nodes(self):
        pos = {"a": (0, 0), "b": (1, 0), "c": (1000, 1000)}
        # Normalized, a and b are 2 units apart; size 100 gives radius ~17.8.
        report = lq.evaluate(pos, [], sizes=100)
        assert report.node_overlap == pytest.approx(2 / 3)
        assert "node_overlap" in report.issues

    def test_separated_nodes_do_not_overlap(self):
        pos = {i: (i % 10, i // 10) for i in range(100)}
        report = lq.evaluate(pos, [], sizes=10)
        assert report.node_overlap == 0.0

    def test_per_node_sizes_are_used(self):
        pos = {"a": (0, 0), "b": (0.2, 0), "c": (1, 1)}
        small = lq.evaluate(pos, [], sizes={"a": 1, "b": 1, "c": 1})
        big = lq.evaluate(pos, [], sizes={"a": 50000, "b": 50000, "c": 1})
        assert small.node_overlap == 0.0
        assert big.node_overlap > 0


class TestSpread:
    def test_outliers_compress_the_core(self):
        rng = np.random.default_rng(0)
        pos = {i: tuple(rng.normal(0, 1, 2)) for i in range(200)}
        pos["far1"] = (500.0, 500.0)
        pos["far2"] = (-500.0, -500.0)
        report = lq.evaluate(pos, [], sizes=1)
        assert report.core_extent < lq.THRESHOLDS["outliers_compress_core"]
        assert "outliers_compress_core" in report.issues

    def test_even_grid_is_not_compressed(self):
        pos = {i: (i % 20, i // 20) for i in range(400)}
        report = lq.evaluate(pos, [], sizes=1)
        assert report.core_extent > 0.7
        assert report.occupancy > 0.5

    def test_aspect_reports_stretch(self):
        pos = {i: (i, (i % 2) * 0.1) for i in range(30)}
        report = lq.evaluate(pos, [], sizes=1)
        assert report.aspect > lq.THRESHOLDS["distorted_aspect"]

    def test_small_graphs_skip_spread_metrics(self):
        pos, edges = _square_with_diagonals()
        report = lq.evaluate(pos, edges, sizes=1)
        assert report.core_extent is None and report.occupancy is None


class TestScore:
    def test_better_layout_scores_lower(self):
        G = nx.les_miserables_graph()
        good = nx.spring_layout(G, seed=1, iterations=200)
        bad = {node: (0.001 * i, 0.001 * i) for i, node in enumerate(G)}
        bad["Valjean"] = (100, 100)
        assert lq.evaluate(good, G.edges, 50).score < lq.evaluate(bad, G.edges, 50).score

    def test_compact_dict_shape(self):
        pos, edges = _square_with_diagonals()
        out = lq.evaluate(pos, edges, sizes=1).as_dict()
        assert set(out) == {
            "node_overlap", "crossings", "crossings_per_edge", "crossings_sampled",
            "edge_length_cv", "core_extent", "aspect", "occupancy", "score", "issues",
        }


def test_runs_under_a_second_on_a_few_thousand_nodes():
    G = nx.barabasi_albert_graph(3000, 2, seed=0)
    pos = nx.random_layout(G, seed=0)
    start = time.perf_counter()
    lq.evaluate(pos, G.edges, sizes=20)
    assert time.perf_counter() - start < 1.0


class TestRenderedQuality:
    """`visualization_generate` carries the metrics; plain renders do not."""

    def test_generate_reports_quality_after_a_layout(self, db):
        from app.logic.layout import calculate_layout
        from app.logic.visualization_builder import build_visualization
        from tests.test_layout_parameters import setup_graph

        setup_graph(db, n=8)
        calculate_layout(1, "spring", db)
        vis = build_visualization(db, 1, with_quality=True)
        assert vis["layout_quality"]["layout"] == "spring"
        assert "issues" in vis["layout_quality"]
        assert "layout_quality" not in build_visualization(db, 1)
