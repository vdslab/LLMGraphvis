"""GET /chat/{id}: what the graph view receives when it opens a chat."""

import pytest

from app.api.v1.endpoints import chat as chat_endpoint
from app.api.v1.endpoints.auth import get_current_user
from app.main import app
from common import models


def _create_chat(db, with_node: bool):
    user = models.User(username="get-chat-user", hashed_password="not-used")
    network = models.Network(name="Fresh Network")
    db.add_all([user, network])
    db.flush()
    if with_node:
        db.add(models.Node(network_id=network.id, node_id="n0", label="n0"))
    chat = models.Chat(name="Fresh", user_id=user.id, network_id=network.id)
    db.add(chat)
    db.commit()
    db.refresh(chat)
    app.dependency_overrides[get_current_user] = lambda: user
    return chat


@pytest.fixture
def tool_calls(monkeypatch):
    calls = []

    async def execute_tool(name, arguments, session=None):
        calls.append((name, arguments))
        return {"nodes": [], "links": []}

    monkeypatch.setattr(chat_endpoint.mcp_client, "execute_tool", execute_tool)
    return calls


@pytest.mark.asyncio
async def test_chat_before_upload_has_no_network_and_asks_nothing(
    async_client, db, tool_calls
):
    chat = _create_chat(db, with_node=False)

    response = await async_client.get(f"/chat/{chat.id}")

    assert response.status_code == 200
    assert response.json()["network"] is None
    assert tool_calls == []


@pytest.mark.asyncio
async def test_chat_with_data_but_no_saved_state_is_generated(
    async_client, db, tool_calls
):
    chat = _create_chat(db, with_node=True)

    response = await async_client.get(f"/chat/{chat.id}")

    assert response.status_code == 200
    assert response.json()["network"] == {"nodes": [], "links": []}
    assert tool_calls == [("visualization_generate", {"network_id": chat.network_id})]
