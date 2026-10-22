"""The turn trace (ADR 0032): observation that never changes a turn."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.services.llm import trace
from app.services.llm.engine import GraphVisAgent
from app.services.llm.hooks import (
    HookEvent,
    ToolCallDecision,
    build_context,
    new_turn_state,
    registry,
)
from app.services.llm.providers.types import FunctionCallData


@pytest.fixture
def trace_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_TRACE", "1")
    monkeypatch.setenv("AGENT_TRACE_DIR", str(tmp_path))
    return tmp_path


def _events(directory):
    lines = []
    for path in sorted(directory.glob("*.jsonl")):
        lines.extend(json.loads(line) for line in path.read_text().splitlines())
    return lines


def test_events_share_a_turn_id_and_are_ordered(trace_dir):
    turn = trace.TurnTrace(chat_id=3, network_id=7)
    turn.emit("turn_start", user_text="hi")
    turn.emit("turn_end", tools_run=0)

    events = _events(trace_dir)
    assert [e["event"] for e in events] == ["turn_start", "turn_end"]
    assert [e["seq"] for e in events] == [1, 2]
    assert {e["turn_id"] for e in events} == {turn.turn_id}
    assert events[0]["chat_id"] == 3 and events[0]["network_id"] == 7


def test_disabled_trace_writes_nothing(trace_dir, monkeypatch):
    monkeypatch.setenv("AGENT_TRACE", "0")
    trace.TurnTrace().emit("turn_start")
    assert _events(trace_dir) == []


def test_unwritable_directory_does_not_raise(tmp_path, monkeypatch):
    blocker = tmp_path / "file"
    blocker.write_text("")
    monkeypatch.setenv("AGENT_TRACE", "1")
    monkeypatch.setenv("AGENT_TRACE_DIR", str(blocker / "sub"))
    turn = trace.TurnTrace()
    turn.emit("turn_start")
    assert turn.active is False


def test_large_values_are_clipped():
    assert trace.clip_value({"a": 1}) == {"a": 1}
    clipped = trace.clip_value({"items": list(range(5000))}, limit=100)
    assert isinstance(clipped, str) and "chars)" in clipped
    assert trace.clip("x" * 10, limit=4).startswith("xxxx…")


@pytest.mark.asyncio
async def test_a_denied_call_is_traced_with_the_deciding_hook(trace_dir):
    with patch("app.services.llm.engine._create_provider") as factory:
        factory.return_value = MagicMock(model_name="test-model")
        agent = GraphVisAgent(db=None)
    agent.trace = trace.TurnTrace(chat_id=1, network_id=1)
    agent._run_tool = AsyncMock()

    name = "test_trace_denier"
    registry.register(
        HookEvent.PRE_TOOL,
        lambda ctx: ToolCallDecision.deny("nope"),
        priority=1,
        name=name,
    )
    state = new_turn_state(10)
    state["network_id"] = 1
    try:
        with patch(
            "app.services.llm.hooks.builtin.guards._owns_network", return_value=True
        ):
            await agent._execute_tools_and_update_history(
                [FunctionCallData(name="test_tool", args={"x": 1}, call_id="c1")],
                "", "", [], AsyncMock(), chat_id=1, turn_state=state, session=None,
            )
    finally:
        registry._hooks[HookEvent.PRE_TOOL] = [
            r for r in registry._hooks[HookEvent.PRE_TOOL] if r.name != name
        ]

    (event,) = [e for e in _events(trace_dir) if e["event"] == "tool"]
    assert event["name"] == "test_tool"
    assert event["status"] == "failed"
    assert event["decision"] == "deny"
    assert event["decided_by"] == name
    assert event["reason"] == "nope"
    assert event["args"] == {"x": 1}
    assert "_last_decision" not in state


def test_skill_suggestions_are_recorded_for_the_trace():
    from app.services.llm.hooks.builtin.context_blocks import inject_skill_suggestions

    state = new_turn_state(10)
    ctx = build_context(
        HookEvent.TURN_START,
        chat_id=1,
        network_id=0,
        turn_state=state,
        user_text="ノードをコミュニティで色分けして",
    )
    inject_skill_suggestions(ctx)
    assert "visual-encoding" in state["skills_suggested"]
