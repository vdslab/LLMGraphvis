"""A turn always ends with words, and preparation does not spend its budget.

Chat 280 ran out of rounds on skill_load / tool_search and ended with a row of
tool cards and no reply.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.llm import engine
from app.services.llm.engine import GraphVisAgent
from app.services.llm.providers.types import FunctionCallData, StreamChunk
from common import models


@pytest.fixture
def chat(db):
    user = models.User(username="budget-test", hashed_password="unused")
    network = models.Network(name="test")
    db.add_all([user, network])
    db.flush()
    chat = models.Chat(name="test", user_id=user.id, network_id=network.id)
    db.add(chat)
    db.commit()
    return chat


def _stream(*chunks):
    async def gen():
        for chunk in chunks:
            yield chunk

    return gen()


def _calls(name, n, start=0):
    return [
        StreamChunk(
            text="",
            function_calls=[FunctionCallData(name=name, args={"query": f"q{i}"})],
        )
        for i in range(start, start + n)
    ]


def _agent(db, responses):
    with patch("app.services.llm.engine._create_provider", return_value=MagicMock()):
        agent = GraphVisAgent(db=db)
    agent.provider.generate = MagicMock(side_effect=[_stream(r) for r in responses])
    return agent


@pytest.mark.asyncio
async def test_exhausted_budget_ends_with_a_closing_report(db, chat):
    with patch.object(engine, "AGENT_MAX_ITERATIONS", 2):
        work = [
            StreamChunk(
                text="",
                function_calls=[
                    FunctionCallData(name="analysis_pagerank", args={"alpha": a})
                ],
            )
            for a in (0.8, 0.85)
        ]
        closing = StreamChunk(text="PageRank を計算しました。次は色分けができます。")
        agent = _agent(db, work[1:] + [closing])
        with patch(
            "app.services.llm.mcp_client.execute_tool",
            new_callable=AsyncMock,
            return_value={"content": "ok"},
        ):
            text, _, _ = await agent._execute_tool_loop(
                _stream(work[0]),
                [],
                [],
                AsyncMock(),
                chat.id,
                chat.network_id,
                None,
                {"network_id": chat.network_id, **engine.hooks.new_turn_state(2)},
            )
    assert "PageRank を計算しました" in text
    prompt = agent.provider.generate.call_args_list[-1].args[0][-1].parts[0].text
    assert prompt == engine.BUDGET_EXHAUSTED_PROMPT


def test_preparation_rounds_do_not_count():
    assert engine._is_preparation_step(
        {"tool_calls": [{"name": "skill_load"}, {"name": "tool_search"}]}
    )
    assert engine._is_preparation_step(
        {"tool_calls": [{"name": "layout_spring", "status": "deferred"}]}
    )
    assert not engine._is_preparation_step(
        {"tool_calls": [{"name": "skill_load"}, {"name": "analysis_pagerank"}]}
    )
    assert not engine._is_preparation_step({"tool_calls": []})
