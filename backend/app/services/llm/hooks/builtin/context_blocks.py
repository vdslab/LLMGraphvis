"""TURN_START hooks: what gets appended to the system prompt for this turn.

Order matters only for readability of the assembled prompt; each hook
contributes one block via `ctx.add_context()`.
"""

from app.core.logging import get_logger

from ..registry import hook
from ..types import HookContext, HookEvent

logger = get_logger(__name__)


@hook(HookEvent.TURN_START, priority=10, name="inject_skill_index")
def inject_skill_index(ctx: HookContext) -> None:
    """The always-on catalogue of loadable skills."""
    from ...skills import registry as skill_registry

    block = skill_registry.index_block()
    if block:
        ctx.add_context(block)


@hook(HookEvent.TURN_START, priority=20, name="inject_skill_suggestions")
def inject_skill_suggestions(ctx: HookContext) -> None:
    """Point at the skills whose triggers match this request.

    Costs one line. Deliberately advisory: the index is always present, so a
    missed keyword match degrades to "the model picks for itself" rather than
    "the procedure is unreachable".
    """
    from ...skills import registry as skill_registry

    current_layout = _current_layout(ctx)
    # Recorded for the turn trace (ADR 0032): suggested vs. actually loaded.
    ctx.turn_state["skills_suggested"] = [
        skill.name
        for skill in skill_registry.suggestions(
            ctx.user_text, current_layout=current_layout
        )
    ]
    block = skill_registry.suggestion_block(
        ctx.user_text, current_layout=current_layout
    )
    if block:
        ctx.add_context(block)


def _current_layout(ctx: HookContext):
    """The layout algorithm the active network was last drawn with, if any."""
    if ctx.db is None or not ctx.network_id:
        return None
    from common import models

    network = (
        ctx.db.query(models.Network.last_layout_name)
        .filter(models.Network.id == ctx.network_id)
        .first()
    )
    return network[0] if network else None


@hook(HookEvent.TURN_START, priority=30, name="inject_iteration_budget")
def inject_iteration_budget(ctx: HookContext) -> None:
    """Tell the model how many tool-calling rounds it has.

    `AGENT_MAX_ITERATIONS` silently truncated turns before this: a model that
    planned eight steps would be cut off at the limit with no idea a limit
    existed, and the user got a half-finished analysis with no explanation.
    """
    budget = ctx.turn_state.get("max_iterations")
    if not budget:
        return
    ctx.add_context(
        f"# Budget\n"
        f"You have at most {budget} tool-calling rounds in this turn (tool calls made "
        f"together in one response count as one round). Plan accordingly: batch "
        f"independent calls into a single response, and if the task genuinely "
        f"needs more than that, do the most informative part first and tell the "
        f"user what remains."
    )


@hook(HookEvent.TURN_START, priority=40, name="inject_active_tuning")
def inject_active_tuning(ctx: HookContext) -> None:
    """Current values of the active tuning panel, and what the user changed there.

    The panel re-runs the pipeline without the agent, so this block is the only
    way the agent learns the canvas no longer shows the values it last chose.
    See ADR 0016.
    """
    from ... import tuning

    if ctx.db is None:
        return
    row = tuning.active_tuning(ctx.db, ctx.chat_id, ctx.network_id)
    if row is not None:
        ctx.turn_state["tuning_tools"] = {tuning.APPLY_TOOL}
        ctx.add_context(tuning.context_block(ctx.db, row))
        return
    # A tuning request about a view drawn in an earlier turn: without this the
    # offer tool is unreachable and a small model falls back to an ask_user menu.
    pipeline = tuning.offerable_pipeline(
        ctx.db, ctx.chat_id, ctx.network_id, ctx.user_text
    )
    if pipeline:
        ctx.turn_state["tuning_tools"] = {tuning.OFFER_TOOL, *pipeline}
        ctx.add_context(tuning.offer_hint(pipeline))
