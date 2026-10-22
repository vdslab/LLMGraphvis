"""Camera bookkeeping for the one-shot viewport channel (ADR 0023).

A viewport instruction changes nothing but the user's view, so repeating it
within a turn costs a model round trip and a render for no visible effect.
Observed in practice: `visualization_highlight(zoom_to=True)` followed by
two identical `visualization_set_viewport(target='highlighted')` calls.

POST_TOOL records what the camera currently frames; PRE_TOOL refuses a
viewport call that would frame the same thing again. Anything that can move
nodes or change the highlighted set forgets the record.
"""

from typing import Any, Dict, Optional, Tuple

from ..registry import hook
from ..types import HookContext, HookEvent, ToolCallDecision

_FRAMED = "framed_view"

# Tools after which the same viewport call would frame something different.
_MOVES_VIEW_PREFIXES = ("layout_", "subgraph_", "network_")
_MOVES_VIEW = {
    "visualization_switch_network",
    "switch_to_main_network",
    "switch_to_parent_network",
    "node_update_label",
    "apply_parameter_tuning",
}


def _key(network_id: Any, target: str, node_ids: Optional[list]) -> Tuple:
    if target == "nodes":
        return (network_id, "nodes", tuple(sorted(node_ids or [])))
    return (network_id, target)


def _viewport_key(args: Dict[str, Any]) -> Tuple:
    return _key(
        args.get("network_id"), args.get("target") or "all", args.get("node_ids")
    )


@hook(
    HookEvent.PRE_TOOL,
    tools="visualization_set_viewport",
    priority=45,
    name="guard_redundant_viewport",
)
def guard_redundant_viewport(ctx: HookContext) -> Optional[ToolCallDecision]:
    framed = ctx.turn_state.get(_FRAMED) or set()
    if _viewport_key(ctx.args) not in framed:
        return None
    return ToolCallDecision.deny(
        "The view already frames exactly this earlier in this turn "
        "(visualization_highlight with zoom_to=True, or the same viewport call), "
        "and nothing has moved since. No further viewport call is needed; "
        "continue with the next step or report the result."
    )


@hook(HookEvent.POST_TOOL, tools="*", priority=20, name="record_framed_view")
def record_framed_view(ctx: HookContext) -> None:
    name = ctx.tool_name or ""
    framed = ctx.turn_state.setdefault(_FRAMED, set())
    if name == "visualization_set_viewport":
        framed.add(_viewport_key(ctx.args))
    elif name == "visualization_highlight":
        # A new highlight changes what 'highlighted' refers to.
        framed.clear()
        viewport = ctx.result.get("viewport") if isinstance(ctx.result, dict) else None
        if viewport:
            network_id = ctx.args.get("network_id")
            framed.add(_key(network_id, "highlighted", None))
            framed.add(_key(network_id, "nodes", viewport.get("node_ids")))
    elif name in _MOVES_VIEW or name.startswith(_MOVES_VIEW_PREFIXES):
        framed.clear()
