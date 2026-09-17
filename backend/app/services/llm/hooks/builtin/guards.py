"""PRE_TOOL safety guards.

These enforce, as mechanism, three rules that previously existed only as prose
in the system prompt — and that a model could therefore skip:

- attributes must exist before you style by them,
- some computations are too expensive to run on a large graph,
- stop retrying after repeated identical calls or repeated failures.

A denied call is not an exception. The engine records
`{"error": ..., "blocked_by": ...}` as the tool result, so the model reads the
reason and corrects itself on the next iteration.
"""

import json
import os
from typing import Any, Dict, List, Optional

from app.core.logging import get_logger

from .. import dbinfo
from ..registry import hook
from ..types import HookContext, HookEvent, ToolCallDecision
from .normalize import _attribute_arg, resolve_attribute

logger = get_logger(__name__)


@hook(HookEvent.PRE_TOOL, tools="*", priority=40, name="guard_tool_is_exposed")
def guard_tool_is_exposed(ctx: HookContext) -> Optional[ToolCallDecision]:
    """Defer stale or invented calls that were absent from this model request."""
    presented = ctx.turn_state.get("presented_tool_names")
    if presented is None or ctx.tool_name in presented:
        return None
    catalog = ctx.turn_state.get("tool_catalog")
    if catalog is None or not catalog.names:
        return None
    if ctx.tool_name in catalog.names:
        return ToolCallDecision.defer(
            f"'{ctx.tool_name}' exists but was not exposed in the current model "
            "request. Load a skill that relates to it or call tool_search with "
            "its exact name, then call it in a later response. A skill or search "
            "call in this same response does not expose it retroactively. Once "
            "exposed it stays callable for the rest of this turn, including "
            "after an ask_user answer."
        )
    return ToolCallDecision.defer(
        f"'{ctx.tool_name}' is not in the live tool catalogue. Use tool_search "
        "with a capability or domain prefix and choose a returned live name."
    )


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name) or default)
    except ValueError:
        logger.warning(f"{name} is not an integer; falling back to {default}")
        return default


def _env_flag(name: str, default: bool = True) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() not in ("0", "false", "no", "off")


# How many times the same tool may be called with identical arguments in one
# turn before the call is refused.
MAX_IDENTICAL_CALLS = _env_int("AGENT_MAX_IDENTICAL_CALLS", 3)

# How many failures of the same tool end the turn.
MAX_TOOL_FAILURES = _env_int("AGENT_MAX_TOOL_FAILURES", 3)


def _fingerprint(tool_name: str, args: Dict[str, Any]) -> str:
    try:
        return f"{tool_name}:{json.dumps(args, sort_keys=True, default=str)}"
    except Exception:
        return f"{tool_name}:{sorted(args.keys())}"


@hook(HookEvent.PRE_TOOL, tools="*", priority=40, name="guard_repeat_call")
def guard_repeat_call(ctx: HookContext) -> Optional[ToolCallDecision]:
    """Refuse the Nth identical call in a turn.

    Runs after the normalizers so the fingerprint is taken over the arguments
    that would actually execute, not the model's raw ones.
    """
    fp = _fingerprint(ctx.tool_name or "", ctx.args)
    counts = ctx.turn_state.setdefault("call_counts", {})
    counts[fp] = counts.get(fp, 0) + 1

    if counts[fp] < MAX_IDENTICAL_CALLS:
        return None

    return ToolCallDecision.deny(
        f"'{ctx.tool_name}' has already been called {counts[fp] - 1} times this "
        f"turn with identical arguments. Repeating it will return the same result. "
        f"Use the result you already have, change the arguments, or explain to the "
        f"user why you cannot proceed."
    )


# Tools whose cost grows faster than linearly. `mitigation_arg`, when present,
# is a parameter that makes the call tractable; supplying it lifts the block.
EXPENSIVE_TOOLS: Dict[str, Dict[str, Optional[str]]] = {
    "analysis_betweenness_centrality": {
        "complexity": "O(N*M)",
        "mitigation_arg": "k",
        "advice": (
            "pass k=500 (or another value well below the node count) to compute an "
            "approximation from sampled pivot nodes"
        ),
    },
    "analysis_closeness_centrality": {
        "complexity": "O(N*M)",
        "mitigation_arg": None,
        "advice": (
            "use analysis_degree_centrality or analysis_pagerank instead, or "
            "extract a smaller subgraph first (for example subgraph_k_core or "
            "subgraph_largest_component)"
        ),
    },
    "layout_kamada_kawai": {
        "complexity": (
            "O(N^2) in both time and memory (it builds a dense N x N distance matrix)"
        ),
        "mitigation_arg": None,
        "advice": (
            "use layout_forceatlas2 or layout_spring, which scale to graphs this size"
        ),
    },
}


