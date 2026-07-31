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

    block = skill_registry.suggestion_block(ctx.user_text)
    if block:
        ctx.add_context(block)


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
