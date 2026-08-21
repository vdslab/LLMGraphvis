import xml.etree.ElementTree as ET
from unittest.mock import AsyncMock, patch

import pytest

from app.api.v1.endpoints.auth import get_current_user
from app.main import app
from app.services import sample_networks
from common import models


GRAPHML_NS = {"g": "http://graphml.graphdrawing.org/xmlns"}


def _create_chat(db):
    user = models.User(username="sample-user", hashed_password="not-used")
    network = models.Network(name="New Chat Network")
    db.add_all([user, network])
    db.flush()
    chat = models.Chat(name="New Chat", user_id=user.id, network_id=network.id)
    db.add(chat)
    db.commit()
    db.refresh(chat)
    app.dependency_overrides[get_current_user] = lambda: user
    return user, chat


def test_bundled_graphml_matches_catalog_metadata():
    for sample in sample_networks.SAMPLE_NETWORKS:
        graphml = sample_networks.load_graphml(sample)
        root = ET.fromstring(graphml)

        assert len(root.findall(".//g:node", GRAPHML_NS)) == sample.node_count
        assert len(root.findall(".//g:edge", GRAPHML_NS)) == sample.edge_count


@pytest.mark.asyncio
async def test_list_samples_returns_public_catalog(async_client, db):
    _create_chat(db)

    response = await async_client.get("/chat/samples")

    assert response.status_code == 200
    assert [sample["id"] for sample in response.json()] == [
        "karate-club",
        "les-miserables",
        "florentine-families",
        "davis-southern-women",
    ]
    assert all("asset_filename" not in sample for sample in response.json())


@pytest.mark.asyncio
async def test_select_sample_uses_the_upload_pipeline(async_client, db):
    _, chat = _create_chat(db)

    with patch(
        "app.services.chat_service.handle_upload_background",
        new_callable=AsyncMock,
    ) as handle_upload:
        response = await async_client.post(f"/chat/{chat.id}/samples/karate-club")

    assert response.status_code == 202
    graphml = sample_networks.load_graphml(
        sample_networks.get_sample("karate-club")
    )
    handle_upload.assert_awaited_once_with(
        chat.id,
        chat.network_id,
        graphml,
        "Zachary's Karate Club.graphml",
    )


@pytest.mark.asyncio
async def test_select_unknown_sample_returns_not_found(async_client, db):
    _, chat = _create_chat(db)

    response = await async_client.post(f"/chat/{chat.id}/samples/not-a-sample")

    assert response.status_code == 404
    assert response.json()["detail"] == "Sample network not found"
