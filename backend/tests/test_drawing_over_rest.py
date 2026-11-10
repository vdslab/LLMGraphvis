"""A drawing tool's receipt becomes the canvas's drawing over REST (ADR 0045)."""

from unittest.mock import AsyncMock, patch

import pytest

from app.services.llm import drawing
from app.services.llm.hooks.builtin.side_effects import (
    on_label_update,
    on_visualization_payload,
)
from app.services.llm.hooks.types import HookContext, HookEvent
from app.services.llm.observations import truncate_tool_result

ROWS = {"nodes": [{"id": "a"}, {"id": "b"}], "links": [{"source": "a", "target": "b"}]}
RECEIPT = {
    "rendered": True,
    "network_id": 7,
    "node_count": 2,
    "link_count": 1,
    "legend": {"node_color": {"type": "linear"}},
    "layout_quality": {"score": 0.1},
    "viewport": {"mode": "fit"},
}


def _rest(payload=None):
    return patch(
        "app.services.network_service.build_visualization",
        new_callable=AsyncMock,
        return_value=dict(payload or {**ROWS, "legend": {}, "network_id": 7}),
    )


def _ctx(tool_name, result):
    return HookContext(
        event=HookEvent.POST_TOOL,
        chat_id=1,
        network_id=7,
        turn_state={"network_id": 7},
        tool_name=tool_name,
        result=result,
        queue=AsyncMock(),
    )


@pytest.mark.asyncio
async def test_receipt_is_completed_with_rows_and_keeps_its_own_keys():
    with _rest() as rest:
        drawn = await drawing.resolve(RECEIPT)

    rest.assert_awaited_once_with(7, with_quality=False)
    assert drawn["nodes"] == ROWS["nodes"] and drawn["links"] == ROWS["links"]
    # Not saved with the network, so only the receipt has them.
    assert drawn["viewport"] == {"mode": "fit"}
    assert drawn["layout_quality"] == {"score": 0.1}
    assert drawn["legend"] == RECEIPT["legend"]
    assert not {"rendered", "node_count", "link_count"} & set(drawn)


@pytest.mark.asyncio
async def test_non_drawing_results_resolve_to_nothing_without_a_request():
    with _rest() as rest:
        assert await drawing.resolve({"message": "Saved."}) is None
        # `rendered` alone, as a stored observation has it, names no network.
        assert await drawing.resolve({"rendered": True}) is None
        assert await drawing.resolve("text") is None
    rest.assert_not_awaited()


@pytest.mark.asyncio
async def test_a_full_payload_from_a_deprecated_tool_is_drawn_as_it_is():
    with _rest() as rest:
        assert await drawing.resolve(ROWS) is ROWS
    rest.assert_not_awaited()


@pytest.mark.asyncio
async def test_hook_pushes_the_fetched_drawing_to_the_canvas():
    ctx = _ctx("visualization_set_node_color", RECEIPT)
    with _rest():
        await on_visualization_payload(ctx)

    event = ctx.queue.put.await_args.args[0]
    assert event["event"] == "render_update"
    assert '"nodes"' in event["data"] and '"viewport"' in event["data"]


@pytest.mark.asyncio
async def test_hook_leaves_the_canvas_alone_when_the_fetch_fails():
    ctx = _ctx("visualization_set_node_color", RECEIPT)
    with patch(
        "app.services.network_service.build_visualization",
        new_callable=AsyncMock,
        side_effect=RuntimeError("networkx-api unreachable"),
    ):
        await on_visualization_payload(ctx)

    ctx.queue.put.assert_not_awaited()


@pytest.mark.asyncio
async def test_the_backends_own_redraw_goes_over_rest_not_mcp():
    ctx = _ctx("node_update_label", {"message": "Renamed."})
    with (
        _rest() as rest,
        patch(
            "app.services.llm.mcp_client.execute_tool", new_callable=AsyncMock
        ) as mcp_call,
    ):
        await on_label_update(ctx)

    rest.assert_awaited_once_with(7, with_quality=True)
    mcp_call.assert_not_awaited()
    ctx.queue.put.assert_awaited_once()


def test_the_model_sees_a_receipt_as_it_saw_a_drawing():
    """The observation is unchanged by where the counts are computed."""
    legacy = {
        k: v
        for k, v in RECEIPT.items()
        if k not in ("rendered", "node_count", "link_count")
    }
    assert truncate_tool_result({**ROWS, **legacy}) == truncate_tool_result(RECEIPT)
