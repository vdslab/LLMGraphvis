"""Observability: per-turn tallies and cache invalidation.

The tallies are what make the rest of the hook system inspectable — without
them, a denied call looks identical to a call the model never made. They are
also the measurement surface for evaluating the Skills change (see the token
comparison in the plan), since TURN_END reports iteration count per turn.
"""

from app.core.logging import get_logger

from .. import dbinfo
from ..registry import hook
from ..types import HookContext, HookEvent

logger = get_logger(__name__)

# Tools that write new node/edge attributes, invalidating the memoized attribute
# name lists that `guard_attribute_exists` reads. `analysis_*` saves metrics
# (e.g. `pagerank`, `louvain_community`) and `layout_*` saves `{name}_x`/`_y`.
_ATTRIBUTE_CREATING_PATTERNS = ("analysis_", "layout_")


@hook(HookEvent.POST_TOOL, tools="*", priority=90, name="audit_tool_success")
def audit_tool_success(ctx: HookContext) -> None:
    ctx.turn_state["tools_run"] = ctx.turn_state.get("tools_run", 0) + 1

    tool_name = ctx.tool_name or ""
    if tool_name.startswith(_ATTRIBUTE_CREATING_PATTERNS):
        # A metric or layout attribute may have just appeared; make the next
        # attribute check re-read the database rather than trust a stale list.
        dbinfo.invalidate_attributes(ctx.turn_state)

    # A tool that succeeded clears that tool's failure streak, so three failures
    # spread across a recovered turn do not abort it.
    failures = ctx.turn_state.get("failure_counts", {})
    if tool_name in failures:
        failures.pop(tool_name, None)


@hook(HookEvent.TOOL_ERROR, tools="*", priority=90, name="audit_tool_error")
def audit_tool_error(ctx: HookContext) -> None:
    ctx.turn_state["tools_failed"] = ctx.turn_state.get("tools_failed", 0) + 1
    logger.info(f"Tool '{ctx.tool_name}' failed: {ctx.error}")


@hook(HookEvent.TURN_END, priority=100, name="audit_turn_summary")
def audit_turn_summary(ctx: HookContext) -> None:
    ts = ctx.turn_state
    logger.info(
        "Turn summary (chat=%s network=%s): iterations=%s/%s tools_run=%s "
        "blocked=%s modified=%s failed=%s hook_errors=%s aborted=%s",
        ctx.chat_id,
        ts.get("network_id") or ctx.network_id,
        ts.get("iteration"),
        ts.get("max_iterations"),
        ts.get("tools_run", 0),
        ts.get("tools_blocked", 0),
        ts.get("tools_modified", 0),
        ts.get("tools_failed", 0),
        ts.get("hook_errors", 0),
        ts.get("should_abort", False),
    )
    if ts.get("skills_loaded"):
        logger.info(f"Skills loaded this turn: {', '.join(ts['skills_loaded'])}")
    if ts.get("abort_reason"):
        logger.warning(f"Turn abort reason: {ts['abort_reason']}")
