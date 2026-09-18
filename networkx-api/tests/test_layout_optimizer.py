"""Parameter search over layout knobs (logic/layout_optimizer.py, ADR 0017)."""

import itertools

import networkx as nx
import pytest

from app.logic import layout_optimizer as opt
from app.logic.layout import calculate_layout
from app.logic.layouts import get_spec
from app.logic.layouts.base import Knob
from app.logic.layouts.profile import profile_graph
from tests.test_layout_parameters import setup_graph


def _fragmented():
    parts = [nx.barabasi_albert_graph(k, 2, seed=k) for k in (40, 20, 10, 6)]
    G = nx.disjoint_union_all(parts)
    G.add_nodes_from(f"iso{i}" for i in range(6))
    return G


def _search(G, name, base=None, **kwargs):
    spec = get_spec(name)
    tuned, _ = spec.tuned(G, profile_graph(G))
    return opt.search(G, spec, base or tuned, 60, tuned_params=tuned, **kwargs)


class TestSearch:
    def test_finds_a_better_forceatlas2_for_a_fragmented_graph(self):
        G = _fragmented()
        # Start from plain gravity, as before profile tuning.
        spec = get_spec("forceatlas2")
        tuned, _ = spec.tuned(G, profile_graph(G))
        result = _search(G, "forceatlas2", base={**tuned, "gravity": 1.0})
        assert result.candidates
        assert result.candidates[0].report.score <= result.baseline.report.score

    def test_candidates_are_ranked_by_score(self):
        result = _search(_fragmented(), "spring")
        scores = [c.report.score for c in result.candidates]
        assert scores == sorted(scores)

    def test_budget_counts_the_baseline(self):
        result = _search(_fragmented(), "forceatlas2", budget=3)
        assert result.evaluations <= 3
        assert len(result.candidates) <= 2

    def test_time_cap_stops_new_runs(self):
        ticks = itertools.count(0, 100)  # every clock read is 100 s later
        result = _search(_fragmented(), "forceatlas2", clock=lambda: next(ticks))
        assert result.evaluations == 1
        assert result.stopped_early

    def test_changes_record_before_and_after(self):
        result = _search(_fragmented(), "forceatlas2")
        for candidate in result.candidates:
            for param, (before, after) in candidate.changes.items():
                assert candidate.params[param] == after
                assert before != after


class TestStep:
    def test_log_knob_doubles_and_clamps(self):
        knob = Knob("x", 1.0, 3.0)
        params, changes = opt._step(knob, +1, {"x": 2.0}, {"x": 2.0})
        assert params["x"] == 3.0 and changes == {"x": (2.0, 3.0)}
        _, no_change = opt._step(knob, +1, {"x": 3.0}, {"x": 2.0})
        assert no_change == {}

    def test_requires_is_applied_with_the_knob(self):
        knob = Knob("gravity", 0.5, 20.0, requires={"method": "energy"})
        params, changes = opt._step(knob, +1, {"gravity": 1.0}, {})
        assert params["method"] == "energy"
        assert changes["method"] == (None, "energy")

    def test_toggle(self):
        knob = Knob("flag", toggle=True)
        params, changes = opt._step(knob, +1, {}, {})
        assert params["flag"] is True
        assert opt._step(knob, +1, {"flag": True}, {})[1] == {}

    def test_direction_zero_tries_both_ways(self):
        knob = Knob("k", fixes={"node_overlap": 0})
        moves = opt._moves([knob], ["node_overlap"], {}, {})
        assert {d for _k, d in moves} == {+1, -1}


class TestSuggestParameters:
    def test_returns_arguments_that_reproduce_a_candidate(self, db):
        setup_graph(db, n=12)
        calculate_layout(1, "forceatlas2", db)
        out = opt.suggest_parameters(1, db)
        assert out["applicable"] and out["layout"] == "forceatlas2"
        for candidate in out["candidates"]:
            assert "weight" not in candidate["arguments"]
            for param, (_before, after) in candidate["changes"].items():
                assert candidate["arguments"][param] == pytest.approx(after)
        assert {k["param"] for k in out["knobs"]} >= {"gravity", "scaling_ratio"}

    def test_saves_nothing(self, db):
        from app.logic.layout import load_layout_positions

        setup_graph(db, n=12)
        calculate_layout(1, "spring", db)
        before = load_layout_positions(1, "spring", db)
        opt.suggest_parameters(1, db)
        assert load_layout_positions(1, "spring", db) == before

    def test_layout_without_knobs_reports_metrics_only(self, db):
        setup_graph(db, n=8)
        calculate_layout(1, "circular", db)
        out = opt.suggest_parameters(1, db)
        assert out["applicable"] is False
        assert "node_overlap" in out["current"]

    def test_requires_a_layout(self, db):
        setup_graph(db, n=8)
        with pytest.raises(ValueError, match="No layout"):
            opt.suggest_parameters(1, db)

    def test_opted_out_weights_stay_off(self, db):
        setup_graph(db, n=8, weighted=True)
        calculate_layout(1, "forceatlas2", db, overrides={"weight": "none"})
        out = opt.suggest_parameters(1, db)
        # The tool would weight automatically, so the opt-out must be passed back.
        assert out["current"]["arguments"]["weight"] == "none"
        assert all(c["arguments"]["weight"] == "none" for c in out["candidates"])

    def test_automatic_weight_is_not_repeated(self, db):
        setup_graph(db, n=8, weighted=True)
        calculate_layout(1, "forceatlas2", db)
        out = opt.suggest_parameters(1, db)
        assert all("weight" not in c["arguments"] for c in out["candidates"])


class TestTools:
    def test_layout_profile_tool(self, db, monkeypatch):
        from contextlib import contextmanager

        from app.mcp.tools.layout import evaluation

        @contextmanager
        def fake_db():
            yield db

        monkeypatch.setattr(evaluation, "get_db_context", fake_db)
        setup_graph(db, n=8)
        out = evaluation.layout_profile(1)
        assert out["profile"]["nodes"] == 8
        assert out["profile"]["is_forest"] is True
        assert out["recommended"][0]["layout"] == "bfs"
