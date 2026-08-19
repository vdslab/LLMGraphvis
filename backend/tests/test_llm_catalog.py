from unittest.mock import patch

from app.services.llm.catalog import get_available_provider_catalog


def _provider_ids():
    with patch(
        "app.services.llm.catalog.list_lmstudio_model_ids", return_value=[]
    ):
        return [provider["id"] for provider in get_available_provider_catalog()]


def test_openai_is_hidden_without_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    assert "openai" not in _provider_ids()


def test_openai_is_hidden_with_blank_api_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "   ")

    assert "openai" not in _provider_ids()


def test_openai_is_available_with_api_key(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    assert "openai" in _provider_ids()


def test_other_providers_are_not_affected(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("LM_STUDIO_MODEL", raising=False)

    assert _provider_ids() == ["google", "anthropic"]


def test_lmstudio_is_hidden_when_server_has_no_models():
    with patch(
        "app.services.llm.catalog.list_lmstudio_model_ids", return_value=[]
    ):
        assert "lmstudio" not in [
            provider["id"] for provider in get_available_provider_catalog()
        ]


def test_lmstudio_uses_discovered_models(monkeypatch):
    monkeypatch.setenv("LM_STUDIO_MODEL", "qwen/qwen3-8b")

    with patch(
        "app.services.llm.catalog.list_lmstudio_model_ids",
        return_value=["qwen/qwen3-8b", "openai/gpt-oss-20b"],
    ):
        providers = get_available_provider_catalog()
    lmstudio = next(provider for provider in providers if provider["id"] == "lmstudio")

    assert lmstudio == {
        "id": "lmstudio",
        "label": "LM Studio (Local)",
        "models": [
            {
                "id": "qwen/qwen3-8b",
                "label": "qwen/qwen3-8b",
                "default": True,
            },
            {
                "id": "openai/gpt-oss-20b",
                "label": "openai/gpt-oss-20b",
                "default": False,
            },
        ],
    }
