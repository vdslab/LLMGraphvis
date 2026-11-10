"""Drawing tools answer with a receipt; the rows travel over REST (ADR 0045)."""

import json

import pytest
from test_layout_parameters import setup_graph

from app.core import database
from app.mcp import tools

# One MCP message may carry this much; a result above it never arrives.
MCP_EVENT_LIMIT = 1024 * 1024


@pytest.fixture
def bound(db, monkeypatch):
    """Route the tools' own sessions to the test session."""
    monkeypatch.setattr(db, "close", lambda: None)
    monkeypatch.setattr(database, "SessionLocal", lambda: db)
    return db


def _graph(db, n=6):
    setup_graph(db, n=n, attrs={"score": {f"n{i}": float(i) for i in range(n)}})
    tools.layout_circular(1)


DRAWING_CALLS = {
    "visualization_generate": lambda: tools.visualization_generate(1),
    "visualization_set_node_color": lambda: tools.visualization_set_node_color(
        1, attribute="score", scale_type="LINEAR"
    ),
    "visualization_set_node_size": lambda: tools.visualization_set_node_size(
        1, attribute="score"
    ),
    "visualization_set_node_labels": lambda: tools.visualization_set_node_labels(
        1, attribute="score"
    ),
    "visualization_set_edge_color": lambda: tools.visualization_set_edge_color(
        1, default_color="#333333"
    ),
    "visualization_set_edge_width": lambda: tools.visualization_set_edge_width(
        1, default_width=2.0
    ),
    "visualization_highlight": lambda: tools.visualization_highlight(
        1, ["n1", "n2"], zoom_to=True
    ),
    "visualization_set_viewport": lambda: tools.visualization_set_viewport(
        1, target="all"
    ),
    "visualization_reset_style": lambda: tools.visualization_reset_style(
        1, ["node_color"]
    ),
    "visualization_switch_network": lambda: tools.visualization_switch_network(1),
}


def test_every_drawing_tool_is_covered():
    """A new drawing tool must be added above, so its result is checked too."""
    drawing_tools = {
        name
        for name in dir(tools)
        if name.startswith("visualization_")
        and name
        not in {
            "visualization_get_state",
            "visualization_describe",
            "visualization_apply_layout",  # deprecated alias of generate
        }
    }
    assert drawing_tools == set(DRAWING_CALLS)


@pytest.mark.parametrize("name", sorted(DRAWING_CALLS))
def test_drawing_tool_returns_a_receipt_matching_the_rest_drawing(name, bound, client):
    _graph(bound)

    receipt = DRAWING_CALLS[name]()

    assert receipt["rendered"] is True and receipt["network_id"] == 1
    assert "nodes" not in receipt and "links" not in receipt

    drawing = client.get("/api/v1/networks/1/visualization?quality=false").json()
    assert "layout_quality" not in drawing
    assert receipt["node_count"] == len(drawing["nodes"]) == 6
    assert receipt["link_count"] == len(drawing["links"])
    # What the tool drew is what the saved style redraws.
    assert receipt["legend"] == drawing["legend"]
    assert "layout_quality" in receipt


def test_rest_drawing_carries_quality_by_default(bound, client):
    _graph(bound)

    drawing = client.get("/api/v1/networks/1/visualization").json()

    assert "layout_quality" in drawing and len(drawing["nodes"]) == 6


def test_receipt_does_not_grow_with_the_network(bound, client):
    """The failure this replaces: 3,393 nodes made a result of over 1 MiB."""
    _graph(bound, n=4000)

    receipt = tools.visualization_set_node_size(1, attribute="score")
    drawing = client.get("/api/v1/networks/1/visualization?quality=false")

    assert len(json.dumps(receipt)) < 16 * 1024
    assert len(drawing.content) > MCP_EVENT_LIMIT / 2
