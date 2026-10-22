from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.services.llm.providers.google_genai import GoogleGenAIProvider
from app.services.llm.providers.types import (
    LLMFunctionCallPart,
    LLMFunctionResponsePart,
    LLMMessage,
)


async def _async_iter(items):
    for item in items:
        yield item


@pytest.fixture
def provider(monkeypatch):
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    monkeypatch.delenv("GEMINI_THINKING_LEVEL", raising=False)
    with patch.object(
        GoogleGenAIProvider, "_initialize_client", return_value=MagicMock()
    ):
        return GoogleGenAIProvider()


def test_gemini_38_is_default_and_uses_native_thinking(provider):
    assert provider.model_name == "gemini-3.8-flash"
    assert provider.thinking_level == "medium"
    assert provider.supports_native_thinking is True


def test_invalid_gemini_thinking_level_fails_fast(monkeypatch):
    monkeypatch.setenv("GEMINI_THINKING_LEVEL", "minimal")
    with patch.object(
        GoogleGenAIProvider, "_initialize_client", return_value=MagicMock()
    ):
        with pytest.raises(ValueError, match="GEMINI_THINKING_LEVEL"):
            GoogleGenAIProvider()


def test_history_preserves_gemini_call_context(provider):
    signature = b"encrypted-thought"
    history = [
        LLMMessage(
            role="model",
            parts=[
                LLMFunctionCallPart(
                    name="analysis_pagerank",
                    args={"network_id": 1},
                    call_id="call_123",
                    thought_signature=signature,
                )
            ],
        ),
        LLMMessage(
            role="tool",
            parts=[
                LLMFunctionResponsePart(
                    name="analysis_pagerank",
                    response={"saved_as": "pagerank"},
                    call_id="call_123",
                )
            ],
        ),
    ]

    converted = provider._to_gemini_history(history)

    call_part = converted[0].parts[0]
    response_part = converted[1].parts[0]
    assert call_part.function_call.id == "call_123"
    assert call_part.thought_signature == signature
    assert response_part.function_response.id == "call_123"
    assert response_part.function_response.name == "analysis_pagerank"


def test_unsigned_legacy_tool_exchange_is_omitted_for_gemini_3(provider):
    history = [
        LLMMessage(
            role="model",
            parts=[LLMFunctionCallPart("old_tool", {}, "legacy_1")],
        ),
        LLMMessage(
            role="tool",
            parts=[LLMFunctionResponsePart("old_tool", {"ok": True}, "legacy_1")],
        ),
    ]

    assert provider._to_gemini_history(history) == []


@pytest.mark.asyncio
async def test_gemini_3_request_uses_thinking_level(provider):
    provider.client.aio.models.generate_content_stream = AsyncMock(
        return_value=MagicMock()
    )

    await provider._raw_generate([], [], "system")

    config = provider.client.aio.models.generate_content_stream.call_args.kwargs[
        "config"
    ]
    assert config.thinking_config.thinking_level.value == "MEDIUM"
    assert config.thinking_config.thinking_budget is None
    assert config.thinking_config.include_thoughts is True


@pytest.mark.asyncio
async def test_stream_preserves_function_call_id_and_signature(provider):
    from google.genai import types

    function_part = types.Part(
        function_call=types.FunctionCall(
            id="call_456",
            name="network_get_summary",
            args={"network_id": 1},
        ),
        thought_signature=b"encrypted",
    )
    candidate = MagicMock()
    candidate.content.parts = [function_part]
    chunk = MagicMock(usage_metadata=None, candidates=[candidate])
    provider._raw_generate = AsyncMock(return_value=_async_iter([chunk]))

    result = [item async for item in provider._stream([], [], "system")]

    call = result[0].function_calls[0]
    assert call.call_id == "call_456"
    assert call.thought_signature == b"encrypted"


def test_local_tool_schemas_survive_gemini_schema_validation(provider):
    """Local tools bypassed the sanitizer that MCP tool schemas go through.

    `google.genai.types.Schema` forbids unknown keys, so the `exclusiveMinimum`
    Pydantic emits for `step: Field(gt=0)` in ask_user's schema made the whole
    FunctionDeclaration list unbuildable — and ask_user is exposed on every
    turn, so every Gemini turn raised before reaching the API.
    """
    from app.services.llm.local_tools import get_local_tools

    definitions = get_local_tools()
    assert {"ask_user", "skill_load", "tool_search"} <= {t.name for t in definitions}

    declarations = provider._to_gemini_tools(definitions)

    assert len(declarations) == len(definitions)
    ask_user = next(
        declaration.function_declarations[0]
        for declaration in declarations
        if declaration.function_declarations[0].name == "ask_user"
    )
    # The array shape the model has to produce must survive the cleaning.
    fields = ask_user.parameters.properties["fields"]
    assert fields.type == "ARRAY"
    assert fields.items.properties["kind"].enum == [
        "select",
        "multiselect",
        "slider",
        "number",
        "text",
    ]


def test_tuning_tool_schemas_survive_gemini_schema_validation(provider):
    """The tuning tools carry `gt=0` steps and a multi-type `value` union."""
    from app.services.llm.local_tools import get_local_tools

    definitions = [
        t
        for t in get_local_tools()
        if t.name in {"offer_parameter_tuning", "apply_parameter_tuning"}
    ]
    assert len(definitions) == 2
    declarations = provider._to_gemini_tools(definitions)
    by_name = {d.function_declarations[0].name: d.function_declarations[0] for d in declarations}
    fields = by_name["offer_parameter_tuning"].parameters.properties["fields"]
    assert fields.type == "ARRAY"
    assert "suggested" in fields.items.properties
    changes = by_name["apply_parameter_tuning"].parameters.properties["changes"]
    assert changes.type == "ARRAY"
