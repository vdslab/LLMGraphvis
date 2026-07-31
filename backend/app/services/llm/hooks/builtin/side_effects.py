"""POST_TOOL side effects: rendering and active-network switching.

This replaces the hardcoded if/elif chain that used to live in
`GraphVisAgent._handle_side_effects()`. The behaviour is the same; the
difference is that handlers are now registered against tool-name patterns, so
changing which tools return a visualization payload no longer requires editing
the engine.

The rules, in dispatch order:

1. `on_new_network_id` — any tool that reports a `new_network_id` (all the
   `subgraph_*` creators) switches the chat's active network and renders it.
2. `on_label_update` — `node_update_label` changes what is drawn but returns no
   payload, so it needs an explicit re-render.
3. `on_visualization_payload` — any tool that already returns `{nodes, links}`
   (the `visualization_*` family) just gets pushed to the client as-is.
"""

from typing import Any, Dict, Optional

from app.core.logging import get_logger
from common import models

from ... import emitters
from ..registry import hook
from ..types import HookContext, HookEvent

logger = get_logger(__name__)


def _active_network_id(ctx: HookContext) -> int:
    """The network the turn is currently pointed at.

    `turn_state` is the source of truth because a single iteration can switch
    networks and later hooks in the same iteration must see the new value.
    """
    return ctx.turn_state.get("network_id") or ctx.network_id


def _update_chat_state(
    ctx: HookContext,
    network_id: Optional[int] = None,
    vis_data: Optional[Dict] = None,
) -> None:
    """Persist the active network / last rendered payload onto the chat row."""
    if not ctx.db:
        return
    chat = ctx.db.query(models.Chat).filter(models.Chat.id == ctx.chat_id).first()
    if not chat:
        return
    if network_id is not None:
        chat.network_id = network_id
    if vis_data is not None:
        chat.visualization_state = vis_data
    ctx.db.commit()


async def _render(ctx: HookContext, network_id: int) -> Optional[Dict[str, Any]]:
    """Build and push a visualization for `network_id`."""
    from ... import mcp_client

    try:
        vis_data = await mcp_client.execute_tool(
            "visualization_generate", {"network_id": network_id}, session=ctx.session
        )
    except Exception as e:
        logger.error(f"Auto-visualization failed for network {network_id}: {e}")
        return None

    if isinstance(vis_data, dict) and "nodes" in vis_data:
        await emitters.emit_render_update(ctx.queue, vis_data)
        return vis_data
    return None


@hook(HookEvent.POST_TOOL, tools="*", priority=10, name="on_new_network_id")
async def on_new_network_id(ctx: HookContext) -> None:
    """A tool created a new network (subgraph): make it active and draw it."""
    if not isinstance(ctx.result, dict):
        return

    new_id = ctx.result.get("new_network_id")
    if new_id is None:
        return

    current = _active_network_id(ctx)
    if new_id == current:
        return

    logger.info(f"Context switch: {current} -> {new_id}")
    vis_data = await _render(ctx, new_id)
    _update_chat_state(ctx, network_id=new_id, vis_data=vis_data)
    ctx.turn_state["network_id"] = new_id
    # We already rendered the new network; stop later handlers from also pushing
    # the creating tool's own (pre-switch) payload on top of it.
    ctx.handled = True


# Tools whose whole purpose is to change which network is being looked at, but
# which report the target as `network_id` rather than `new_network_id` (or, for
# the two local tools, do not report it at all). Without this handler the view
# changed but the agent's effective network_id did not, so the *next* tool call
# in the same turn silently operated on the previous network.
_VIEW_SWITCH_TOOLS = (
    "visualization_switch_network",
    "switch_to_main_network",
    "switch_to_parent_network",
)


@hook(HookEvent.POST_TOOL, tools="*", priority=15, name="on_view_switch")
async def on_view_switch(ctx: HookContext) -> None:
    """Follow an explicit view switch with the agent's own context."""
    if ctx.handled or ctx.tool_name not in _VIEW_SWITCH_TOOLS:
        return

    target = _switch_target(ctx)
    if target is None or target == _active_network_id(ctx):
        return

    logger.info(f"View switch via {ctx.tool_name}: -> {target}")
    ctx.turn_state["network_id"] = target

    # `visualization_switch_network` already returns a rendered payload; the two
    # local tools return only a message, so they need a render of their own.
    if isinstance(ctx.result, dict) and "nodes" in ctx.result and "links" in ctx.result:
        await emitters.emit_render_update(ctx.queue, ctx.result)
        _update_chat_state(ctx, network_id=target, vis_data=ctx.result)
    else:
        vis_data = await _render(ctx, target)
        _update_chat_state(ctx, network_id=target, vis_data=vis_data)

    ctx.handled = True


def _switch_target(ctx: HookContext) -> Optional[int]:
    """The network a view-switch tool moved to.

    `visualization_switch_network` echoes it as `network_id`; the two local
    hierarchy tools report nothing usable, so the chat row — which they update
    themselves — is the only source.
    """
    if isinstance(ctx.result, dict):
        candidate = ctx.result.get("network_id")
        if isinstance(candidate, int):
            return candidate

    if ctx.db:
        chat = ctx.db.query(models.Chat).filter(models.Chat.id == ctx.chat_id).first()
        if chat and isinstance(chat.network_id, int):
            return chat.network_id
    return None


@hook(
    HookEvent.POST_TOOL, tools="node_update_label", priority=20, name="on_label_update"
)
async def on_label_update(ctx: HookContext) -> None:
    """Renaming a node changes the drawing but returns no payload."""
    if ctx.handled:
        return
    await _render(ctx, _active_network_id(ctx))
    ctx.handled = True


@hook(HookEvent.POST_TOOL, tools="*", priority=30, name="on_visualization_payload")
async def on_visualization_payload(ctx: HookContext) -> None:
    """The tool already returned a renderable payload: forward it."""
    if ctx.handled:
        return
    if not isinstance(ctx.result, dict):
        return

    vis_data = None
    if "nodes" in ctx.result and "links" in ctx.result:
        vis_data = ctx.result
    elif (
        ctx.tool_name in ("network_initialize", "initialize_network")
        and "network" in ctx.result
    ):
        # `initialize_network` is the pre-refactor name; both are accepted so the
        # deprecated compound tool keeps rendering if anything still calls it.
        vis_data = ctx.result["network"]

    if vis_data:
        await emitters.emit_render_update(ctx.queue, vis_data)
        _update_chat_state(ctx, vis_data=vis_data)
