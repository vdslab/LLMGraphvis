from unittest.mock import AsyncMock, patch

import pytest
from app.services.llm.hooks.builtin.side_effects import (
    on_new_network_id,
    on_view_switch,
)
from app.services.llm.hooks.types import HookContext, HookEvent


@pytest.mark.asyncio
async def test_atomic_extraction_does_not_switch_or_render():
    state = {"network_id": 7}
    ctx = HookContext(
        event=HookEvent.POST_TOOL,
        chat_id=1,
        network_id=7,
        turn_state=state,
        tool_name="subgraph_extract_nodes",
        result={"created_network_id": 9},
    )
    with patch(
        "app.services.llm.hooks.builtin.side_effects._render", new_callable=AsyncMock
    ) as render:
        await on_new_network_id(ctx)
        await on_view_switch(ctx)
    render.assert_not_called()
    assert state["network_id"] == 7


@pytest.mark.asyncio
async def test_select_updates_context_without_rendering():
    state = {"network_id": 7}
    ctx = HookContext(
        event=HookEvent.POST_TOOL,
        chat_id=1,
        network_id=7,
        turn_state=state,
        tool_name="network_select",
        result={"network_id": 9},
    )
    with patch(
        "app.services.llm.hooks.builtin.side_effects._render", new_callable=AsyncMock
    ) as render:
        await on_view_switch(ctx)
    render.assert_not_called()
    assert state["network_id"] == 9
    assert ctx.handled
