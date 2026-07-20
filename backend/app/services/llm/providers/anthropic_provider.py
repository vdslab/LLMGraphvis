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


# TODO: if the debug log below never fires in production logs, this function and its
# call site can be safely removed as dead code (Gemini-specific uppercase-type quirk
# that MCP/Pydantic-generated schemas don't exhibit).
def _lowercase_schema_types(schema) -> dict:
    """Recursively convert uppercase JSON Schema type values to lowercase.

    Google GenAI uses uppercase types ("OBJECT", "STRING"), but Anthropic
    requires standard JSON Schema lowercase types ("object", "string").
    """
    if not isinstance(schema, dict):
        return schema
    result = {}
    for key, value in schema.items():
        if key == "type" and isinstance(value, str):
            if value != value.lower():
                logger.debug(
                    f"_lowercase_schema_types: found non-lowercase type value {value!r} "
                    "— this function may not be dead code after all"
                )
            result[key] = value.lower()
        elif isinstance(value, dict):
            result[key] = _lowercase_schema_types(value)
        elif isinstance(value, list):
            result[key] = [
                _lowercase_schema_types(item) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            result[key] = value
    return result


DEFAULT_CLAUDE_MODEL = "claude-opus-4-8"
DEFAULT_ANTHROPIC_VERTEX_REGION = "us-east5"
DEFAULT_MAX_TOKENS = 16000


class AnthropicProvider(LLMProvider):
    def __init__(self, model_name: Optional[str] = None):
        self.client = self._initialize_client()
        # `or` chains (instead of os.getenv defaults) so that empty-string values —
        # e.g. docker-compose passing through an unset host variable — still fall back.
        self.model_name = model_name or os.getenv("CLAUDE_MODEL") or DEFAULT_CLAUDE_MODEL
        self.max_tokens = int(os.getenv("ANTHROPIC_MAX_TOKENS") or DEFAULT_MAX_TOKENS)

    @property
    def supports_native_thinking(self) -> bool:
        # `_stream` always requests thinking={"type": "adaptive"} below, so every
        # Claude call on this provider yields real thinking_delta chunks.
        return True

    def _initialize_client(self):
        import anthropic
        project_id = os.getenv("VERTEX_PROJECT_ID")
        if project_id:
            # Anthropic on Vertex AI — uses Google Cloud ADC, no ANTHROPIC_API_KEY needed.
            # Vertex regions for Claude differ from Google's own services.
            region = (
                os.getenv("ANTHROPIC_VERTEX_REGION")
                or os.getenv("VERTEX_LOCATION")
                or DEFAULT_ANTHROPIC_VERTEX_REGION
            )
            logger.info(
                f"Using Anthropic on Vertex AI (Project: {project_id}, Region: {region})"
            )
            return anthropic.AsyncAnthropicVertex(project_id=project_id, region=region, max_retries=5)
        else:
            logger.info("Using Anthropic API (direct)")
            return anthropic.AsyncAnthropic(max_retries=5)

    def _to_anthropic_messages(self, history: List[LLMMessage]) -> List[dict]:
        """Convert LLMMessage list to Anthropic messages format.

        Role mapping:
          "user"  -> "user" with text content blocks
          "model" -> "assistant" with text and/or tool_use blocks
          "tool"  -> merged into the preceding "user" turn as tool_result blocks
        """
        messages = []
        for msg in history:
            if msg.role == "model":
                content = []
                for part in msg.parts:
                    if isinstance(part, LLMTextPart) and part.text:
                        content.append({"type": "text", "text": part.text})
                    elif isinstance(part, LLMFunctionCallPart):
                        content.append({
                            "type": "tool_use",
                            "id": part.call_id or f"call_{part.name}",
                            "name": part.name,
                            "input": part.args,
                        })
                if content:
                    messages.append({"role": "assistant", "content": content})

            elif msg.role == "tool":
                content = []
                for part in msg.parts:
                    if isinstance(part, LLMFunctionResponsePart):
                        resp = part.response
                        if not isinstance(resp, str):
                            resp = json.dumps(resp)
                        content.append({
                            "type": "tool_result",
                            "tool_use_id": part.call_id or f"call_{part.name}",
                            "content": resp,
                        })
                if content:
                    if messages and messages[-1]["role"] == "user":
                        prev = messages[-1]["content"]
                        if isinstance(prev, list):
                            prev.extend(content)
                        else:
                            messages[-1]["content"] = [{"type": "text", "text": prev}] + content
                    else:
                        messages.append({"role": "user", "content": content})

            else:  # "user"
                content = []
                for part in msg.parts:
                    if isinstance(part, LLMTextPart):
                        content.append({"type": "text", "text": part.text})
                if content:
                    # Use plain string for single text-only user messages
                    if len(content) == 1:
                        messages.append({"role": "user", "content": content[0]["text"]})
                    else:
                        messages.append({"role": "user", "content": content})
        return messages

    def _to_anthropic_tools(self, tools: List[ToolDefinition]) -> List[dict]:
        return [
            {
                "name": t.name,
                "description": t.description,
                "input_schema": _lowercase_schema_types(t.parameters)
                if t.parameters
                else {"type": "object", "properties": {}},
            }
            for t in tools
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
        messages = self._to_anthropic_messages(history)
        anthropic_tools = self._to_anthropic_tools(tools)

        # Accumulate partial tool-call inputs, keyed by content block index
        pending_tools: dict = {}

        # Usage accounting: input/cached tokens arrive once at message_start;
        # output_tokens arrives on message_delta as a running total for this stream,
        # so we simply overwrite usage_output rather than summing deltas.
        usage_input = 0
        usage_cached = 0
        usage_output = 0

        async with self.client.messages.stream(
            model=self.model_name,
            max_tokens=self.max_tokens,
            system=system_instruction,
            messages=messages,
            tools=anthropic_tools,
            thinking={"type": "adaptive"},
        ) as stream:
            async for event in stream:
                etype = event.type

                if etype == "content_block_start":
                    cb = event.content_block
                    if cb.type == "tool_use":
                        pending_tools[event.index] = {
                            "id": cb.id,
                            "name": cb.name,
                            "input_str": "",
                        }

                elif etype == "content_block_delta":
                    delta = event.delta
                    if delta.type == "thinking_delta":
                        yield StreamChunk(thought=delta.thinking)
                    elif delta.type == "text_delta":
                        yield StreamChunk(text=delta.text)
                    elif delta.type == "input_json_delta":
                        idx = event.index
                        if idx in pending_tools:
                            pending_tools[idx]["input_str"] += delta.partial_json

                elif etype == "content_block_stop":
                    idx = event.index
                    if idx in pending_tools:
                        tc = pending_tools.pop(idx)
                        try:
                            args = json.loads(tc["input_str"]) if tc["input_str"] else {}
                        except json.JSONDecodeError:
                            args = {}
                        yield StreamChunk(function_calls=[
                            FunctionCallData(name=tc["name"], args=args, call_id=tc["id"])
                        ])

                elif etype == "message_start":
                    u = getattr(event.message, "usage", None)
                    if u is not None:
                        usage_input = getattr(u, "input_tokens", 0) or 0
                        usage_cached = getattr(u, "cache_read_input_tokens", 0) or 0

                elif etype == "message_delta":
                    u = getattr(event, "usage", None)
                    if u is not None:
                        # message_delta.usage.output_tokens is a running total for this
                        # stream (not a delta) — overwrite rather than accumulate.
                        output_tokens = getattr(u, "output_tokens", None)
                        if output_tokens is not None:
                            usage_output = output_tokens

                elif etype == "message_stop":
                    yield StreamChunk(usage=UsageData(
                        input_tokens=usage_input,
                        output_tokens=usage_output,
                        cached_input_tokens=usage_cached,
                    ))
