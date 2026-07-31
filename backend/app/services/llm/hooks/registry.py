"""Hook registration and dispatch.

Registration is by decorator, matched against tool names with `fnmatch`:

    @hook(HookEvent.PRE_TOOL, tools="analysis_*", priority=20)
    async def guard_something(ctx: HookContext) -> ToolCallDecision | None:
        ...

Ordering is by ascending `priority`, so normalization (low numbers) runs before
guards (higher numbers) and guards therefore validate the already-corrected
arguments.
"""

import fnmatch
import inspect
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, List, Optional, Union

from app.core.logging import get_logger

from .types import HookContext, HookEvent, ToolCallDecision

logger = get_logger(__name__)

HookResult = Union[ToolCallDecision, None]
HookFn = Callable[[HookContext], Union[HookResult, Awaitable[HookResult]]]


@dataclass
class Registration:
    event: HookEvent
    fn: HookFn
    tools: str
    priority: int
    name: str


class HookRegistry:
    def __init__(self) -> None:
        self._hooks: Dict[HookEvent, List[Registration]] = {e: [] for e in HookEvent}

    # --- registration ---

    def register(
        self,
        event: HookEvent,
        fn: HookFn,
        tools: str = "*",
        priority: int = 100,
        name: Optional[str] = None,
    ) -> HookFn:
        reg = Registration(
            event=event,
            fn=fn,
            tools=tools,
            priority=priority,
            name=name or str(getattr(fn, "__name__", "anonymous_hook")),
        )
        bucket = self._hooks[event]
        bucket.append(reg)
        bucket.sort(key=lambda r: r.priority)
        return fn

    def hook(
        self,
        event: HookEvent,
        tools: str = "*",
        priority: int = 100,
        name: Optional[str] = None,
    ) -> Callable[[HookFn], HookFn]:
        def decorator(fn: HookFn) -> HookFn:
            return self.register(event, fn, tools=tools, priority=priority, name=name)

        return decorator

    def clear(self) -> None:
        """Drop all registrations. Used by tests to get an isolated registry."""
        for bucket in self._hooks.values():
            bucket.clear()

    def registered(self, event: HookEvent) -> List[str]:
        return [r.name for r in self._hooks[event]]

    # --- dispatch ---

    def _matching(
        self, event: HookEvent, tool_name: Optional[str]
    ) -> List[Registration]:
        regs = self._hooks[event]
        if tool_name is None:
            return list(regs)
        return [
            r for r in regs
            if r.tools == "*" or fnmatch.fnmatch(tool_name, r.tools)
        ]

    async def _call(self, reg: Registration, ctx: HookContext) -> HookResult:
        """Invoke one hook, tolerating both sync and async implementations.

        A hook that raises is logged and treated as "no opinion" (fail-open).
        Failing closed would let a bug in one guard take down every tool call;
        the tradeoff is that a crashing guard stops guarding, which is why
        `tools_hook_errors` is tallied and surfaced at TURN_END.
        """
        try:
            result = reg.fn(ctx)
            if inspect.isawaitable(result):
                result = await result
            if isinstance(result, ToolCallDecision):
                result.hook_name = reg.name
            return result
        except Exception as e:
            logger.exception(f"Hook '{reg.name}' ({reg.event.value}) raised: {e}")
            ctx.turn_state["hook_errors"] = ctx.turn_state.get("hook_errors", 0) + 1
            return None

    async def run_pre_tool(self, ctx: HookContext) -> ToolCallDecision:
        """Run PRE_TOOL hooks and collapse them into a single decision.

        - `modify` updates `ctx.args` in place and dispatch continues, so later
          hooks validate the corrected arguments.
        - `deny` stops dispatch immediately and wins outright.
        """
        final = ToolCallDecision.allow()
        notes: List[str] = []

        for reg in self._matching(HookEvent.PRE_TOOL, ctx.tool_name):
            decision = await self._call(reg, ctx)
            if decision is None or decision.action == "allow":
                continue

            if decision.action == "deny":
                logger.info(
                    f"Hook '{reg.name}' DENIED {ctx.tool_name}: {decision.reason}"
                )
                return decision

            if decision.action == "modify":
                if decision.args is not None:
                    ctx.args = decision.args
                if decision.reason:
                    notes.append(f"{reg.name}: {decision.reason}")
                logger.info(f"Hook '{reg.name}' MODIFIED args for {ctx.tool_name}")
                final = ToolCallDecision(
                    action="modify",
                    args=ctx.args,
                    reason="; ".join(notes) or None,
                    hook_name=reg.name,
                )

        return final

    async def run_post_tool(self, ctx: HookContext) -> None:
        for reg in self._matching(HookEvent.POST_TOOL, ctx.tool_name):
            await self._call(reg, ctx)

    async def run_tool_error(self, ctx: HookContext) -> None:
        for reg in self._matching(HookEvent.TOOL_ERROR, ctx.tool_name):
            await self._call(reg, ctx)

    async def run_no_tool_calls(self, ctx: HookContext) -> Optional[Dict[str, Any]]:
        """Run NO_TOOL_CALLS hooks; return a continuation request if one was made."""
        for reg in self._matching(HookEvent.NO_TOOL_CALLS, ctx.tool_name):
            await self._call(reg, ctx)
        return ctx.turn_state.get("continuation")

    async def run_turn_start(self, ctx: HookContext) -> List[str]:
        for reg in self._matching(HookEvent.TURN_START, None):
            await self._call(reg, ctx)
        return ctx.context_additions

    async def run_turn_end(self, ctx: HookContext) -> None:
        for reg in self._matching(HookEvent.TURN_END, None):
            await self._call(reg, ctx)


# Process-wide registry. Builtin hooks register themselves on import via
# load_builtin_hooks(); tests can build their own HookRegistry instead.
registry = HookRegistry()
hook = registry.hook

_builtins_loaded = False


def load_builtin_hooks() -> HookRegistry:
    """Import the builtin hook modules so their decorators run.

    Idempotent: importing twice would otherwise double-register every hook.
    """
    global _builtins_loaded
    if _builtins_loaded:
        return registry

    from .builtin import (  # noqa: F401
        audit,
        context_blocks,
        guards,
        intent,
        normalize,
        side_effects,
    )

    _builtins_loaded = True
    logger.info(
        "Builtin hooks loaded: "
        + ", ".join(
            f"{e.value}={len(registry.registered(e))}" for e in HookEvent
        )
    )
    return registry


def build_context(
    event: HookEvent,
    *,
    chat_id: int,
    network_id: int,
    turn_state: Dict[str, Any],
    **kwargs: Any,
) -> HookContext:
    """Convenience constructor used by the engine."""
    return HookContext(
        event=event,
        chat_id=chat_id,
        network_id=network_id,
        turn_state=turn_state,
        **kwargs,
    )
