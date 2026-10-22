"""Tests for hook registration and dispatch semantics."""

import pytest
from app.services.llm.hooks.registry import HookRegistry
from app.services.llm.hooks.types import (
    HookContext,
    HookEvent,
    ToolCallDecision,
    new_turn_state,
)


def make_ctx(event=HookEvent.PRE_TOOL, tool_name="layout_spring", args=None, **kw):
    return HookContext(
        event=event,
        chat_id=1,
        network_id=7,
        turn_state=kw.pop("turn_state", new_turn_state(10)),
        tool_name=tool_name,
        args=args if args is not None else {},
        **kw,
    )


@pytest.fixture
def reg():
    return HookRegistry()


class TestRegistration:
    def test_decorator_registers(self, reg):
        @reg.hook(HookEvent.PRE_TOOL)
        def my_hook(ctx):
            return None

        assert reg.registered(HookEvent.PRE_TOOL) == ["my_hook"]

    def test_explicit_name_overrides_function_name(self, reg):
        @reg.hook(HookEvent.PRE_TOOL, name="custom")
        def my_hook(ctx):
            return None

        assert reg.registered(HookEvent.PRE_TOOL) == ["custom"]

    def test_clear_removes_all(self, reg):
        reg.register(
            HookEvent.PRE_TOOL,
            lambda ctx: None,
            name="a",
        )
        reg.clear()
        assert reg.registered(HookEvent.PRE_TOOL) == []


class TestToolPatternMatching:
    @pytest.mark.asyncio
    async def test_pattern_selects_matching_tools(self, reg):
        seen = []

        @reg.hook(HookEvent.POST_TOOL, tools="analysis_*")
        def only_analysis(ctx):
            seen.append(ctx.tool_name)

        await reg.run_post_tool(make_ctx(HookEvent.POST_TOOL, "analysis_pagerank"))
        await reg.run_post_tool(make_ctx(HookEvent.POST_TOOL, "layout_spring"))
        assert seen == ["analysis_pagerank"]

    @pytest.mark.asyncio
    async def test_star_matches_everything(self, reg):
        seen = []
        reg.register(
            HookEvent.POST_TOOL,
            lambda ctx: seen.append(ctx.tool_name),
            tools="*",
        )
        await reg.run_post_tool(make_ctx(HookEvent.POST_TOOL, "anything_at_all"))
        assert seen == ["anything_at_all"]


class TestPriorityOrdering:
    @pytest.mark.asyncio
    async def test_runs_in_ascending_priority(self, reg):
        order = []
        reg.register(
            HookEvent.PRE_TOOL,
            lambda c: order.append("late"), priority=90,
            name="late",
        )
        reg.register(
            HookEvent.PRE_TOOL,
            lambda c: order.append("early"), priority=10,
            name="early",
        )
        reg.register(
            HookEvent.PRE_TOOL,
            lambda c: order.append("mid"), priority=50,
            name="mid",
        )
        await reg.run_pre_tool(make_ctx())
        assert order == ["early", "mid", "late"]


