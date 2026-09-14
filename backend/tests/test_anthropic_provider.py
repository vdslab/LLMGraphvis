from unittest.mock import AsyncMock, MagicMock
import pytest

from app.services.llm.providers.anthropic_provider import AnthropicProvider
from app.services.llm.providers.types import (
    LLMFunctionCallPart,
    LLMFunctionResponsePart,
    LLMMessage,
    LLMTextPart,
    ToolDefinition,
)


def _provider(client=None):
    provider = AnthropicProvider.__new__(AnthropicProvider)
    provider.client = client or MagicMock()
    provider.model_name = "claude-sonnet-4-6"
    provider.max_tokens = 4096
    return provider


def test_converts_history_and_preserves_tool_call_ids():
    provider = _provider()
    history = [
        LLMMessage("user", [LLMTextPart("analyse")]),
        LLMMessage(
            "model",
            [
                LLMTextPart("Checking."),
                LLMFunctionCallPart("analysis_degree", {"network_id": 3}, "call_1"),
            ],
        ),
        LLMMessage(
            "tool",
            [
                LLMFunctionResponsePart(
                    "analysis_degree", {"values": [1, 2]}, "call_1"
                )
            ],
        ),
    ]

    messages = provider._to_anthropic_messages(history)

    assert messages[0] == {"role": "user", "content": "analyse"}
    assert messages[1]["role"] == "assistant"
    assert messages[1]["content"][0] == {"type": "text", "text": "Checking."}
    assert messages[1]["content"][1] == {
        "type": "tool_use",
        "id": "call_1",
        "name": "analysis_degree",
        "input": {"network_id": 3},
    }
    assert messages[2]["role"] == "user"
    assert messages[2]["content"][0] == {
        "type": "tool_result",
        "tool_use_id": "call_1",
        "content": '{"values": [1, 2]}',
    }


def test_converts_tools_and_lowercases_schemas():
    provider = _provider()
    tools = [
        ToolDefinition(
            name="test_tool",
            description="A test tool",
            parameters={
                "type": "OBJECT",
                "properties": {
                    "count": {"type": "INTEGER"},
                },
            },
        )
    ]
    anthropic_tools = provider._to_anthropic_tools(tools)
    assert len(anthropic_tools) == 1
    assert anthropic_tools[0]["name"] == "test_tool"
    assert anthropic_tools[0]["input_schema"]["type"] == "object"
    assert anthropic_tools[0]["input_schema"]["properties"]["count"]["type"] == "integer"


@pytest.mark.asyncio
async def test_stream_applies_prompt_caching():
    provider = _provider()

    mock_stream = MagicMock()
    mock_stream.__aenter__ = AsyncMock(return_value=mock_stream)
    mock_stream.__aexit__ = AsyncMock(return_value=None)

    async def empty_generator():
        if False:
            yield

    mock_stream.__aiter__ = MagicMock(side_effect=empty_generator)
    provider.client.messages.stream = MagicMock(return_value=mock_stream)

    tools = [
        ToolDefinition(name="t1", description="d1", parameters={"type": "object"}),
        ToolDefinition(name="t2", description="d2", parameters={"type": "object"}),
    ]
    history = [LLMMessage("user", [LLMTextPart("hello")])]

    async for _ in provider._stream(history, tools, "Instruction prompt"):
        pass

    provider.client.messages.stream.assert_called_once()
    call_kwargs = provider.client.messages.stream.call_args.kwargs

    # Check system prompt caching
    system_arg = call_kwargs["system"]
    assert isinstance(system_arg, list)
    assert system_arg[0]["text"] == "Instruction prompt"
    assert system_arg[0]["cache_control"] == {"type": "ephemeral"}

    # Check tools caching: last tool has cache_control
    tools_arg = call_kwargs["tools"]
    assert len(tools_arg) == 2
    assert "cache_control" not in tools_arg[0]
    assert tools_arg[1]["cache_control"] == {"type": "ephemeral"}


@pytest.mark.asyncio
async def test_stream_captures_usage_with_prompt_caching():
    from types import SimpleNamespace

    provider = _provider()

    mock_stream = MagicMock()
    mock_stream.__aenter__ = AsyncMock(return_value=mock_stream)
    mock_stream.__aexit__ = AsyncMock(return_value=None)

    events = [
        SimpleNamespace(
            type="message_start",
            message=SimpleNamespace(
                usage=SimpleNamespace(
                    input_tokens=10,
                    cache_creation_input_tokens=1000,
                    cache_read_input_tokens=500,
                )
            ),
        ),
        SimpleNamespace(
            type="message_delta",
            usage=SimpleNamespace(output_tokens=50),
        ),
        SimpleNamespace(type="message_stop"),
    ]

    async def event_generator():
        for e in events:
            yield e

    mock_stream.__aiter__ = MagicMock(side_effect=event_generator)
    provider.client.messages.stream = MagicMock(return_value=mock_stream)

    chunks = []
    async for chunk in provider._stream([], [], "prompt"):
        chunks.append(chunk)

    usage_chunk = next(c for c in chunks if c.usage is not None)
    assert usage_chunk.usage.input_tokens == 1010  # 10 + 1000
    assert usage_chunk.usage.output_tokens == 50
    assert usage_chunk.usage.cached_input_tokens == 500
