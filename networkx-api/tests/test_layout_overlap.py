"""Overlap removal after force layouts (logic/layouts/overlap.py, ADR 0048)."""

import networkx as nx
import numpy as np
import pytest

from app.logic import layout_quality as lq
from app.logic.layouts import REMOVE_OVERLAP, get_spec
from app.logic.layouts.overlap import separate_overlaps

SIZE = 20.0  # an area; radius about 8 drawn units


def _overlap(pos, size=SIZE):
    return lq.evaluate(pos, [], size).node_overlap


def _crowded(n=400, seed=0):
    """Random points packed into a small disc inside a wider frame.

    Two far corner nodes keep the frame wide, so the crowd is drawn small and
    almost every node touches another, as in a large spring layout.
    """
    rng = np.random.default_rng(seed)
    pos = {i: tuple(rng.normal(0, 0.05, 2)) for i in range(n)}
    pos["corner_a"], pos["corner_b"] = (-1.0, -1.0), (1.0, 1.0)
    return pos


class TestSeparateOverlaps:
    def test_removes_most_overlap(self):
        pos = _crowded()
        before = _overlap(pos)
        assert before > 0.5
        assert _overlap(separate_overlaps(pos, SIZE)) < before / 4

    def test_keeps_the_coordinate_frame(self):
        pos = _crowded()
        out = separate_overlaps(pos, SIZE)
        before = np.array(list(pos.values()))
        after = np.array(list(out.values()))
        np.testing.assert_allclose(after.min(axis=0), before.min(axis=0), atol=1e-9)
        np.testing.assert_allclose(after.max(axis=0), before.max(axis=0), atol=1e-9)

    def test_keeps_neighbourhoods(self):
        """Nodes move locally: who is near whom stays mostly the same."""
        rng = np.random.default_rng(1)
        centres = [(-0.5, 0.0), (0.5, 0.0)]
        pos = {
            (g, i): tuple(np.add(centres[g], rng.normal(0, 0.05, 2)))
            for g in range(2)
            for i in range(150)
        }
        out = separate_overlaps(pos, SIZE)
        for (g, _i), (x, _y) in out.items():
            assert (x < 0) == (g == 0)

    def test_leaves_a_clean_layout_alone(self):
        pos = {i: (float(i % 10), float(i // 10)) for i in range(100)}
        out = separate_overlaps(pos, SIZE)
        np.testing.assert_allclose([out[i] for i in pos], [pos[i] for i in pos])

    def test_separates_coincident_nodes_deterministically(self):
        pos = {i: (0.0, 0.0) for i in range(5)}
        pos.update({"a": (-1.0, -1.0), "b": (1.0, 1.0)})
        first = separate_overlaps(pos, SIZE)
        assert first == separate_overlaps(pos, SIZE)
        assert len({first[i] for i in range(5)}) == 5

    def test_size_per_node(self):
        pos = _crowded(n=100)
        sizes = {node: (200.0 if node == 0 else 5.0) for node in pos}
        before = lq.evaluate(pos, [], sizes).node_overlap
        after = lq.evaluate(separate_overlaps(pos, sizes), [], sizes).node_overlap
        assert after < before / 4

    def test_tiny_inputs(self):
        assert separate_overlaps({}, SIZE) == {}
        assert separate_overlaps({"a": (1.0, 2.0)}, SIZE) == {"a": (1.0, 2.0)}
        assert separate_overlaps({"a": (0, 0), "b": (0, 0)}, 0.0) == {
            "a": (0, 0),
            "b": (0, 0),
        }


class TestLayoutDeclaration:
    @pytest.mark.parametrize("name", ["spring", "forceatlas2", "arf", "kamada_kawai"])
    def test_force_layouts_remove_overlap_by_default(self, name):
        spec = get_spec(name)
        assert spec.removes_overlap
        assert REMOVE_OVERLAP in spec.accepted
        G = nx.path_graph(5)
        params, _ = spec.tuned(G, _profile(G))
        assert params[REMOVE_OVERLAP] is True

    @pytest.mark.parametrize("name", ["circular", "shell", "bipartite", "spectral"])
    def test_meaningful_positions_are_left_alone(self, name):
        spec = get_spec(name)
        assert not spec.removes_overlap
        assert REMOVE_OVERLAP not in spec.accepted

    def test_run_separates_and_compute_does_not(self):
        spec = get_spec("spring")
        G = nx.barabasi_albert_graph(400, 1, seed=0)
        params, _ = spec.tuned(G, _profile(G))
        bare = spec.compute(G, params)
        assert _overlap(bare, 200.0) > 0.1
        drawn = spec.run(G, params, 200.0)
        assert _overlap(drawn, 200.0) < _overlap(bare, 200.0)

    def test_opting_out_keeps_the_bare_layout(self):
        spec = get_spec("spring")
        G = nx.barabasi_albert_graph(400, 1, seed=0)
        params, _ = spec.tuned(G, _profile(G))
        params[REMOVE_OVERLAP] = False
        drawn, bare = spec.run(G, params, 200.0), spec.compute(G, params)
        np.testing.assert_allclose([drawn[v] for v in G], [bare[v] for v in G])


def _profile(G):
    from app.logic.layouts.profile import profile_graph

    return profile_graph(G, None)


class TestCalculateLayout:
    def test_reports_removal_and_caches_by_drawn_size(self, db):
        from test_layout_parameters import setup_graph

        from app.logic.layout import calculate_layout
        from common import models

        setup_graph(db)
        first = calculate_layout(1, "spring", db)
        assert first["parameters"][REMOVE_OVERLAP] is True
        assert calculate_layout(1, "spring", db)["cached"] is True

        network = db.query(models.Network).filter(models.Network.id == 1).one()
        network.last_node_size_config = {"default": 50.0}
        db.commit()
        assert calculate_layout(1, "spring", db)["cached"] is False

    def test_opt_out_is_accepted_where_it_applies(self, db):
        from test_layout_parameters import setup_graph

        from app.logic.layout import calculate_layout

        setup_graph(db)
        result = calculate_layout(1, "spring", db, overrides={REMOVE_OVERLAP: False})
        assert result["parameters"][REMOVE_OVERLAP] is False
        with pytest.raises(ValueError, match="Unsupported parameters"):
            calculate_layout(1, "circular", db, overrides={REMOVE_OVERLAP: False})
