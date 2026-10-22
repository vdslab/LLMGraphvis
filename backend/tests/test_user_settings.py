"""Password change, token_version sign-out, and per-user model defaults (ADR 0026)."""

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from app.services.llm.engine import resolve_chat_model

CATALOG = [
    {
        "id": "google",
        "label": "Google Gemini",
        "models": [
            {"id": "gemini-3.8-flash", "label": "Gemini 3.8 Flash", "default": True}
        ],
    }
]


async def _register(client, username="alice", password="password-1"):
    response = await client.post(
        "/auth/register", json={"username": username, "password": password}
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def _bearer(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_change_password_signs_out_other_sessions(async_client):
    old_token = await _register(async_client)

    response = await async_client.post(
        "/auth/change-password",
        json={"current_password": "password-1", "new_password": "password-2"},
        headers=_bearer(old_token),
    )
    assert response.status_code == 200
    new_token = response.json()["access_token"]

    async_client.cookies.clear()
    assert (
        await async_client.get("/auth/users/me", headers=_bearer(old_token))
    ).status_code == 401
    assert (
        await async_client.get("/auth/users/me", headers=_bearer(new_token))
    ).status_code == 200

    login = await async_client.post(
        "/auth/token", data={"username": "alice", "password": "password-2"}
    )
    assert login.status_code == 200


@pytest.mark.asyncio
async def test_change_password_requires_current_password(async_client):
    token = await _register(async_client)
    response = await async_client.post(
        "/auth/change-password",
        json={"current_password": "wrong", "new_password": "password-2"},
        headers=_bearer(token),
    )
    assert response.status_code == 400

    too_short = await async_client.post(
        "/auth/change-password",
        json={"current_password": "password-1", "new_password": "short"},
        headers=_bearer(token),
    )
    assert too_short.status_code == 422


@pytest.mark.asyncio
async def test_default_model_setting_is_validated(async_client):
    token = await _register(async_client)
    with patch(
        "app.api.v1.endpoints.users.get_available_provider_catalog",
        return_value=CATALOG,
    ):
        ok = await async_client.patch(
            "/users/me/settings",
            json={"default_provider": "google", "default_model": "gemini-3.8-flash"},
            headers=_bearer(token),
        )
        bad = await async_client.patch(
            "/users/me/settings",
            json={"default_provider": "google", "default_model": "nope"},
            headers=_bearer(token),
        )
        half = await async_client.patch(
            "/users/me/settings",
            json={"default_provider": "google"},
            headers=_bearer(token),
        )
    assert ok.status_code == 200
    assert ok.json()["default_model"] == "gemini-3.8-flash"
    assert bad.status_code == 422
    assert half.status_code == 422

    settings = await async_client.get("/users/me/settings", headers=_bearer(token))
    assert settings.json()["default_provider"] == "google"

    usage = await async_client.get("/users/me/usage", headers=_bearer(token))
    assert usage.status_code == 200
    assert usage.json()["totals"]["task_count"] == 0


def test_chat_pin_beats_user_default():
    user = SimpleNamespace(
        default_provider="anthropic", default_model="claude-haiku-4-5"
    )
    pinned = SimpleNamespace(provider="google", model="gemini-2.5-pro", user=user)
    unpinned = SimpleNamespace(provider=None, model=None, user=user)
    bare = SimpleNamespace(
        provider=None,
        model=None,
        user=SimpleNamespace(default_provider=None, default_model=None),
    )

    assert resolve_chat_model(pinned) == ("google", "gemini-2.5-pro")
    assert resolve_chat_model(unpinned) == ("anthropic", "claude-haiku-4-5")
    assert resolve_chat_model(bare) == (None, None)
