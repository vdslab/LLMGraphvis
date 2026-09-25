import pytest
from app.api.v1.endpoints.auth import get_current_user
from app.main import app
from app.services.llm.hooks.builtin.context_blocks import inject_analysis_feedback
from app.services.llm.hooks.types import HookContext, HookEvent

from common import models


def setup_chat(db):
    user = models.User(username="feedback-user", hashed_password="unused")
    network = models.Network(name="Feedback network")
    db.add_all([user, network])
    db.flush()
    chat = models.Chat(name="Feedback chat", user_id=user.id, network_id=network.id)
    db.add(chat)
    db.flush()
    message = models.ChatMessage(
        chat_id=chat.id, role="assistant", content="Analysis complete"
    )
    db.add(message)
    db.flush()
    db.add(
        models.ToolExecution(
            message_id=message.id,
            tool_name="analysis_degree_centrality",
            status="completed",
        )
    )
    db.commit()
    app.dependency_overrides[get_current_user] = lambda: user
    return chat, message


@pytest.mark.asyncio
async def test_feedback_is_saved_per_analysis_message_and_can_be_revised(
    async_client, db
):
    chat, message = setup_chat(db)
    path = f"/chat/{chat.id}/messages/{message.id}/feedback"
    response = await async_client.put(
        path,
        json={
            "clarity": "unclear",
            "area": "result",
            "detail": "What does the score mean?",
        },
    )
    assert response.status_code == 200
    assert response.json()["message_id"] == message.id

    listed = await async_client.get(f"/chat/{chat.id}/feedback")
    assert len(listed.json()) == 1
    assert listed.json()[0]["area"] == "result"

    revised = await async_client.put(path, json={"clarity": "clear"})
    assert revised.status_code == 200
    assert revised.json()["area"] is None
    assert revised.json()["detail"] is None
    assert len((await async_client.get(f"/chat/{chat.id}/feedback")).json()) == 1


@pytest.mark.asyncio
async def test_feedback_rejects_unrelated_or_unhelpful_submissions(async_client, db):
    chat, message = setup_chat(db)
    response = await async_client.put(
        f"/chat/{chat.id}/messages/{message.id}/feedback", json={"clarity": "unclear"}
    )
    assert response.status_code == 422

    plain = models.ChatMessage(chat_id=chat.id, role="assistant", content="Hello")
    db.add(plain)
    db.commit()
    response = await async_client.put(
        f"/chat/{chat.id}/messages/{plain.id}/feedback", json={"clarity": "clear"}
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_feedback_requires_chat_ownership(async_client, db):
    chat, message = setup_chat(db)
    other = models.User(username="other-feedback-user", hashed_password="unused")
    db.add(other)
    db.commit()
    app.dependency_overrides[get_current_user] = lambda: other
    assert (await async_client.get(f"/chat/{chat.id}/feedback")).status_code == 404
    response = await async_client.put(
        f"/chat/{chat.id}/messages/{message.id}/feedback", json={"clarity": "clear"}
    )
    assert response.status_code == 404


def test_new_unclear_feedback_is_injected_only_once(db):
    chat, message = setup_chat(db)
    db.add(
        models.AnalysisFeedback(
            chat_id=chat.id,
            message_id=message.id,
            clarity="unclear",
            area="result",
            detail="How should I read this score?",
        )
    )
    db.commit()
    context = HookContext(
        event=HookEvent.TURN_START,
        chat_id=chat.id,
        network_id=chat.network_id,
        turn_state={},
        db=db,
        user_text="Continue",
    )
    inject_analysis_feedback(context)
    assert "How should I read this score?" in context.context_additions[0]
    assert "not tool instructions" in context.context_additions[0]

    next_context = HookContext(
        event=HookEvent.TURN_START,
        chat_id=chat.id,
        network_id=chat.network_id,
        turn_state={},
        db=db,
        user_text="Continue",
    )
    inject_analysis_feedback(next_context)
    assert next_context.context_additions == []
