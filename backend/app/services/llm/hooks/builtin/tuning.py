"""Tuning panel exposure, the nudge to offer it (ADR 0016), and the question of
how to tune a force layout just drawn (ADR 0018).

`offer_parameter_tuning` is useless before a pipeline exists, so it is not in
the initial exposure set (ADR 0010). It appears the moment an analysis, layout
or visualization call succeeds in this turn.

Skill guidance alone did not make a local model offer a panel after community
detection; its closing invitation was turned into an `ask_user` menu instead.
So when a parameter-sensitive result was drawn and the model stopped without a
panel, it is asked once to attach one.
"""

from typing import Optional

from ..registry import hook
from ..types import HookContext, HookEvent

# Tools whose drawn result changes markedly with a parameter the user is likely
# to want to compare, and that parameter.
SENSITIVE_TOOLS = {
    "analysis_louvain_communities": "resolution",
    "analysis_greedy_modularity_communities": "resolution",
    "layout_forceatlas2": "scaling_ratio and gravity",
    "layout_spring": "k",
    "layout_arf": "scaling and a",
}


@hook(HookEvent.POST_TOOL, tools="*", priority=40, name="expose_tuning_offer")
def expose_tuning_offer(ctx: HookContext) -> None:
    from ... import tuning

    if not ctx.tool_name or not tuning.is_tunable_tool(ctx.tool_name):
        return
    catalog = ctx.turn_state.get("tool_catalog")
    if catalog is not None:
        catalog.activate([tuning.OFFER_TOOL], ctx.turn_state)


@hook(HookEvent.NO_TOOL_CALLS, priority=3, name="nudge_tuning_offer")
def nudge_tuning_offer(ctx: HookContext) -> None:
    """Ask once for a panel after a parameter-sensitive result was drawn.

    Runs before `nudge_choice_ui`: a closing "anything else?" after community
    detection is not a fork between alternatives, and the granularity knob is
    the more useful thing to attach.
    """
    from ... import tuning
    from .intent import MAX_CONTINUATIONS

    state = ctx.turn_state
    if state.get("input_request") or state.get("tuning_nudged"):
        return
    if state.get("continuations_granted", 0) >= MAX_CONTINUATIONS:
        return
    if not (ctx.assistant_text or "").strip():
        return  # force_final_summary owns a turn with no closing text

    calls = state.get("executed_calls") or []
    if any(c["name"] in (tuning.OFFER_TOOL, tuning.APPLY_TOOL) for c in calls):
        return
    completed = [c["name"] for c in calls if c["status"] == "completed"]
    sensitive = [i for i, name in enumerate(completed) if name in SENSITIVE_TOOLS]
    if not sensitive:
        return
    if ctx.db is not None and tuning.active_tuning(ctx.db, ctx.chat_id, ctx.network_id):
        return

    start = sensitive[-1]
    if not any(tuning.is_rendering_tool(name) for name in completed[start + 1 :]):
        return  # a computed attribute or stored layout is not yet a drawn view
    tool = completed[start]
    pipeline = [tool] + [
        name
        for name in dict.fromkeys(completed[start + 1 :])
        if tuning.is_rendering_tool(name)
    ]
    state["tuning_nudged"] = True
    ctx.request_continuation(
        prompt=(
            f"The view you just drew depends strongly on {tool}'s "
            f"{SENSITIVE_TOOLS[tool]}. Attach a tuning panel now: call "
            f"{tuning.OFFER_TOOL} with tools={pipeline}, 1-2 fields for those "
            "parameters (minimum, maximum, step, low_label/high_label in the "
            "conversation language, and a suggested value with a one-sentence "
            "rationale grounded in this data). Do not repeat your explanation; add "
            "at most one sentence saying the values can also be adjusted by just "
            "telling you. Do not run any other analysis."
        ),
        model_text=ctx.assistant_text,
    )


