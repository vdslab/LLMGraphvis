"""Highlight, label visibility and viewport channels (ADR 0023)."""

import pytest
from app.core import database
from app.logic import visualization_builder
from app.mcp import tools
from test_layout_parameters import setup_graph

from common import models


@pytest.fixture
def bound(db, monkeypatch):
    """Route the tools' own sessions to the test session."""
    monkeypatch.setattr(db, "close", lambda: None)
    monkeypatch.setattr(database, "SessionLocal", lambda: db)
    setup_graph(db, attrs={"score": {f"n{i}": float(i) for i in range(6)}})
    tools.layout_circular(1)
    return db


def by_id(vis):
    return {n["id"]: n for n in vis["nodes"]}


def edge_map(vis):
    return {(e["source"], e["target"]): e for e in vis["links"]}


def test_path_highlight_marks_route_edges_and_dims_the_rest(bound):
    vis = tools.visualization_highlight(1, ["n1", "n2", "n3"], edges="path")

    nodes, edges = by_id(vis), edge_map(vis)
    assert nodes["n2"]["highlighted"] and nodes["n2"]["opacity"] == 1.0
    assert "highlighted" not in nodes["n0"] and nodes["n0"]["opacity"] < 0.5
    assert edges[("n1", "n2")]["highlighted"] and edges[("n2", "n3")]["highlighted"]
    assert "highlighted" not in edges[("n0", "n1")]
    assert vis["legend"]["highlight"] == {"node_count": 3, "edge_count": 2, "edges": "path"}


def test_highlight_persists_through_other_channels_until_reset(bound):
    tools.visualization_highlight(1, ["n0"], neighbor_hops=1, edges="incident")

    vis = tools.visualization_set_node_size(1, attribute="score")
    assert {n["id"] for n in vis["nodes"] if n.get("highlighted")} == {"n0", "n1"}

    reset = tools.visualization_reset_style(1, ["highlight"])
    assert reset["reset"] == ["highlight"]
    assert not any(n.get("highlighted") for n in reset["nodes"])
    assert all(n["opacity"] == 1.0 for n in reset["nodes"])


def test_resetting_the_zoom_as_a_style_points_to_set_viewport(bound):
    """The zoom is not a channel; a guessed 'viewport' target must say what is."""
    hint = r"visualization_set_viewport\(target='all'\)"
    with pytest.raises(RuntimeError, match=hint):
        tools.visualization_reset_style(1, ["viewport"])


def test_zoom_to_highlight_says_how_to_zoom_back_out(bound):
    vis = tools.visualization_highlight(1, ["n1", "n2"], zoom_to=True)
    assert "visualization_set_viewport(target='all')" in vis["view"]


def test_path_highlight_rejects_non_adjacent_nodes_and_unknown_ids(bound):
    with pytest.raises(RuntimeError, match="No edge n0 -> n3"):
        tools.visualization_highlight(1, ["n0", "n3"], edges="path")
    with pytest.raises(RuntimeError, match="Unknown node ID"):
        tools.visualization_highlight(1, ["nope"])


def test_top_n_labels_follow_rank_attribute_and_style_is_reported(bound):
    vis = tools.visualization_set_node_labels(
        1, visibility="top_n", top_n=2, rank_by="score", font_size=14, max_length=8
    )

    labelled = {n["id"] for n in vis["nodes"] if n["show_label"]}
    assert labelled == {"n5", "n4"}
    assert vis["label_style"] == {
        "font_size": 14,
        "max_length": 8,
        "visibility": "top_n",
        "labeled_count": 2,
    }


def test_labels_without_visibility_leave_the_canvas_toggle_in_charge(bound):
    vis = tools.visualization_set_node_labels(1, attribute="score")

    assert "show_label" not in vis["nodes"][0]
    assert by_id(vis)["n3"]["label"] == "3.0"


def test_highlighted_label_visibility_uses_the_highlight(bound):
    tools.visualization_highlight(1, ["n2"])
    vis = tools.visualization_set_node_labels(1, visibility="highlighted")

    assert {n["id"] for n in vis["nodes"] if n["show_label"]} == {"n2"}


def test_viewport_is_a_one_shot_instruction_not_saved_state(bound):
    vis = tools.visualization_set_viewport(1, target="nodes", node_ids=["n4"])
    assert vis["viewport"]["mode"] == "nodes"
    assert vis["viewport"]["node_ids"] == ["n4"]

    again = tools.visualization_generate(1)
    assert "viewport" not in again

    with pytest.raises(RuntimeError, match="Nothing is highlighted"):
        tools.visualization_set_viewport(1, target="highlighted")


def test_current_state_reports_highlight(bound):
    tools.visualization_highlight(1, ["n1"])
    state = visualization_builder.get_current_visualization(bound, 1)
    assert state["highlight"]["node_ids"] == ["n1"]
    assert bound.query(models.Network).get(1).last_highlight_config["edges"] == "induced"
