"""Tuning panel exposure and the one nudge to offer it. See ADR 0016.

`offer_parameter_tuning` is useless before a pipeline exists, so it is not in
the initial exposure set (ADR 0010). It appears the moment an analysis, layout
or visualization call succeeds in this turn.

Skill guidance alone did not make a local model offer a panel after community
detection; its closing invitation was turned into an `ask_user` menu instead.
So when a parameter-sensitive result was drawn and the model stopped without a
panel, it is asked once to attach one.
"""

from ..registry import hook
from ..types import HookContext, HookEvent

# Tools whose drawn result changes markedly with a parameter the user is likely
# to want to compare, and that parameter.
SENSITIVE_TOOLS = {
    "analysis_louvain_communities": "resolution",
    "analysis_greedy_modularity_communities": "resolution",
    "layout_forceatlas2": "scaling_ratio and gravity",
    "layout_spring": "k",
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
    tool = completed[start]
    pipeline = [tool] + [
        name
        for name in dict.fromkeys(completed[start + 1 :])
        if name.startswith("visualization_") and tuning.is_tunable_tool(name)
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
