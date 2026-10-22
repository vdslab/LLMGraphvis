"""Graph profiles, profile-driven tuning and knob declarations (ADR 0017)."""

import networkx as nx
import pytest

from app.logic.layout import calculate_layout, format_layout_result
from app.logic.layouts import SPECS, get_spec
from app.logic.layouts.base import Knob
from app.logic.layouts.profile import (
    profile_graph,
    recommend_layouts,
    unsuitable_layouts,
)
from tests.test_layout_parameters import setup_graph


def _fragmented():
    G = nx.disjoint_union_all([nx.path_graph(5) for _ in range(8)])
    G.add_nodes_from(["iso1", "iso2"])
    return G


class TestProfile:
    def test_counts_components_and_isolates(self):
        p = profile_graph(_fragmented())
        assert p.components == 10
        assert p.isolates == 2
        assert p.fragmented
        assert p.is_forest

    def test_weighted_strength(self):
        G = nx.path_graph(3)
        nx.set_edge_attributes(G, {(0, 1): 1.0, (1, 2): 3.0}, "w")
        p = profile_graph(G, "w")
        assert p.weighted and p.weight_ratio == 3.0
        assert p.avg_strength == pytest.approx(8 / 3)
        assert profile_graph(G).weighted is False

    def test_structure_flags(self):
        p = profile_graph(nx.complete_graph(5))
        assert p.is_planar is False and p.is_bipartite is False
        assert profile_graph(nx.cycle_graph(6)).is_bipartite is True


class TestRecommendations:
    def test_tree_suggests_bfs_first(self):
        recs = recommend_layouts(profile_graph(nx.balanced_tree(2, 4)))
        assert recs[0]["layout"] == "bfs"

    def test_planar_graph_offers_planar(self):
        names = [r["layout"] for r in recommend_layouts(profile_graph(nx.grid_2d_graph(4, 4)))]
        assert "planar" in names

    def test_large_or_split_graph_rules_out_kamada_kawai(self):
        big = profile_graph(nx.barabasi_albert_graph(400, 2, seed=0))
        assert "kamada_kawai" not in [r["layout"] for r in recommend_layouts(big)]
        assert "kamada_kawai" in [r["layout"] for r in unsuitable_layouts(big)]
        split = profile_graph(_fragmented())
        assert "kamada_kawai" in [r["layout"] for r in unsuitable_layouts(split)]


class TestTuning:
    def test_fragmented_graph_raises_forceatlas2_gravity(self):
        params, notes = get_spec("forceatlas2").tuned(_fragmented(), profile_graph(_fragmented()))
        assert params["gravity"] > 1.0
        assert any("`gravity`" in n for n in notes)

    def test_connected_graph_keeps_plain_defaults(self):
        G = nx.karate_club_graph()
        params, notes = get_spec("forceatlas2").tuned(G, profile_graph(G))
        assert params["gravity"] == 1.0 and notes == []

    def test_fragmented_graph_switches_spring_to_energy(self):
        params, notes = get_spec("spring").tuned(_fragmented(), profile_graph(_fragmented()))
        assert params["method"] == "energy" and params["gravity"] > 1
        assert notes

    def test_notes_reach_the_tool_message(self, db):
        setup_graph(db, n=6)
        from common import models

        db.add(models.Node(network_id=1, node_id="lonely"))
        db.commit()
        info = calculate_layout(1, "forceatlas2", db)
        assert "Auto-tuned:" in format_layout_result(info, "done.")

    def test_notes_are_dropped_for_overridden_parameters(self, db):
        setup_graph(db, n=6)
        from common import models

        db.add(models.Node(network_id=1, node_id="lonely"))
        db.commit()
        info = calculate_layout(1, "forceatlas2", db, overrides={"gravity": 2.0})
        assert info["tuning_notes"] == []

    def test_tree_gets_few_spring_iterations(self):
        G = nx.random_labeled_tree(100, seed=1)
        params, notes = get_spec("spring").tuned(G, profile_graph(G))
        assert params["iterations"] < get_spec("spring").tuned(
            nx.karate_club_graph(), profile_graph(nx.karate_club_graph())
        )[0]["iterations"]
        assert any("`iterations`" in n for n in notes)


class TestKnobs:
    @pytest.mark.parametrize("name", ["forceatlas2", "spring", "arf"])
    def test_force_layouts_are_tunable(self, name):
        assert SPECS[name].knobs

    def test_every_knob_is_an_accepted_parameter(self):
        for spec in SPECS.values():
            for knob in spec.knobs:
                assert knob.param in spec.params
                for required in knob.requires:
                    assert required in spec.params

    def test_knobs_name_real_issue_labels(self):
        from app.logic.layout_quality import THRESHOLDS

        for spec in SPECS.values():
            for knob in spec.knobs:
                assert set(knob.fixes) <= set(THRESHOLDS), (spec.name, knob.param)

    def test_register_rejects_a_knob_it_does_not_accept(self):
        from app.logic.layouts.base import register

        with pytest.raises(ValueError, match="does not accept"):
            register("bogus", params={"a"}, knobs=(Knob("b"),))(lambda G, p: {})

    def test_relative_range_scales_with_the_tuned_value(self):
        knob = Knob("k", 0.25, 4.0, relative=True)
        assert knob.bounds(0.2) == pytest.approx((0.05, 0.8))
        assert knob.describe(0.2)["range"] == [0.05, 0.8]
