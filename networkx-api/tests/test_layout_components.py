"""Packing a graph in several parts, part by part (ADR 0041)."""

import math

import networkx as nx
import numpy as np
import pytest
from tests.test_layout_parameters import setup_graph

from app.logic.layout import calculate_layout
from app.logic.layouts import components, force_directed, get_spec
from app.logic.layouts.components import (
    PART_GAP,
    connected_parts,
    layout_by_part,
)


def _split_graph():
    G = nx.disjoint_union_all(
        [nx.barabasi_albert_graph(80, 2, seed=1)]
        + [nx.cycle_graph(6) for _ in range(5)]
        + [nx.path_graph(3) for _ in range(8)]
    )
    G.add_nodes_from(f"iso{i}" for i in range(6))
    return G


def _spring(H):
    return nx.spring_layout(H, seed=42)


def _parts_of(G, pos):
    for nodes in connected_parts(G):
        yield nodes, np.array([pos[n] for n in nodes])


class TestPacking:
    def test_parts_keep_their_clearance(self):
        G = _split_graph()
        pos = layout_by_part(G, _spring)
        parts = list(_parts_of(G, pos))
        # Rounding to the grid can cost up to one cell of the clearance.
        tolerance = 2 * components._CELL
        for i, (_a, xy_a) in enumerate(parts):
            for _b, xy_b in parts[i + 1 :]:
                gaps = np.linalg.norm(xy_a[:, None] - xy_b[None], axis=2)
                assert gaps.min() >= PART_GAP - tolerance

    def test_largest_part_is_in_the_middle(self):
        G = _split_graph()
        pos = layout_by_part(G, _spring)
        centres = [np.linalg.norm(xy.mean(axis=0)) for _n, xy in _parts_of(G, pos)]
        assert centres[0] == pytest.approx(0.0, abs=1e-9)
        assert centres[0] == min(centres)

    def test_parts_are_drawn_at_one_edge_length(self):
        """A part's own layout scale must not decide how large it is drawn."""
        G = nx.disjoint_union(nx.cycle_graph(10), nx.cycle_graph(10))
        scales = iter([1.0, 50.0])

        def lay_out(H):
            factor = next(scales)
            return {n: factor * p for n, p in nx.circular_layout(H).items()}

        pos = layout_by_part(G, lay_out)
        lengths = (
            [math.dist(pos[u], pos[v]) for u, v in G.edges() if u < 10],
            [math.dist(pos[u], pos[v]) for u, v in G.edges() if u >= 10],
        )
        assert np.median(lengths[0]) == pytest.approx(1.0)
        assert np.median(lengths[1]) == pytest.approx(1.0)

    def test_isolates_alone_are_spread_out(self):
        G = nx.empty_graph(30)
        pos = layout_by_part(G, _spring)
        xy = np.array(list(pos.values()))
        gaps = np.linalg.norm(xy[:, None] - xy[None], axis=2)
        np.fill_diagonal(gaps, np.inf)
        assert gaps.min() >= PART_GAP - 2 * components._CELL

    def test_result_does_not_depend_on_set_order(self):
        """Parts are built in the graph's node order, not a set's."""
        G = _split_graph()
        first = layout_by_part(G, _spring)
        again = layout_by_part(nx.relabel_nodes(G, str), _spring)
        for node, point in first.items():
            assert np.allclose(again[str(node)], point)

    def test_directed_graph_is_split_by_weak_connectivity(self):
        D = nx.DiGraph([(0, 1), (2, 1), (3, 4)])
        assert [sorted(p) for p in connected_parts(D)] == [[0, 1, 2], [3, 4]]
        assert set(layout_by_part(D, _spring)) == set(D)


class TestSpring:
    def test_packed_spring_lays_out_every_node(self):
        G = _split_graph()
        params, _notes = get_spec("spring").tuned(G, _profile(G))
        pos = get_spec("spring").compute(G, params)
        assert set(pos) == set(G)
        assert all(np.isfinite(p).all() for p in pos.values())

    def test_starting_positions_turn_packing_off(self):
        G = _split_graph()
        start = nx.circular_layout(G)
        params = {"pack_components": True, "pos": start, "iterations": 5, "seed": 1}
        pos = get_spec("spring").compute(G, dict(params))
        plain = nx.spring_layout(G, pos=start, iterations=5, seed=1)
        assert all(np.allclose(pos[n], plain[n]) for n in G)

    def test_k_is_scaled_to_each_part(self, monkeypatch):
        seen = []
        real = nx.spring_layout

        def spy(H, **kw):
            seen.append((len(H), kw.get("k")))
            return real(H, **kw)

        monkeypatch.setattr(force_directed.nx, "spring_layout", spy)
        G = nx.disjoint_union(nx.cycle_graph(40), nx.cycle_graph(10))
        force_directed.spring(G, {"pack_components": True, "k": 0.1, "seed": 1})
        assert dict(seen) == pytest.approx(
            {40: 0.1 * math.sqrt(50 / 40), 10: 0.1 * math.sqrt(50 / 10)}
        )

    @pytest.mark.parametrize("prefer", ["short", "full"])
    def test_large_part_keeps_the_better_scored_run(self, monkeypatch, prefer):
        """Long strands want a short run, dense parts the full one (ADR 0041)."""
        from app.logic import layout_quality

        runs = []
        real = nx.spring_layout

        def spy(H, **kw):
            pos = real(H, **kw)
            runs.append(pos)
            return pos

        class Report:
            def __init__(self, score):
                self.score = score

        def fake_evaluate(pos, edges, sizes):
            is_short = pos is runs[0]
            return Report(0.0 if is_short == (prefer == "short") else 1.0)

        monkeypatch.setattr(force_directed.nx, "spring_layout", spy)
        monkeypatch.setattr(layout_quality, "evaluate", fake_evaluate)
        H = nx.cycle_graph(force_directed._SPRING_ENERGY_FROM)
        got = force_directed._spring_part(
            H, {"iterations": 60, "seed": 1}, H.number_of_nodes()
        )
        assert len(runs) == 2
        assert got is runs[0 if prefer == "short" else 1]

    def test_small_part_runs_once(self, monkeypatch):
        calls = []
        real = nx.spring_layout
        monkeypatch.setattr(
            force_directed.nx,
            "spring_layout",
            lambda H, **kw: calls.append(kw) or real(H, **kw),
        )
        force_directed._spring_part(nx.cycle_graph(30), {"iterations": 500}, 30)
        assert len(calls) == 1 and calls[0]["iterations"] == 500


class TestThroughCalculateLayout:
    def _split_network(self, db):
        setup_graph(db, n=6)
        from common import models

        db.add(models.Node(network_id=1, node_id="lonely"))
        db.commit()

    def test_packing_is_part_of_the_effective_parameters(self, db):
        self._split_network(db)
        info = calculate_layout(1, "spring", db)
        assert info["parameters"]["pack_components"] is True

    def test_packing_can_be_turned_off(self, db):
        self._split_network(db)
        info = calculate_layout(1, "spring", db, overrides={"pack_components": False})
        assert info["parameters"]["pack_components"] is False
        assert not any("`pack_components`" in n for n in info["tuning_notes"])

    def test_other_layouts_reject_it(self, db):
        self._split_network(db)
        with pytest.raises(ValueError, match="Unsupported parameters"):
            calculate_layout(1, "circular", db, overrides={"pack_components": True})


def _profile(G):
    from app.logic.layouts.profile import profile_graph

    return profile_graph(G)
