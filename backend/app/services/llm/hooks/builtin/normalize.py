"""PRE_TOOL argument normalization.

These run at low priority numbers so the guards in `guards.py` validate the
already-corrected arguments rather than the model's raw output.

Each hook returns `modify` with a short reason, which the engine attaches to the
tool result. That matters: silently rewriting arguments would leave the model
reporting the value it asked for rather than the value that ran.
"""

from typing import Any, Dict, Optional, Tuple

from app.core.logging import get_logger

from .. import dbinfo
from ..registry import hook
from ..types import HookContext, HookEvent, ToolCallDecision

logger = get_logger(__name__)


# Tools whose `attribute` argument names a NODE attribute, and those where it
# names an EDGE attribute. Anything not listed is left alone.
NODE_ATTRIBUTE_TOOLS = {
    "visualization_set_node_color",
    "visualization_set_node_size",
    "visualization_set_node_labels",
    "node_get_top_ranked",
    "node_filter",
    "subgraph_community",
    "layout_bipartite",
    "layout_multipartite",
}
EDGE_ATTRIBUTE_TOOLS = {
    "visualization_set_edge_color",
    "visualization_set_edge_width",
}

# Argument names that carry an attribute key, in priority order per tool. Most
# use `attribute`; a few use a different name.
ATTRIBUTE_ARG_NAMES = (
    "attribute",
    "attribute_name",
    "community_attribute",
    "metric",
    "partition_attribute",
)


def _attribute_arg(tool_name: str, args: Dict[str, Any]) -> Optional[str]:
    """Which argument of this call holds an attribute key, if any."""
    if tool_name not in NODE_ATTRIBUTE_TOOLS and tool_name not in EDGE_ATTRIBUTE_TOOLS:
        return None
    for name in ATTRIBUTE_ARG_NAMES:
        value = args.get(name)
        if isinstance(value, str) and value:
            return name
    return None


def resolve_attribute(
    ctx: HookContext, tool_name: str, requested: str
) -> Tuple[Optional[str], list]:
    """Match `requested` against the network's real attribute names.

    Returns `(resolved_name_or_None, all_known_names)`. Resolution is exact
    first, then unique case-insensitive match. A case-insensitive match that is
    ambiguous (the network has both `Type` and `type`) resolves to None so the
    guard asks the user instead of picking one.
    """
    is_edge = tool_name in EDGE_ATTRIBUTE_TOOLS
    known = dbinfo.cached_attribute_names(
        ctx.turn_state, ctx.db, ctx.network_id, edges=is_edge
    )
    if not known:
        # Nothing to compare against (no DB, or attributes not loaded yet):
        # do not block or rewrite on the basis of missing information.
        return (requested, known)

    if requested in known:
        return (requested, known)

    lowered = requested.lower()
    matches = [name for name in known if name.lower() == lowered]
    if len(matches) == 1:
        return (matches[0], known)

    return (None, known)


@hook(HookEvent.PRE_TOOL, tools="*", priority=10, name="normalize_network_id")
def normalize_network_id(ctx: HookContext) -> Optional[ToolCallDecision]:
    """Default `network_id` to the chat's active network.

    Previously hardcoded in `GraphVisAgent._run_tool()`. Nearly every
    networkx-api tool requires it and the model has no reason to track it, so
    filling it in is the single most-used normalization in the system.
    """
    if ctx.args.get("network_id"):
        return None

    network_id = ctx.turn_state.get("network_id") or ctx.network_id
    if not network_id:
        return None

    args = {**ctx.args, "network_id": network_id}
    # No `reason`: this is invisible plumbing, not a correction the model needs
    # to report on. Surfacing it on every call would be pure noise.
    return ToolCallDecision.modify(args)


@hook(HookEvent.PRE_TOOL, tools="*", priority=20, name="normalize_attribute_case")
def normalize_attribute_case(ctx: HookContext) -> Optional[ToolCallDecision]:
    """Fix attribute keys that differ from the stored name only by case.

    `Club` -> `club` is a correction; `Nationality` -> `citizenship` is not
    something to guess at, and is left for `guard_attribute_exists` to reject
    with the real candidate list.
    """
    arg_name = _attribute_arg(ctx.tool_name or "", ctx.args)
    if not arg_name:
        return None

    requested = ctx.args[arg_name]
    resolved, _known = resolve_attribute(ctx, ctx.tool_name or "", requested)

    if resolved is None or resolved == requested:
        return None

    args = {**ctx.args, arg_name: resolved}
    return ToolCallDecision.modify(
        args,
        reason=(
            f"attribute '{requested}' was corrected to '{resolved}' "
            f"(exact stored name)"
        ),
    )


# (min, max) bounds per parameter name, applied to any tool that accepts them.
# Bounds reflect what the underlying networkx/logic layer can actually use, not
# taste: e.g. a negative `iterations` makes nx return the initial random layout,
# and `damping_factor >= 1` makes PageRank diverge.
PARAM_BOUNDS: Dict[str, Tuple[float, float]] = {
    "iterations": (1, 100_000),
    "max_iter": (1, 100_000),
    "k": (0.0, 1e6),
    "gravity": (0.0, 1e4),
    "scaling_ratio": (0.01, 1e4),
    "jitter_tolerance": (0.01, 100.0),
    "resolution": (0.01, 100.0),
    "damping_factor": (0.0, 0.999),
    "tol": (1e-12, 1.0),
    "threshold": (1e-12, 1.0),
    "scale": (1e-6, 1e6),
    "min_size": (0.0, 1e5),
    "max_size": (0.0, 1e5),
    "min_width": (0.0, 1e5),
    "max_width": (0.0, 1e5),
    "radius": (1, 100),
    "limit": (1, 100_000),
}

# `k` means "optimal node distance" for layout_spring but "number of pivot
# nodes for approximate betweenness" for analysis_betweenness_centrality. The
# spring meaning is a float in (0, inf); the betweenness meaning is an int >= 1.
# Bounding them identically would be wrong, so betweenness is special-cased.
_K_INTEGER_TOOLS = {"analysis_betweenness_centrality"}


@hook(HookEvent.PRE_TOOL, tools="*", priority=30, name="normalize_numeric_params")
def normalize_numeric_params(ctx: HookContext) -> Optional[ToolCallDecision]:
    """Clamp out-of-range numeric parameters instead of letting them fail."""
    changes = []
    args = dict(ctx.args)

    for name, value in list(args.items()):
        if name not in PARAM_BOUNDS:
            continue
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            continue

        low, high = PARAM_BOUNDS[name]
        if name == "k" and ctx.tool_name in _K_INTEGER_TOOLS:
            low, high = 1, 100_000

        clamped: Any = min(max(value, low), high)
        if clamped == value:
            continue

        if isinstance(value, int) and not isinstance(value, bool):
            clamped = int(clamped)
        args[name] = clamped
        changes.append(f"{name}={value} was clamped to {clamped}")

    if not changes:
        return None

    return ToolCallDecision.modify(args, reason="; ".join(changes))