class TestPreToolDecisions:
    @pytest.mark.asyncio
    async def test_no_hooks_allows(self, reg):
        assert (await reg.run_pre_tool(make_ctx())).action == "allow"

    @pytest.mark.asyncio
    async def test_returning_none_allows(self, reg):
        reg.register(
            HookEvent.PRE_TOOL,
            lambda c: None,
            name="noop",
        )
        assert (await reg.run_pre_tool(make_ctx())).action == "allow"

    @pytest.mark.asyncio
    async def test_deny_wins_and_carries_hook_name(self, reg):
        reg.register(
            HookEvent.PRE_TOOL,
            lambda c: ToolCallDecision.deny("nope"),
            name="blocker",
        )
        decision = await reg.run_pre_tool(make_ctx())
        assert decision.action == "deny"
        assert decision.reason == "nope"
        assert decision.hook_name == "blocker"

    @pytest.mark.asyncio
    async def test_deny_short_circuits_later_hooks(self, reg):
        ran = []
        reg.register(
            HookEvent.PRE_TOOL,
            lambda c: ToolCallDecision.deny("stop"),
            priority=10,
            name="blocker",
        )
        reg.register(
            HookEvent.PRE_TOOL,
            lambda c: ran.append("after"), priority=20,
            name="after",
        )
        await reg.run_pre_tool(make_ctx())
        assert ran == []

    @pytest.mark.asyncio
    async def test_modify_replaces_args(self, reg):
        reg.register(
            HookEvent.PRE_TOOL,
            lambda c: ToolCallDecision.modify({**c.args, "k": 1.5}, reason="set k"),
            name="setter",
        )
        ctx = make_ctx(args={"network_id": 7})
        decision = await reg.run_pre_tool(ctx)
        assert decision.action == "modify"
        assert decision.args == {"network_id": 7, "k": 1.5}
        assert "set k" in decision.reason

    @pytest.mark.asyncio
    async def test_later_hooks_see_modified_args(self, reg):
        """Normalizers run before guards precisely so guards validate corrected args."""
        observed = {}
        reg.register(
            HookEvent.PRE_TOOL,
            lambda c: ToolCallDecision.modify({**c.args, "attribute": "club"}),
            priority=10,
            name="normalizer",
        )
        reg.register(
            HookEvent.PRE_TOOL,
            lambda c: observed.update(c.args) or None,
            priority=50,
            name="guard",
        )
        await reg.run_pre_tool(make_ctx(args={"attribute": "Club"}))
        assert observed["attribute"] == "club"

    @pytest.mark.asyncio
    async def test_two_modifications_compose(self, reg):
        reg.register(
            HookEvent.PRE_TOOL,
            lambda c: ToolCallDecision.modify({**c.args, "a": 1}, reason="a"),
            priority=10,
            name="one",
        )
        reg.register(
            HookEvent.PRE_TOOL,
            lambda c: ToolCallDecision.modify({**c.args, "b": 2}, reason="b"),
            priority=20,
            name="two",
        )
        decision = await reg.run_pre_tool(make_ctx())
        assert decision.args == {"a": 1, "b": 2}
        assert "a" in decision.reason and "b" in decision.reason

    @pytest.mark.asyncio
    async def test_modify_then_deny_denies(self, reg):
        reg.register(
            HookEvent.PRE_TOOL,
            lambda c: ToolCallDecision.modify({**c.args, "a": 1}),
            priority=10,
            name="mod",
        )
        reg.register(
            HookEvent.PRE_TOOL,
            lambda c: ToolCallDecision.deny("bad"),
            priority=20,
            name="den",
        )
        assert (await reg.run_pre_tool(make_ctx())).action == "deny"


class TestAsyncAndErrorHandling:
    @pytest.mark.asyncio
    async def test_async_hooks_are_awaited(self, reg):
        async def async_hook(ctx):
            return ToolCallDecision.deny("async denial")

        reg.register(HookEvent.PRE_TOOL, async_hook, name="async_hook")
        decision = await reg.run_pre_tool(make_ctx())
        assert decision.action == "deny"

    @pytest.mark.asyncio
    async def test_a_raising_hook_fails_open_and_is_counted(self, reg):
        """A buggy guard must not take down every tool call, but must be visible."""
        def broken(ctx):
            raise RuntimeError("boom")

        ran_after = []
        reg.register(HookEvent.PRE_TOOL, broken, priority=10, name="broken")
        reg.register(
            HookEvent.PRE_TOOL,
            lambda c: ran_after.append(1), priority=20,
            name="after",
        )

        ctx = make_ctx()
        decision = await reg.run_pre_tool(ctx)
        assert decision.action == "allow"
        assert ran_after == [1]
        assert ctx.turn_state["hook_errors"] == 1