@hook(HookEvent.PRE_TOOL, tools="*", priority=50, name="guard_expensive_computation")
def guard_expensive_computation(ctx: HookContext) -> Optional[ToolCallDecision]:
    """Block super-linear computations on graphs above a node threshold.

    Without this, a betweenness-centrality call on a large graph occupies the
    request until it finishes — there is no timeout anywhere in the tool path —
    so the user sees a hung chat rather than an explanation.

    Escape hatches, both environment-level: raise
    `AGENT_EXPENSIVE_NODE_THRESHOLD`, or set
    `AGENT_EXPENSIVE_GUARD_ENABLED=0` to disable the guard entirely.
    """
    spec = EXPENSIVE_TOOLS.get(ctx.tool_name or "")
    if not spec:
        return None
    if not _env_flag("AGENT_EXPENSIVE_GUARD_ENABLED", True):
        return None

    threshold = _env_int("AGENT_EXPENSIVE_NODE_THRESHOLD", 2000)
    network_id = (
        ctx.args.get("network_id")
        or ctx.turn_state.get("network_id")
        or ctx.network_id
    )
    node_count, edge_count = dbinfo.cached_graph_size(
        ctx.turn_state, ctx.db, network_id
    )

    if node_count <= threshold:
        return None

    mitigation = spec.get("mitigation_arg")
    if mitigation and ctx.args.get(mitigation) is not None:
        logger.info(
            f"{ctx.tool_name} allowed on {node_count} nodes: "
            f"mitigation '{mitigation}' supplied"
        )
        return None

    return ToolCallDecision.deny(
        f"'{ctx.tool_name}' is {spec['complexity']} and this network has "
        f"{node_count} nodes and {edge_count} edges, above the safe limit of "
        f"{threshold}. Running it would block the conversation for a long time. "
        f"Instead, {spec['advice']}. "
        f"Tell the user which alternative you chose and why."
    )


@hook(HookEvent.PRE_TOOL, tools="*", priority=60, name="guard_attribute_exists")
def guard_attribute_exists(ctx: HookContext) -> Optional[ToolCallDecision]:
    """Refuse styling/filtering by an attribute the network does not have.

    `normalize_attribute_case` has already fixed pure case differences, so
    anything still unresolved is either a genuinely absent attribute or an
    ambiguous case-insensitive match. Both need the user or a lookup, not a
    guess.
    """
    tool_name = ctx.tool_name or ""
    arg_name = _attribute_arg(tool_name, ctx.args)
    if not arg_name:
        return None

    requested = ctx.args[arg_name]
    resolved, known = resolve_attribute(ctx, tool_name, requested)

    if resolved is not None:
        return None

    if not known:
        # resolve_attribute only returns None with a non-empty candidate list.
        return None

    ambiguous = [name for name in known if name.lower() == requested.lower()]
    if len(ambiguous) > 1:
        return ToolCallDecision.deny(
            f"'{requested}' matches more than one attribute on this network "
            f"({', '.join(sorted(ambiguous))}) and differs only by case. Ask the "
            f"user which one they mean rather than picking one."
        )

    if arg_name == "metric":
        return ToolCallDecision.defer(
            f"Ranking was deferred because '{requested}' is not an attribute of "
            f"this network yet. Available: {_format_candidates(known)}. Run the "
            "matching analysis_* tool first; it saves the attribute and states "
            "the exact name in its result. Then call node_get_top_ranked again."
        )

    return ToolCallDecision.deny(
        f"'{requested}' is not an attribute of this network, so '{tool_name}' "
        f"cannot use it. Available: {_format_candidates(known)}. "
        f"Pick the correct name, or ask the user if none of these is what they meant."
    )



_SIBLING_NODE_CHANNEL = {
    "visualization_set_node_color": "visualization_set_node_size",
    "visualization_set_node_size": "visualization_set_node_color",
}


