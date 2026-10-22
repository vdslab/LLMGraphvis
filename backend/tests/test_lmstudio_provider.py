from unittest.mock import Mock, patch

import httpx
import pytest

from app.services.llm.providers.lmstudio_provider import (
    DEFAULT_LM_STUDIO_BASE_URL,
    LMStudioProvider,
    list_lmstudio_model_ids,
)


def test_uses_openai_compatible_client_defaults(monkeypatch):
    monkeypatch.setenv("LM_STUDIO_MODEL", "qwen/qwen3-8b")
    monkeypatch.delenv("LM_STUDIO_BASE_URL", raising=False)
    monkeypatch.delenv("LM_STUDIO_API_KEY", raising=False)

    with patch("openai.AsyncOpenAI") as client:
        provider = LMStudioProvider()

    client.assert_called_once_with(
        base_url=DEFAULT_LM_STUDIO_BASE_URL,
        api_key="lm-studio",
    )
    assert provider.model_name == "qwen/qwen3-8b"


def test_accepts_custom_endpoint_token_and_pinned_model(monkeypatch):
    monkeypatch.setenv("LM_STUDIO_MODEL", "ignored-model")
    monkeypatch.setenv("LM_STUDIO_BASE_URL", "http://host.docker.internal:1234/v1/")
    monkeypatch.setenv("LM_STUDIO_API_KEY", "secret-token")

    with patch("openai.AsyncOpenAI") as client:
        provider = LMStudioProvider(model_name="loaded-model")

    client.assert_called_once_with(
        base_url="http://host.docker.internal:1234/v1",
        api_key="secret-token",
    )
    assert provider.model_name == "loaded-model"


def test_requires_a_model_identifier(monkeypatch):
    monkeypatch.delenv("LM_STUDIO_MODEL", raising=False)

    with patch(
        "app.services.llm.providers.lmstudio_provider.list_lmstudio_model_ids",
        return_value=[],
    ):
        with pytest.raises(ValueError, match="no available model"):
            LMStudioProvider()


def test_uses_first_discovered_model_when_no_default_is_configured(monkeypatch):
    monkeypatch.delenv("LM_STUDIO_MODEL", raising=False)

    with (
        patch("openai.AsyncOpenAI"),
        patch(
            "app.services.llm.providers.lmstudio_provider.list_lmstudio_model_ids",
            return_value=["first-model", "second-model"],
        ),
    ):
        provider = LMStudioProvider()

    assert provider.model_name == "first-model"


def test_discovers_models_from_openai_compatible_endpoint(monkeypatch):
    monkeypatch.setenv("LM_STUDIO_BASE_URL", "http://localhost:1234/v1/")
    monkeypatch.setenv("LM_STUDIO_API_KEY", "local-token")
    response = Mock()
    response.json.return_value = {
        "models": [
            {"type": "llm", "key": "qwen/qwen3-8b"},
            {"type": "llm", "key": "openai/gpt-oss-20b"},
            {"type": "llm", "key": "qwen/qwen3-8b"},
            {"type": "embedding", "key": "nomic-embed-text"},
        ]
    }

    with patch("httpx.get", return_value=response) as get:
        models = list_lmstudio_model_ids()

    get.assert_called_once_with(
        "http://localhost:1234/api/v1/models",
        headers={"Authorization": "Bearer local-token"},
        timeout=2.0,
    )
    response.raise_for_status.assert_called_once_with()
    assert models == ["qwen/qwen3-8b", "openai/gpt-oss-20b"]


def test_model_discovery_failure_returns_empty_list():
    with patch("httpx.get", side_effect=httpx.ConnectError("offline")):
        assert list_lmstudio_model_ids() == []
