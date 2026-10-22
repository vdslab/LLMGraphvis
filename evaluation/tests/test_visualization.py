from evaluation.visualization import diff_visualizations, summarize_visualization


def test_summarize_visualization_detects_invalid_state() -> None:
    state = {
        "network_id": 7,
        "nodes": [
            {"id": "a", "x": 1, "y": 2, "color": "#fff", "size": 3},
            {"id": "b", "x": None, "y": 4, "color": "", "size": "large"},
        ],
        "links": [{"source": "a", "target": "missing"}],
    }

    summary = summarize_visualization(state)

    assert summary["node_count"] == 2
    assert summary["link_count"] == 1
    assert any("invalid coordinates" in issue for issue in summary["issues"])
    assert any("invalid colors" in issue for issue in summary["issues"])
    assert any("links reference" in issue for issue in summary["issues"])


def test_diff_visualizations_reports_encoding_change() -> None:
    before = {
        "network_id": 1,
        "render": {
            "nodes": [{"id": "a", "x": 1, "y": 2, "size": 2}],
            "links": [],
        },
        "metadata": {"last_layout_name": "spring"},
        "node_attributes": [{"name": "group"}],
        "edge_attributes": [],
    }
    after = {
        **before,
        "render": {
            "nodes": [{"id": "a", "x": 4, "y": 5, "size": 8}],
            "links": [],
        },
        "metadata": {"last_layout_name": "forceatlas2"},
    }

    result = diff_visualizations(before, after)

    assert result["changed"] is True
    assert "node_size" in result["changes"]
    assert "position_hash" in result["changes"]
    assert "layout" in result["changes"]
    assert result["after"]["node_attributes"] == ["group"]