@hook(
    HookEvent.PRE_TOOL,
    tools="visualization_set_*",
    priority=45,
    name="guard_channel_overwrite",
)
def guard_channel_overwrite(ctx: HookContext) -> Optional[ToolCallDecision]:
    """Stop a channel from being re-pointed at a second attribute in one turn.

    Each channel holds one attribute, so calling the same `set_*` tool twice
    with different attributes discards the first mapping. Between two user
    messages there is no reason to want that: the model is trying to show two
    variables and is putting both on the same channel because the other
    channel's tool is not currently exposed. Deny, and expose the sibling so
    the correction is one call away.
    """
    tool_name = ctx.tool_name or ""
    previous = (ctx.turn_state.get("styled_channels") or {}).get(tool_name)
    attribute = (ctx.args or {}).get("attribute")
    if not previous or not attribute or previous == attribute:
        return None

    sibling = _SIBLING_NODE_CHANNEL.get(tool_name)
    catalog = ctx.turn_state.get("tool_catalog")
    if sibling and catalog is not None:
        catalog.activate([sibling], ctx.turn_state)
    alternative = (
        f" To show both variables, leave this channel on `{previous}` and put "
        f"`{attribute}` on another one — `{sibling}` is now available."
        if sibling
        else ""
    )
    return ToolCallDecision.deny(
        f"`{tool_name}` already encodes `{previous}` in this turn. Calling it "
        f"again with `{attribute}` would replace that mapping, not add to it, "
        f"and the first encoding would be lost.{alternative}"
    )


@hook(
    HookEvent.PRE_TOOL,
    tools="ask_user",
    priority=66,
    name="guard_question_needs_prose",
)
def guard_question_needs_prose(ctx: HookContext) -> Optional[ToolCallDecision]:
    """A form with no accompanying text is a menu the user cannot judge.

    `ask_user` ends the turn, so whatever the model wrote alongside the call is
    the only explanation the user gets. When it wrote nothing, the chat shows a
    bare set of options: no statement of what each one would draw, what it would
    reveal, or what has to be computed first. The prompt asks for that prose; a
    small model routinely skips it, which is the case a hook exists for.

    Deferred at most once per turn. If the model comes back with a form and still
    no text, the form is better than another round trip.
    """
    if ctx.turn_state.get("assistant_text_so_far", "").strip():
        return None
    if ctx.turn_state.get("question_prose_deferred"):
        return None
    ctx.turn_state["question_prose_deferred"] = True
    return ToolCallDecision.defer(
        "This question would reach the user with no explanation: you have written "
        "no text in this turn, and ask_user ends the turn. Write the explanation "
        "as ordinary text first — what the data supports and what each option "
        "would show, naming the visual channels it would assign — then call "
        "ask_user again in that same response, in the user's language."
    )


def _without_layout_coordinates(names: List[str]) -> List[str]:
    """Drop the `{layout}_x` / `{layout}_y` pairs layouts store as node attributes.

    They are internal coordinate storage, never something to style by, and on a
    network with several computed layouts they outnumber the real attributes —
    burying the name the model is actually looking for. A name is only dropped
    when its counterpart exists, so a genuine user attribute called `pos_x`
    survives unless the data also has `pos_y`.
    """
    present = set(names)
    coordinates = {
        name
        for name in names
        if (name.endswith("_x") and f"{name[:-2]}_y" in present)
        or (name.endswith("_y") and f"{name[:-2]}_x" in present)
    }
    return [name for name in names if name not in coordinates]


def _format_candidates(names: List[str], limit: int = 40) -> str:
    ordered = sorted(_without_layout_coordinates(names))
    if not ordered:
        return "(none)"
    if len(ordered) <= limit:
        return ", ".join(ordered)
    return ", ".join(ordered[:limit]) + f", ... (+{len(ordered) - limit} more)"


@hook(HookEvent.TOOL_ERROR, tools="*", priority=50, name="guard_consecutive_failures")
def guard_consecutive_failures(ctx: HookContext) -> None:
    """End the turn after repeated failures of the same tool.

    The prompt has always said "if you fail 3 times, stop and report"; nothing
    enforced it, so a model could burn the whole iteration budget retrying. The
    loop reads `should_abort` and reports the reason to the user.
    """
    tool_name = ctx.tool_name or "unknown"
    failures = ctx.turn_state.setdefault("failure_counts", {})
    failures[tool_name] = failures.get(tool_name, 0) + 1

    if failures[tool_name] < MAX_TOOL_FAILURES:
        return

    ctx.abort_turn(
        f"'{tool_name}' failed {failures[tool_name]} times in a row. "
        f"Last error: {ctx.error}"
    )
    logger.warning(f"Turn aborted: {tool_name} failed {failures[tool_name]} times")
