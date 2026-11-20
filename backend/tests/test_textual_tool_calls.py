"""Tool calls written as text (`tool_code` / `default_api.`) never reach the user.

Regression for chat 260 (2026-10-20, Gemini 2.5 Flash): after running
set_viewport and reset_style for "全体が見えるように戻して", the model echoed both
calls as `::tool_code` text instead of reporting, and that text became the
stored reply.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.services.llm import markup
from app.services.llm.engine import GraphVisAgent
from app.services.llm.history import build_history
from app.services.llm.hooks.builtin import intent
from app.services.llm.hooks.types import HookContext, HookEvent, new_turn_state
from app.services.llm.providers.types import LLMTextPart, StreamChunk

# The model text of the final iteration, verbatim from the turn trace.
LEAKED = (
    "::tool_code\n"
    "print(default_api.visualization_set_viewport(network_id=878, target='all'))\n"
    "print(default_api.visualization_reset_style(network_id=878, "
    "targets=['highlight', 'node_label']))"
)


class TestSplitTextualToolCalls:
    def test_removes_the_leaked_block_and_names_its_tools(self):
        text, names = markup.split_textual_tool_calls(LEAKED)

        assert text == ""
        assert names == ["visualization_set_viewport", "visualization_reset_style"]

    def test_hyphenated_directive_and_surrounding_prose(self):
        text, names = markup.split_textual_tool_calls(
            "経路を強調しました。\n\n::tool-code\n"
            'print(default_api.visualization_highlight(node_ids=["Cosette"]))\n'
            "\n以上です。"
        )

        assert names == ["visualization_highlight"]
        assert "default_api" not in text
        assert "経路を強調しました。" in text and "以上です。" in text

    def test_fenced_block(self):
        text, names = markup.split_textual_tool_calls(
            "Done.\n\n```tool_code\nprint(default_api.layout_spring(seed=1))\n```\nAfter."
        )

        assert names == ["layout_spring"]
        assert text == "Done.\n\nAfter."

    def test_bare_call_line(self):
        text, names = markup.split_textual_tool_calls(
            "Shown.\ndefault_api.visualization_set_viewport(target='all')\n"
        )

        assert names == ["visualization_set_viewport"]
        assert text == "Shown.\n"

    @pytest.mark.parametrize(
        "prose",
        [
            "The tool_code format is not used here.",
            "default_api is only a word in this sentence.",
            "`visualization_set_viewport(target='all')` shows everything.",
        ],
    )
    def test_prose_is_left_alone(self, prose):
        assert markup.split_textual_tool_calls(prose) == (prose, [])

    def test_sanitize_model_text_strips_it(self):
        assert "default_api" not in markup.sanitize_model_text("OK.\n\n" + LEAKED)


def test_history_text_drops_markers_and_leaked_calls():
    stored = (
        '\n\n::tool-execution{index="0"}\n\n\n\n::tool-execution{index="1"}\n\n'
        + LEAKED
    )
    assert markup.history_text(stored) == ""
    assert (
        markup.history_text('全体を表示しました。\n\n::tool-execution{index="0"}\n\n')
        == "全体を表示しました。"
    )


def _message(role, content):
    return SimpleNamespace(
        role=role, content=content, tool_executions=[], meta_data=None
    )


def test_build_history_does_not_replay_markers_or_leaked_text():
    messages = [
        _message("user", "全体が見えるように戻して"),
        _message("model", '::tool-execution{index="0"}\n\n' + LEAKED),
        _message("model", '表示しました。\n\n::tool-execution{index="0"}'),
    ]
    db = MagicMock()
    query = db.query.return_value.filter.return_value.order_by.return_value
    query.all.return_value = messages

    history = build_history(260, "How many nodes are there?", db)

    texts = [p.text for m in history for p in m.parts if isinstance(p, LLMTextPart)]
    assert texts == [
        "全体が見えるように戻して",
        "表示しました。",
        "How many nodes are there?",
    ]


class TestNudgeTextualToolCalls:
    def _ctx(self, names, *, granted=0, text=""):
        state = new_turn_state(10)
        state["textual_tool_calls"] = names
        state["continuations_granted"] = granted
        return HookContext(
            event=HookEvent.NO_TOOL_CALLS,
            chat_id=260,
            network_id=878,
            turn_state=state,
            assistant_text=text,
        )

    def test_requests_a_continuation_naming_the_tools(self):
        c = self._ctx(["visualization_set_viewport", "visualization_set_viewport"])

        intent.nudge_textual_tool_calls(c)

        prompt = c.turn_state["continuation"]["prompt"]
        assert "wrote tool calls as text (visualization_set_viewport)" in prompt
        assert "default_api" not in c.turn_state["continuation"]["model_text"]

    def test_silent_without_textual_calls(self):
        c = self._ctx([])
        intent.nudge_textual_tool_calls(c)
        assert c.turn_state["continuation"] is None

    def test_respects_the_continuation_budget(self):
        c = self._ctx(["f"], granted=intent.MAX_CONTINUATIONS)
        intent.nudge_textual_tool_calls(c)
        assert c.turn_state["continuation"] is None


async def _async_iter(items):
    for item in items:
        yield item


@pytest.mark.asyncio
async def test_loop_strips_the_leak_and_asks_for_a_real_reply():
    with patch("app.services.llm.engine._create_provider") as factory:
        factory.return_value = MagicMock(model_name="gemini-2.5-flash")
        agent = GraphVisAgent(db=None)
    reply = [StreamChunk(text="全体を表示しました。")]
    agent.provider.generate = MagicMock(side_effect=lambda *a, **k: _async_iter(reply))
    history = []
    turn_state = new_turn_state(10)
    turn_state["network_id"] = 878
    turn_state["tools_run"] = 2

    final_text, _log, _usage = await agent._execute_tool_loop(
        initial_stream=_async_iter([StreamChunk(text=LEAKED)]),
        history=history,
        all_tools=[],
        queue=AsyncMock(),
        chat_id=260,
        network_id=878,
        session=None,
        turn_state=turn_state,
    )

    assert final_text == "全体を表示しました。"
    assert turn_state["continuation"] is None
    assert turn_state["continuations_granted"] == 1
    # The leaked text is not replayed to the model either.
    assert all("default_api" not in p.text for m in history for p in m.parts)
    assert "wrote tool calls as text" in history[-1].parts[0].text
