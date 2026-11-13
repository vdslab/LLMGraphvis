import copy
import math
from pathlib import Path

from evaluation.scenarios import (
    KARATE,
    audit_tool_arguments,
    browser_checks,
    check_drawing,
    fixture,
)


def _degree_drawing():
    original = fixture(Path(__file__).resolve().parents[2] / KARATE)
    state = {
        "network_id": 1,
        "metadata": {"last_node_size_config": {"attribute": "degree_centrality"}},
        "render": {
            "nodes": [
                {
                    "id": key,
                    "x": 0,
                    "y": 1,
                    "color": "#123456",
                    "size": original["degree"][key] + 1,
                    "opacity": 1,
                }
                for key in original["nodes"]
            ],
            "links": [{"source": a, "target": b} for a, b in original["edges"]],
        },
    }
    return original, state


def test_outcome_checks_reject_reversed_sizes_and_unrequested_extraction():
    original, state = _degree_drawing()
    assert all(check_drawing("degree", original, state, 1).values())
    wrong = copy.deepcopy(state)
    for node in wrong["render"]["nodes"]:
        node["size"] = 100 - node["size"]
    assert not check_drawing("degree", original, wrong, 1)["degree_size_order"]
    wrong = copy.deepcopy(state)
    wrong["network_id"] = 2
    wrong["render"]["nodes"].pop()
    checks = check_drawing("focus", original, wrong, 1)
    assert not checks["scope"]
    assert not checks["node_ids"]
    assert not checks["highlighted_ids"]


def test_browser_checks_reject_stale_encoding_even_with_matching_counts():
    _, state = _degree_drawing()
    capture = {
        "captured": True,
        "dom_consistent": True,
        "errors": [],
        "svg_validation": {"invalid_node_elements": 0},
        "rendered_nodes": [
            {
                "id": node["id"],
                "color": node["color"],
                "opacity": 1,
                "radius": math.sqrt(node["size"] * 10 / math.pi),
            }
            for node in state["render"]["nodes"]
        ],
    }
    assert all(browser_checks(capture, state).values())
    capture["rendered_nodes"][0]["color"] = "#ffffff"
    assert not browser_checks(capture, state)["drawn_channels_match"]
    capture["errors"] = ["Backend reported error"]
    assert not browser_checks(capture, state)["no_console_errors"]


def test_tool_audit_catches_color_arguments_on_size_tool():
    schemas = {
        "visualization_set_node_size": {
            "properties": {
                "network_id": {},
                "attribute": {},
                "transform": {},
            }
        }
    }
    notes = audit_tool_arguments(
        [
            {
                "tool_name": "visualization_set_node_size",
                "arguments": {
                    "network_id": 1,
                    "attribute": "degree_centrality",
                    "scale_type": "LINEAR",
                },
            },
        ],
        schemas,
    )
    assert notes == [
        {"tool": "visualization_set_node_size", "undeclared_arguments": ["scale_type"]}
    ]
