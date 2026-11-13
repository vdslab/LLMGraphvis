"""The redundant-viewport guard (hooks/builtin/view.py)."""

import pytest

from app.services.llm.hooks.builtin import view
from app.services.llm.hooks.types import HookContext, HookEvent, new_turn_state


@pytest.mark.parametrize(
    "user_text, preserve",
    [
        ("ノードID 0だけを強調し、それ以外を薄くしてください。", True),
        ("Highlight node 0 and dim the rest", True),
        ("Zoom in on node 0 and highlight it", False),
        ("ノード0に寄って強調してください", False),
        ("ノード0を拡大して強調してください", False),
        ("Highlight node 0 without zooming", True),
        ("ズームしないでノード0だけ強調してください", True),
        ("Keep the current zoom and highlight node 0", True),
        ("Highlight node 0 without changing the zoom", True),
    ],
)
def test_highlight_preserves_camera_unless_zoom_was_requested(user_text, preserve):
    c = HookContext(
        event=HookEvent.PRE_TOOL,
        chat_id=1,
        network_id=7,
        turn_state={"user_text": user_text},
        tool_name="visualization_highlight",
        args={"network_id": 7, "node_ids": ["0"], "zoom_to": True},
    )
    decision = view.preserve_highlight_camera(c)
    if preserve:
        assert decision.action == "modify"
        assert decision.args["zoom_to"] is False
        assert decision.args["node_ids"] == ["0"]
    else:
        assert decision is None


def run(event, tool, args, state, result=None):
    ctx = HookContext(
        event=event,
        chat_id=1,
        network_id=7,
        turn_state=state,
        tool_name=tool,
        args=args,
        result=result,
    )
    if event == HookEvent.PRE_TOOL:
        return view.guard_redundant_viewport(ctx)
    return view.record_framed_view(ctx)


def test_zoom_after_highlight_with_zoom_to_is_refused():
    state = new_turn_state(10)
    run(
        HookEvent.POST_TOOL,
        "visualization_highlight",
        {"network_id": 7, "node_ids": ["a", "b"], "zoom_to": True},
        state,
        result={"viewport": {"mode": "nodes", "node_ids": ["a", "b"]}},
    )

    decision = run(
        HookEvent.PRE_TOOL,
        "visualization_set_viewport",
        {"network_id": 7, "target": "highlighted"},
        state,
    )
    assert decision.action == "deny"

    same_nodes = run(
        HookEvent.PRE_TOOL,
        "visualization_set_viewport",
        {"network_id": 7, "target": "nodes", "node_ids": ["b", "a"]},
        state,
    )
    assert same_nodes.action == "deny"


def test_repeat_viewport_is_refused_until_something_moves():
    state = new_turn_state(10)
    args = {"network_id": 7, "target": "all"}
    assert run(HookEvent.PRE_TOOL, "visualization_set_viewport", args, state) is None
    run(HookEvent.POST_TOOL, "visualization_set_viewport", args, state)

    again = run(HookEvent.PRE_TOOL, "visualization_set_viewport", args, state)
    assert again.action == "deny"

    run(HookEvent.POST_TOOL, "layout_forceatlas2", {"network_id": 7}, state)
    assert run(HookEvent.PRE_TOOL, "visualization_set_viewport", args, state) is None


def test_a_new_highlight_without_zoom_allows_zooming_to_it():
    state = new_turn_state(10)
    target = {"network_id": 7, "target": "highlighted"}
    run(HookEvent.POST_TOOL, "visualization_set_viewport", target, state)
    run(
        HookEvent.POST_TOOL,
        "visualization_highlight",
        {"network_id": 7, "node_ids": ["c"]},
        state,
        result={"nodes": [], "links": []},
    )

    assert run(HookEvent.PRE_TOOL, "visualization_set_viewport", target, state) is None
