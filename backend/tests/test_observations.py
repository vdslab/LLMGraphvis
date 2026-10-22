import json

from app.services.llm.observations import (
    MAP_PREVIEW_ITEMS,
    PAST_OBSERVATION_CHAR_BUDGET,
    compact_past_observation,
    truncate_tool_result,
)


def test_large_numeric_map_keeps_highest_values_and_counts():
    per_node = {f"n{i}": i for i in range(500)}

    compact = truncate_tool_result({"core_numbers": per_node, "node_count": 500})

    summary = compact["core_numbers"]
    assert summary["count"] == 500
    assert summary["min"] == 0 and summary["max"] == 499
    top = range(499, 499 - MAP_PREVIEW_ITEMS, -1)
    assert list(summary["highest"]) == [f"n{i}" for i in top]
    assert summary["omitted"] == 500 - MAP_PREVIEW_ITEMS
    assert compact["node_count"] == 500


def test_small_maps_and_records_pass_through():
    record = {"attribute": "pagerank", "count": 3, "values": {"a": 1, "b": 2}}

    assert truncate_tool_result(record) == record


def test_large_non_numeric_map_is_previewed_not_ranked():
    labels = {f"n{i}": f"label {i}" for i in range(100)}

    summary = truncate_tool_result(labels)

    assert summary["count"] == 100
    assert "preview" in summary and "highest" not in summary
    assert len(summary["preview"]) == MAP_PREVIEW_ITEMS


def test_past_observation_keeps_scalars_and_names_what_was_dropped():
    result = {
        "network_id": 7,
        "saved_attribute": "louvain_community",
        "sizes": list(range(400)),
        "detail": {f"k{i}": [i] for i in range(200)},
    }

    compact = compact_past_observation(result)

    assert compact["network_id"] == 7
    assert compact["saved_attribute"] == "louvain_community"
    assert compact["sizes"].startswith("<list of 400")
    assert "omitted" in compact["detail"]
    assert len(json.dumps(compact)) < PAST_OBSERVATION_CHAR_BUDGET


def test_small_past_observation_is_unchanged():
    result = {"reachable": True, "source": "a", "target": "b"}

    assert compact_past_observation(result) == result


def test_serialized_observation_keeps_japanese_literal_and_compact():
    from app.services.llm.observations import serialize_observation

    text = serialize_observation({"composer": "モーツァルト", "count": 2})

    assert text == '{"composer":"モーツァルト","count":2}'
    assert serialize_observation("already text") == "already text"
