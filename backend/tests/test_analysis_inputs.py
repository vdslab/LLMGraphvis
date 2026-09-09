from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import BackgroundTasks, HTTPException

from app import schemas
from app.api.v1.endpoints.chat import get_analysis_input, process_message
from app.services.llm.engine import GraphVisAgent
from app.services.llm.inputs import InputForm, accept_answer, present_question
from app.services.llm.providers.types import FunctionCallData, StreamChunk
from common import models

FORM = {
    "question": "どの条件で分析しますか？",
    "fields": [
        {
            "id": "method",
            "label": "分析目的",
            "kind": "select",
            "options": ["中心性", "経路"],
        },
        {
            "id": "iterations",
            "label": "反復回数",
            "kind": "slider",
            "minimum": 10,
            "maximum": 100,
            "step": 10,
        },
    ],
}


@pytest.fixture
def chat(db):
    user = models.User(username="input-test", hashed_password="unused")
    network = models.Network(name="test")
    db.add_all([user, network])
    db.flush()
    chat = models.Chat(name="test", user_id=user.id, network_id=network.id)
    db.add(chat)
    db.commit()
    return chat


def test_form_validates_bounds_options_and_field_ids():
    form = InputForm.model_validate(FORM)
    assert "反復回数: 20" in form.answer_text({"method": "経路", "iterations": 20})
    for values in [
        {"method": "invalid", "iterations": 20},
        {"method": "経路", "iterations": 21},
        {"method": "経路", "iterations": True},
        {"method": "経路", "iterations": float("inf")},
        {"method": "経路"},
    ]:
        with pytest.raises(ValueError):
            form.answer_text(values)


def test_question_survives_reload_and_supersedes_previous(db, chat):
    state = {}
    first = present_question(chat.id, db, FORM, state)["input_request"]
    assert state["input_request"]["id"] == first["id"]
    second = present_question(chat.id, db, FORM, {})["input_request"]
    db.expire_all()
    assert db.get(models.AnalysisInput, first["id"]).status == "superseded"
    assert db.get(models.AnalysisInput, second["id"]).status == "pending"
    with pytest.raises(ValueError, match="no longer active"):
        accept_answer(chat, db, first["id"], None, "経路で")


@pytest.mark.asyncio
async def test_answer_submission_is_idempotent_and_bound_to_chat(db, chat):
    request = present_question(chat.id, db, FORM, {})["input_request"]
    user = db.get(models.User, chat.user_id)
    payload = schemas.ChatProcessRequest(
        message={"content": "ignored"},
        input_request_id=request["id"],
        input_values={"method": "経路", "iterations": 20},
    )
    tasks = BackgroundTasks()
    assert await process_message(chat.id, payload, tasks, user, db) == {
        "status": "accepted"
    }
    assert len(tasks.tasks) == 1
    retry_tasks = BackgroundTasks()
    assert await process_message(chat.id, payload, retry_tasks, user, db) == {
        "status": "already_accepted"
    }
    assert not retry_tasks.tasks
    assert db.query(models.ChatMessage).count() == 1
    assert "分析目的: 経路" in db.query(models.ChatMessage).one().content
    assert get_analysis_input(chat.id, request["id"], user, db)["status"] == "answered"
    other_user = models.User(username="other", hashed_password="unused")
    db.add(other_user)
    db.commit()
    with pytest.raises(HTTPException) as error:
        get_analysis_input(chat.id, request["id"], other_user, db)
    assert error.value.status_code == 404


def test_network_change_expires_question(db, chat):
    request = present_question(chat.id, db, FORM, {})["input_request"]
    network = models.Network(name="other")
    db.add(network)
    db.flush()
    chat.network_id = network.id
    db.commit()
    with pytest.raises(ValueError, match="no longer active"):
        accept_answer(chat, db, request["id"], None, "yes")


@pytest.mark.asyncio
async def test_plain_text_reply_resolves_pending_question(db, chat):
    request = present_question(chat.id, db, FORM, {})["input_request"]
    user = db.get(models.User, chat.user_id)
    payload = schemas.ChatProcessRequest(message={"content": "まず経路だけ調べて"})
    await process_message(chat.id, payload, BackgroundTasks(), user, db)
    assert db.get(models.AnalysisInput, request["id"]).answer == {
        "free_text": "まず経路だけ調べて"
    }


@pytest.mark.asyncio
async def test_question_blocks_entire_tool_batch_and_ends_generation(db, chat):
    with patch("app.services.llm.engine._create_provider", return_value=MagicMock()):
        agent = GraphVisAgent(db=db)
    state = {"network_id": chat.network_id}
    queue = AsyncMock()
    calls = [
        FunctionCallData(name="analysis_pagerank", args={}),
        FunctionCallData(name="ask_user", args=FORM),
        FunctionCallData(name="visualization_generate", args={}),
    ]

    async def stream():
        yield StreamChunk(function_calls=calls)

    with patch(
        "app.services.llm.mcp_client.execute_tool", new_callable=AsyncMock
    ) as remote:
        text, log, _ = await agent._execute_tool_loop(
            stream(), [], [], queue, chat.id, chat.network_id, None, state
        )
    remote.assert_not_called()
    agent.provider.generate.assert_not_called()
    assert FORM["question"] in text
    assert [call["name"] for call in log[0]["tool_calls"]] == ["ask_user"]
    assert db.query(models.AnalysisInput).count() == 1
