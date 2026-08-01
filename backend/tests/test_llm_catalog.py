from app.services.llm.catalog import get_available_provider_catalog


def _provider_ids():
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

    assert _provider_ids() == ["google", "anthropic"]