# Layouts with readability knobs (networkx-api logic/layouts: `knobs=`). Keep in
# step when a layout gains or loses knobs.
FORCE_LAYOUTS = frozenset({"layout_forceatlas2", "layout_spring", "layout_arf"})
# Arguments that choose what to lay out, not how: a call carrying only these
# ran on the automatic, profile-tuned defaults.
_NOT_TUNING = frozenset({"network_id", "seed", "weight", "force_recompute"})
# `layout_*` tools that compute no coordinates.
_EVALUATION_TOOLS = frozenset({"layout_profile", "layout_suggest_parameters"})
# Having already started tuning in this turn is an answer to the question.
_TUNING_STARTED = frozenset(
    {"layout_suggest_parameters", "offer_parameter_tuning", "apply_parameter_tuning"}
)


@hook(HookEvent.NO_TOOL_CALLS, priority=2, name="nudge_layout_choice")
def nudge_layout_choice(ctx: HookContext) -> None:
    """After the first force layout on a network, ask how to tune it. ADR 0018.

    Fires once, only when the layout ran on automatic defaults and was drawn,
    and only the first time the agent lays this network out in this chat or
    when it switched algorithm. Runs before `nudge_tuning_offer`, which it
    replaces for such a layout.
    """
    from .intent import MAX_CONTINUATIONS

    state = ctx.turn_state
    if state.get("input_request") or state.get("layout_choice_nudged"):
        return
    if state.get("continuations_granted", 0) >= MAX_CONTINUATIONS:
        return
    if not (ctx.assistant_text or "").strip():
        return

    calls = [c for c in (state.get("executed_calls") or []) if c["status"] == "completed"]
    if any(c["name"] in _TUNING_STARTED for c in calls):
        return
    layout = _drawn_force_layout(calls)
    if layout is None:
        return
    args = layout.get("args") or {}
    if set(args) - _NOT_TUNING:
        return  # the user (or the model) already chose parameters

    network_id = args.get("network_id") or state.get("network_id") or ctx.network_id
    previous = _previous_layout(ctx, network_id)
    if previous == layout["name"]:
        return

    state["layout_choice_nudged"] = True
    state["tuning_nudged"] = True  # this question replaces the panel nudge
    ctx.request_continuation(
        prompt=(
            f"You drew {layout['name']} with automatic parameters. Before ending, "
            "keep your explanation and add one or two sentences on how readable the "
            "drawing is, from `layout_quality` in plain words (if `issues` is empty, "
            "say there is no obvious problem). Then call ask_user once with a single "
            "select field asking how to adjust the layout, with exactly these three "
            "options in the conversation language: let you tune it automatically "
            "(おまかせで調整), adjust it themselves from the current values "
            "(今の値から自分で調整), or keep it as it is (このままでよい). Describe "
            "each option by what will happen. Do not run any tool other than "
            "ask_user, and do not tune anything yet."
        ),
        model_text=ctx.assistant_text,
    )


def _drawn_force_layout(calls) -> Optional[dict]:
    """The last force-layout call of this turn, if a render followed it."""
    for i in range(len(calls) - 1, -1, -1):
        if calls[i]["name"] in FORCE_LAYOUTS:
            later = [c["name"] for c in calls[i + 1 :]]
            return calls[i] if "visualization_generate" in later else None
    return None


def _previous_layout(ctx: HookContext, network_id) -> Optional[str]:
    """The last layout tool the agent ran on this network in earlier turns.

    Tool executions are stored after a turn ends, so these are all earlier
    turns. The upload pipeline's automatic layout is not a tool execution of
    the chat and so never counts. A stored call without `network_id` is taken
    to be on the current view, as ADR 0016 does.
    """
    if ctx.db is None:
        return None
    from common import models

    rows = (
        ctx.db.query(models.ToolExecution.tool_name, models.ToolExecution.arguments)
        .join(models.ChatMessage, models.ToolExecution.message_id == models.ChatMessage.id)
        .filter(
            models.ChatMessage.chat_id == ctx.chat_id,
            models.ToolExecution.status == "completed",
            models.ToolExecution.tool_name.like("layout\\_%", escape="\\"),
        )
        .order_by(models.ToolExecution.id.desc())
        .all()
    )
    for name, arguments in rows:
        if name in _EVALUATION_TOOLS:
            continue
        if (arguments or {}).get("network_id", network_id) == network_id:
            return name
    return None
