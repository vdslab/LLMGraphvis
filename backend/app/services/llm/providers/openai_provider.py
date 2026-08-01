import json
import os
from typing import AsyncIterator, List, Optional

from app.core.logging import get_logger

from .base import LLMProvider
from .types import (
    FunctionCallData,
    LLMFunctionCallPart,
    LLMFunctionResponsePart,
    LLMMessage,
    LLMTextPart,
    StreamChunk,
    ToolDefinition,
    UsageData,
)

logger = get_logger(__name__)

DEFAULT_OPENAI_MODEL = "gpt-5.6-sol"


class OpenAIProvider(LLMProvider):
    """OpenAI Chat Completions adapter for the provider-agnostic agent loop."""

    def __init__(self, model_name: Optional[str] = None):
        from openai import AsyncOpenAI

        self.client = AsyncOpenAI()
        self.model_name = (
            model_name or os.getenv("OPENAI_MODEL") or DEFAULT_OPENAI_MODEL
        )

    def _to_openai_messages(
        self, history: List[LLMMessage], system_instruction: str
    ) -> List[dict]:
        messages = [{"role": "system", "content": system_instruction}]

        for msg in history:
            if msg.role == "model":
                text = "".join(
                    part.text
                    for part in msg.parts
                    if isinstance(part, LLMTextPart) and part.text
                )
                tool_calls = [
                    {
                        "id": part.call_id or f"call_{part.name}",
                        "type": "function",
                        "function": {
                            "name": part.name,
                            "arguments": json.dumps(part.args),
                        },
                    }
                    for part in msg.parts
                    if isinstance(part, LLMFunctionCallPart)
                ]
                message = {"role": "assistant", "content": text or None}
                if tool_calls:
                    message["tool_calls"] = tool_calls
                if text or tool_calls:
                    messages.append(message)

            elif msg.role == "tool":
                for part in msg.parts:
                    if not isinstance(part, LLMFunctionResponsePart):
                        continue
                    response = part.response
                    if not isinstance(response, str):
                        response = json.dumps(response)
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": part.call_id or f"call_{part.name}",
                            "content": response,
                        }
                    )

            else:
                text = "".join(
                    part.text
                    for part in msg.parts
                    if isinstance(part, LLMTextPart)
                )
                if text:
                    messages.append({"role": "user", "content": text})

        return messages

    def _to_openai_tools(self, tools: List[ToolDefinition]) -> List[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.parameters
                    or {"type": "object", "properties": {}},
                },
            }
            for tool in tools
        ]

    def generate(
        self,
        history: List[LLMMessage],
        tools: List[ToolDefinition],
        system_instruction: str,
    ) -> AsyncIterator[StreamChunk]:
        return self._stream(history, tools, system_instruction)

    async def _stream(
        self,
        history: List[LLMMessage],
        tools: List[ToolDefinition],
        system_instruction: str,
    ):
        messages = self._to_openai_messages(history, system_instruction)
        openai_tools = self._to_openai_tools(tools)
        pending_tools: dict[int, dict] = {}

        stream = await self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            tools=openai_tools or None,
            stream=True,
            stream_options={"include_usage": True},
        )

        async for chunk in stream:
            usage = getattr(chunk, "usage", None)
            if usage is not None:
                prompt_details = getattr(usage, "prompt_tokens_details", None)
                yield StreamChunk(
                    usage=UsageData(
                        input_tokens=getattr(usage, "prompt_tokens", 0) or 0,
                        output_tokens=getattr(usage, "completion_tokens", 0) or 0,
                        cached_input_tokens=(
                            getattr(prompt_details, "cached_tokens", 0) or 0
                            if prompt_details is not None
                            else 0
                        ),
                    )
                )

            choices = getattr(chunk, "choices", None) or []
            for choice in choices:
                delta = choice.delta
                if getattr(delta, "content", None):
                    yield StreamChunk(text=delta.content)

                for tool_call in getattr(delta, "tool_calls", None) or []:
                    pending = pending_tools.setdefault(
                        tool_call.index,
                        {"id": None, "name": "", "arguments": ""},
                    )
                    if getattr(tool_call, "id", None):
                        pending["id"] = tool_call.id
                    function = getattr(tool_call, "function", None)
                    if function is not None:
                        if getattr(function, "name", None):
                            pending["name"] = function.name
                        if getattr(function, "arguments", None):
                            pending["arguments"] += function.arguments

                if getattr(choice, "finish_reason", None) == "tool_calls":
                    for index in sorted(pending_tools):
                        pending = pending_tools[index]
                        try:
                            args = json.loads(pending["arguments"] or "{}")
                        except json.JSONDecodeError:
                            logger.warning(
                                "OpenAI returned invalid tool arguments for %s",
                                pending["name"],
                            )
                            args = {}
                        yield StreamChunk(
                            function_calls=[
                                FunctionCallData(
                                    name=pending["name"],
                                    args=args,
                                    call_id=pending["id"],
                                )
                            ]
                        )
                    pending_tools.clear()
