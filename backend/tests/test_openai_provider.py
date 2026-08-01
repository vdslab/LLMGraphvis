import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services.llm.providers.openai_provider import OpenAIProvider
from app.services.llm.providers.types import (
    LLMFunctionCallPart,
    LLMFunctionResponsePart,
    LLMMessage,
    LLMTextPart,
    ToolDefinition,
)


def _provider(client=None):
    provider = OpenAIProvider.__new__(OpenAIProvider)
    provider.client = client
    provider.model_name = "gpt-5.6-sol"
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

    messages = provider._to_openai_messages(history, "system prompt")

    assert messages[0] == {"role": "system", "content": "system prompt"}
    assert messages[1] == {"role": "user", "content": "analyse"}
    assert messages[2]["role"] == "assistant"
    assert messages[2]["tool_calls"][0]["id"] == "call_1"
    assert json.loads(messages[2]["tool_calls"][0]["function"]["arguments"]) == {
        "network_id": 3
    }
    assert messages[3] == {
        "role": "tool",
        "tool_call_id": "call_1",
        "content": '{"values": [1, 2]}',
    }


def test_converts_tool_definitions():
    provider = _provider()
    tools = [
        ToolDefinition(
            name="network_info",
            description="Inspect a network.",
            parameters={
                "type": "object",
                "properties": {"network_id": {"type": "integer"}},
            },
        )
    ]

    converted = provider._to_openai_tools(tools)

    assert converted == [
        {
            "type": "function",
            "function": {
                "name": "network_info",
                "description": "Inspect a network.",
                "parameters": tools[0].parameters,
            },
        }
    ]


class _AsyncStream:
    def __init__(self, chunks):
        self._chunks = chunks

    def __aiter__(self):
        self._iterator = iter(self._chunks)
        return self

    async def __anext__(self):
        try:
            return next(self._iterator)
        except StopIteration:
            raise StopAsyncIteration


@pytest.mark.asyncio
async def test_streams_text_tools_and_usage():
    tool_start = SimpleNamespace(
        index=0,
        id="call_abc",
        function=SimpleNamespace(name="network_info", arguments='{"network_'),
    )
    tool_end = SimpleNamespace(
        index=0,
        id=None,
        function=SimpleNamespace(name=None, arguments='id": 7}'),
    )
    chunks = [
        SimpleNamespace(
            usage=None,
            choices=[
                SimpleNamespace(
                    delta=SimpleNamespace(content="Inspecting", tool_calls=None),
                    finish_reason=None,
                )
            ],
        ),
        SimpleNamespace(
            usage=None,
            choices=[
                SimpleNamespace(
                    delta=SimpleNamespace(content=None, tool_calls=[tool_start]),
                    finish_reason=None,
                )
            ],
        ),
        SimpleNamespace(
            usage=None,
            choices=[
                SimpleNamespace(
                    delta=SimpleNamespace(content=None, tool_calls=[tool_end]),
                    finish_reason="tool_calls",
                )
            ],
        ),
        SimpleNamespace(
            usage=SimpleNamespace(
                prompt_tokens=120,
                completion_tokens=30,
                prompt_tokens_details=SimpleNamespace(cached_tokens=20),
            ),
            choices=[],
        ),
    ]
    completions = SimpleNamespace(create=AsyncMock(return_value=_AsyncStream(chunks)))
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    provider = _provider(client)

    result = [
        chunk
        async for chunk in provider.generate(
            [LLMMessage("user", [LLMTextPart("inspect")])], [], "system"
        )
    ]

    assert result[0].text == "Inspecting"
    assert result[1].function_calls[0].name == "network_info"
    assert result[1].function_calls[0].args == {"network_id": 7}
    assert result[1].function_calls[0].call_id == "call_abc"
    assert result[2].usage.input_tokens == 120
    assert result[2].usage.output_tokens == 30
    assert result[2].usage.cached_input_tokens == 20
    kwargs = completions.create.await_args.kwargs
    assert kwargs["stream"] is True
    assert kwargs["stream_options"] == {"include_usage": True}
    assert kwargs["tools"] is None
