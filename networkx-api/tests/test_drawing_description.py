"""visualization_describe: the drawing in numbers (ADR 0042)."""

import pytest
from test_layout_parameters import setup_graph

from app.core import database
from app.logic.drawing_description import (
    describe_drawing,
    placement_of,
    region_of,
)
from app.mcp import tools


def node(node_id, x, y, color="#000", size=10.0, **extra):
    return {
        "id": node_id,
        "label": node_id,
        "x": x,
        "y": y,
        "color": color,
        "size": size,
        "opacity": 1.0,
        **extra,
    }


def two_clusters(mixed=False):
    """Six nodes top-left and six bottom-right, colored by side unless mixed."""
    nodes = []
    for i in range(6):
        nodes.append(
            node(
                f"a{i}",
                -800 + i * 10,
                -800 + i * 10,
                color="#f00" if not mixed or i % 2 else "#00f",
            )
        )
        nodes.append(
            node(
                f"b{i}",
                800 - i * 10,
                800 - i * 10,
                color="#00f" if not mixed or i % 2 else "#f00",
            )
        )
    links = [{"source": f"a{i}", "target": f"a{i + 1}"} for i in range(5)]
    links += [{"source": f"b{i}", "target": f"b{i + 1}"} for i in range(5)]
    return {"nodes": nodes, "links": links, "legend": {"layout": "spring"}}


def test_regions_follow_the_svg_axes():
    assert region_of(-900, -900) == "top-left"
    assert region_of(0, 900) == "bottom"
    assert region_of(900, 0) == "right"
    assert region_of(100, -100) == "center"
    assert placement_of(0, 0) == "core"
    assert placement_of(1000, 1000) == "periphery"


def test_separated_groups_score_high_and_mixed_ones_low():
    apart = describe_drawing(two_clusters())["groups"]
    mixed = describe_drawing(two_clusters(mixed=True))["groups"]

    assert apart["by"] == "drawn color"
    assert apart["separation"] == pytest.approx(1.0)
    assert mixed["separation"] < 0.3
    regions = {item["color"]: item["region"] for item in apart["items"]}
    assert regions == {"#f00": "top-left", "#00f": "bottom-right"}


def test_split_group_lists_both_regions():
    """Half of group x on each side: one center would hide the split."""
    side = {f"{c}{i}": "x" if i < 3 else "y" for c in "ab" for i in range(6)}
    result = describe_drawing(two_clusters(), ("side", side))
    items = {item["value"]: item for item in result["groups"]["items"]}
    assert set(items["x"]["main_regions"]) == {"top-left", "bottom-right"}
    assert items["x"]["spread"] > 0.9


def test_a_single_group_is_not_described():
    side = {f"{c}{i}": "z" for c in "ab" for i in range(6)}
    assert describe_drawing(two_clusters(), ("side", side))["groups"] is None


def test_components_outliers_and_prominent_nodes():
    data = two_clusters()
    data["nodes"].append(node("far", 0, 0, size=50.0))
    result = describe_drawing(data, limit=1)

    comps = result["components"]
    assert comps["count"] == 3 and comps["isolated_nodes"] == 1
    assert comps["largest"][0]["node_count"] == 6 and comps["omitted"] == 1
    assert result["outliers"]["items"][0]["id"] == "far"
    top = result["prominent_nodes"]["items"][0]
    assert top["id"] == "far" and top["placement"] == "core"
    assert top["degree"] == 0


def test_numeric_placement_finds_high_values_at_the_center():
    nodes = [node(f"n{i}", (i % 5 - 2) * 400, (i // 5 - 2) * 400) for i in range(25)]
    values = {n["id"]: -abs(n["x"]) - abs(n["y"]) for n in nodes}
    result = describe_drawing(
        {"nodes": nodes, "links": [], "legend": {}},
        numeric=[("node_size", "score", values)],
    )
    entry = result["numeric_placement"][0]
    assert entry["center_correlation"] > 0.9
    assert entry["high_values"]["region"] == "center"


def test_lists_are_bounded_by_limit():
    nodes = [
        node(f"n{i}", i * 5 - 1000, 0, color=f"#{i:06x}", size=float(i))
        for i in range(12)
    ]
    result = describe_drawing({"nodes": nodes, "links": [], "legend": {}}, limit=3)
    assert len(result["groups"]["items"]) == 3
    assert result["groups"]["omitted"] == 9
    assert len(result["prominent_nodes"]["items"]) == 3


def test_empty_drawing():
    assert describe_drawing({"nodes": [], "links": [], "legend": {}})["note"]


@pytest.fixture
def bound(db, monkeypatch):
    monkeypatch.setattr(db, "close", lambda: None)
    monkeypatch.setattr(database, "SessionLocal", lambda: db)
    setup_graph(
        db,
        n=8,
        attrs={
            "team": {f"n{i}": "red" if i < 4 else "blue" for i in range(8)},
            "score": {f"n{i}": float(i) for i in range(8)},
        },
    )
    tools.layout_circular(1)
    return db


def test_tool_describes_the_saved_drawing_without_a_payload(bound):
    tools.visualization_set_node_color(1, attribute="team", scale_type="CATEGORICAL")
    tools.visualization_set_node_size(1, attribute="score")
    result = tools.visualization_describe(1)

    assert "nodes" not in result and "links" not in result
    assert result["layout"] == "circular"
    assert result["canvas"]["node_count"] == 8
    assert result["groups"]["by"] == "team"
    assert {i["value"] for i in result["groups"]["items"]} == {"red", "blue"}
    assert result["numeric_placement"][0]["attribute"] == "score"
    assert result["prominent_nodes"]["items"][0]["id"] == "n7"
    assert "layout_quality" in result


def test_tool_group_by_and_unknown_attribute(bound):
    result = tools.visualization_describe(1, group_by="team")
    assert result["groups"]["count"] == 2
    with pytest.raises(RuntimeError, match="Known attributes"):
        tools.visualization_describe(1, group_by="nope")
