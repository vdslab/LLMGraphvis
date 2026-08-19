from unittest.mock import patch

import pytest

from app.services.llm.providers.lmstudio_provider import (
    DEFAULT_LM_STUDIO_BASE_URL,
    LMStudioProvider,
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

    with pytest.raises(ValueError, match="LM_STUDIO_MODEL"):
        LMStudioProvider()
