import httpx
import pytest
from app.api.v1.endpoints.auth import get_current_user
from app.main import app
from app.services import network_service

from common import models

GRAPHML = '<?xml version="1.0"?><graphml><graph edgedefault="undirected"/></graphml>'


def _create_chat(db):
    user = models.User(username="export-user", hashed_password="not-used")
    network = models.Network(name="Export Network")
    db.add_all([user, network])
    db.flush()
    chat = models.Chat(name="Export", user_id=user.id, network_id=network.id)
    db.add(chat)
    db.commit()
    db.refresh(chat)
    app.dependency_overrides[get_current_user] = lambda: user
    return chat


@pytest.fixture
def networkx_api(monkeypatch):
    """Answer networkx-api requests with the handler a test installs."""
    calls = []
    state = {"handler": None}

    def transport_handler(request):
        calls.append(request)
        return state["handler"](request)

    def client():
        return httpx.AsyncClient(
            base_url="http://networkx-api:8001",
            transport=httpx.MockTransport(transport_handler),
        )

    monkeypatch.setattr(network_service, "_networkx_client", client)

    def install(handler):
        state["handler"] = handler
        return calls

    return install


@pytest.mark.asyncio
async def test_export_returns_graphml_from_networkx_api(async_client, db, networkx_api):
    chat = _create_chat(db)
    calls = networkx_api(lambda request: httpx.Response(200, json={"graphml": GRAPHML}))

    response = await async_client.get(f"/chat/{chat.id}/export")

    assert response.status_code == 200
    assert response.text == GRAPHML
    assert response.headers["content-type"].startswith("application/graphml+xml")
    disposition = response.headers["content-disposition"]
    assert f"network_{chat.network_id}.graphml" in disposition
    assert calls[0].url.path == f"/api/v1/networks/{chat.network_id}/export"


@pytest.mark.asyncio
async def test_export_of_missing_network_is_404(async_client, db, networkx_api):
    chat = _create_chat(db)
    networkx_api(lambda request: httpx.Response(404, json={"detail": "not found"}))

    response = await async_client.get(f"/chat/{chat.id}/export")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_export_failure_upstream_is_502(async_client, db, networkx_api):
    chat = _create_chat(db)
    networkx_api(lambda request: httpx.Response(500, json={"detail": "boom"}))

    response = await async_client.get(f"/chat/{chat.id}/export")

    assert response.status_code == 502
    assert "boom" not in response.text


@pytest.mark.asyncio
async def test_export_unreachable_networkx_api_is_502(async_client, db, networkx_api):
    chat = _create_chat(db)

    def refuse(request):
        raise httpx.ConnectError("connection refused", request=request)

    networkx_api(refuse)

    response = await async_client.get(f"/chat/{chat.id}/export")

    assert response.status_code == 502


@pytest.mark.asyncio
async def test_export_of_another_users_chat_is_404(async_client, db, networkx_api):
    chat = _create_chat(db)
    stranger = models.User(username="stranger", hashed_password="not-used")
    db.add(stranger)
    db.commit()
    app.dependency_overrides[get_current_user] = lambda: stranger
    calls = networkx_api(lambda request: httpx.Response(200, json={"graphml": GRAPHML}))

    response = await async_client.get(f"/chat/{chat.id}/export")

    assert response.status_code == 404
    assert calls == []
