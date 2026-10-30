"""Automatic iteration budgets follow graph structure as well as size."""

import networkx as nx
import pytest

from app.logic.layouts.force_directed import fa2_iterations, tune_spring
from app.logic.layouts.profile import profile_graph


@pytest.mark.parametrize("n", [50, 1000, 2500])
def test_spring_does_not_fold_trees_with_long_runs(n):
    graph = nx.path_graph(n)
    parameters, notes = tune_spring(graph, profile_graph(graph))
    assert parameters["iterations"] == 50
    assert any("tree" in note for note in notes)


def test_forceatlas2_caps_quadratic_work_on_large_graphs():
    small_iterations, small_limited = fa2_iterations(50)
    large_iterations, large_limited = fa2_iterations(2500)
    assert small_iterations == 200
    assert not small_limited
    assert large_limited
    assert 2500**2 * large_iterations <= 500_000_000
