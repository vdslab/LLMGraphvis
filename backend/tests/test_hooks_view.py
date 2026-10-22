"""The redundant-viewport guard (hooks/builtin/view.py)."""

from app.services.llm.hooks.builtin import view
from app.services.llm.hooks.types import HookContext, HookEvent, new_turn_state


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