class TestOtherEvents:
    @pytest.mark.asyncio
    async def test_turn_start_collects_context_additions(self, reg):
        reg.register(
            HookEvent.TURN_START,
            lambda c: c.add_context("block A"), priority=10,
            name="a",
        )
        reg.register(
            HookEvent.TURN_START,
            lambda c: c.add_context("block B"), priority=20,
            name="b",
        )
        ctx = make_ctx(HookEvent.TURN_START, tool_name=None)
        assert await reg.run_turn_start(ctx) == ["block A", "block B"]

    @pytest.mark.asyncio
    async def test_add_context_ignores_empty(self, reg):
        reg.register(
            HookEvent.TURN_START,
            lambda c: c.add_context(""),
            name="empty",
        )
        ctx = make_ctx(HookEvent.TURN_START, tool_name=None)
        assert await reg.run_turn_start(ctx) == []

    @pytest.mark.asyncio
    async def test_tool_error_can_abort_the_turn(self, reg):
        reg.register(
            HookEvent.TOOL_ERROR,
            lambda c: c.abort_turn("too many failures"),
            name="aborter",
        )
        ctx = make_ctx(HookEvent.TOOL_ERROR, error="boom")
        await reg.run_tool_error(ctx)
        assert ctx.turn_state["should_abort"] is True
        assert ctx.turn_state["abort_reason"] == "too many failures"

    @pytest.mark.asyncio
    async def test_no_tool_calls_returns_continuation(self, reg):
        reg.register(
            HookEvent.NO_TOOL_CALLS,
            lambda c: c.request_continuation("do it", model_text="I will"),
            name="nudge",
        )
        ctx = make_ctx(HookEvent.NO_TOOL_CALLS, tool_name=None)
        result = await reg.run_no_tool_calls(ctx)
        assert result["prompt"] == "do it"
        assert result["model_text"] == "I will"

    @pytest.mark.asyncio
    async def test_first_continuation_request_wins(self, reg):
        reg.register(
            HookEvent.NO_TOOL_CALLS,
            lambda c: c.request_continuation("first"),
            priority=10,
            name="one",
        )
        reg.register(
            HookEvent.NO_TOOL_CALLS,
            lambda c: c.request_continuation("second"),
            priority=20,
            name="two",
        )
        ctx = make_ctx(HookEvent.NO_TOOL_CALLS, tool_name=None)
        assert (await reg.run_no_tool_calls(ctx))["prompt"] == "first"

    @pytest.mark.asyncio
    async def test_no_continuation_returns_none(self, reg):
        ctx = make_ctx(HookEvent.NO_TOOL_CALLS, tool_name=None)
        assert await reg.run_no_tool_calls(ctx) is None


class TestBuiltinsLoadOnce:
    """Note: `app.services.llm.hooks.registry` is the HookRegistry *instance*
    exported by the package __init__, which shadows the same-named submodule —
    so these go through the package-level names."""

    def test_load_builtin_hooks_is_idempotent(self):
        from app.services.llm.hooks import load_builtin_hooks

        first = load_builtin_hooks()
        counts = {e: len(first.registered(e)) for e in HookEvent}
        load_builtin_hooks()
        assert {e: len(first.registered(e)) for e in HookEvent} == counts

    def test_expected_builtin_hooks_are_present(self):
        from app.services.llm.hooks import load_builtin_hooks

        r = load_builtin_hooks()
        assert "normalize_network_id" in r.registered(HookEvent.PRE_TOOL)
        assert "guard_attribute_exists" in r.registered(HookEvent.PRE_TOOL)
        assert "guard_expensive_computation" in r.registered(HookEvent.PRE_TOOL)
        assert "on_new_network_id" in r.registered(HookEvent.POST_TOOL)
        assert "inject_skill_index" in r.registered(HookEvent.TURN_START)

    def test_normalizers_run_before_guards(self):
        """Ordering is load-bearing: guards must see corrected arguments."""
        from app.services.llm.hooks import load_builtin_hooks

        r = load_builtin_hooks()
        names = r.registered(HookEvent.PRE_TOOL)
        assert names.index("normalize_attribute_case") < names.index(
            "guard_attribute_exists"
        )
