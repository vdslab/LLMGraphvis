import logging
import os
from typing import AsyncIterator, List, Optional

from dotenv import load_dotenv
from google import genai
from google.genai import types
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from app.core.logging import get_logger

from .base import LLMProvider
from .defaults import DEFAULT_GEMINI_MODEL
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
load_dotenv()


def _is_retryable_error(exception) -> bool:
    try:
        code = getattr(exception, "code", None)
        status = getattr(exception, "status", None)
        retryable_codes = [429, 500, 502, 503, 504]
        if code in retryable_codes:
            return True
        retryable_statuses = [
            "RESOURCE_EXHAUSTED",
            "INTERNAL",
            "UNAVAILABLE",
            "DEADLINE_EXCEEDED",
        ]
        if str(status) in retryable_statuses:
            return True
        msg = str(exception).lower()
        if (
            "resource exhausted" in msg
            or "internal server error" in msg
            or "service unavailable" in msg
        ):
            return True
    except Exception:
        pass
    return False


DEFAULT_VERTEX_LOCATION = "global"
DEFAULT_THINKING_LEVEL = "medium"
SUPPORTED_THINKING_LEVELS = {"minimal", "low", "medium", "high"}
# Only these accept "minimal"; the others are sent "low" instead.
MINIMAL_THINKING_MODELS = ("gemini-3.6-flash", "gemini-3.5-flash-lite")
# Gemini 4 Argon can think for minutes before its first token; Google asks
# for an HTTP timeout of at least 15 minutes (milliseconds here).
HTTP_TIMEOUT_MS = 15 * 60 * 1000


def usage_from_metadata(meta) -> UsageData:
    """Normalize Gemini `usage_metadata` to UsageData's meaning.

    `prompt_token_count` already includes `cached_content_token_count`, and
    `tool_use_prompt_token_count` is billed as input beside it. Thinking is
    billed as output but counted in `thoughts_token_count`, not in
    `candidates_token_count`.
    """

    def count(name: str) -> int:
        return getattr(meta, name, 0) or 0

    thoughts = count("thoughts_token_count")
    return UsageData(
        input_tokens=count("prompt_token_count") + count("tool_use_prompt_token_count"),
        output_tokens=count("candidates_token_count") + thoughts,
        cached_input_tokens=count("cached_content_token_count"),
        reasoning_tokens=thoughts,
    )


def _uses_thinking_level(model_name: str) -> bool:
    """Whether the model takes `thinking_level` and signs its function calls.

    Gemini 3 and later do (ADR 0007, 0043); only the 2.5 generation does not.
    """
    return not model_name.startswith("gemini-2.")


class GoogleGenAIProvider(LLMProvider):
    def __init__(self, model_name: Optional[str] = None):
        self.client = self._initialize_client()
        # `or` chains (instead of os.getenv defaults) so that empty-string values —
        # e.g. docker-compose passing through an unset host variable — still fall back.
        self.model_name = (
            model_name or os.getenv("GEMINI_MODEL") or DEFAULT_GEMINI_MODEL
        )
        self.thinking_level = (
            (os.getenv("GEMINI_THINKING_LEVEL") or DEFAULT_THINKING_LEVEL)
            .strip()
            .lower()
        )
        if self.thinking_level not in SUPPORTED_THINKING_LEVELS:
            choices = ", ".join(sorted(SUPPORTED_THINKING_LEVELS))
            raise ValueError(f"GEMINI_THINKING_LEVEL must be one of: {choices}")

    @property
    def supports_native_thinking(self) -> bool:
        # Every request asks for thought summaries (`include_thoughts`).
        return True

    def _thinking_config(self) -> types.ThinkingConfig:
        if not _uses_thinking_level(self.model_name):
            # Gemini 2.5 thinks with a dynamic budget by default.
            return types.ThinkingConfig(include_thoughts=True)
        level = self.thinking_level
        if level == "minimal" and not self.model_name.startswith(
            MINIMAL_THINKING_MODELS
        ):
            level = "low"
        return types.ThinkingConfig(thinking_level=level, include_thoughts=True)

    def _initialize_client(self) -> genai.Client:
        project_id = os.getenv("VERTEX_PROJECT_ID")
        location = os.getenv("VERTEX_LOCATION") or DEFAULT_VERTEX_LOCATION
        api_key = os.getenv("GOOGLE_API_KEY")
        http_options = types.HttpOptions(timeout=HTTP_TIMEOUT_MS)

        if project_id:
            logger.info(
                f"Using Vertex AI (Project: {project_id}, Location: {location})"
            )
            return genai.Client(
                vertexai=True,
                project=project_id,
                location=location,
                http_options=http_options,
            )
        else:
            logger.info("Using Google AI Studio (API Key)")
            return genai.Client(api_key=api_key, http_options=http_options)

    def _to_gemini_history(self, history: List[LLMMessage]) -> List[types.Content]:
        result = []
        valid_call_ids = set()
        for msg in history:
            parts = []
            call_parts = [
                part for part in msg.parts if isinstance(part, LLMFunctionCallPart)
            ]
            # Gemini 3 and later require the encrypted signature from the original model
            # response. Old persisted history only has synthetic calls; omit those
            # tool exchanges while retaining the assistant's final text turns.
            signed_model_turn = not (
                _uses_thinking_level(self.model_name)
                and call_parts
                and not any(part.thought_signature for part in call_parts)
            )
            for part in msg.parts:
                if isinstance(part, LLMTextPart):
                    parts.append(types.Part.from_text(text=part.text))
                elif isinstance(part, LLMFunctionCallPart):
                    if not signed_model_turn:
                        continue
                    parts.append(
                        types.Part(
                            function_call=types.FunctionCall(
                                id=part.call_id,
                                name=part.name,
                                args=part.args,
                            ),
                            thought_signature=part.thought_signature,
                        )
                    )
                    if part.call_id:
                        valid_call_ids.add(part.call_id)
                elif isinstance(part, LLMFunctionResponsePart):
                    if _uses_thinking_level(self.model_name) and (
                        not part.call_id or part.call_id not in valid_call_ids
                    ):
                        continue
                    parts.append(
                        types.Part(
                            function_response=types.FunctionResponse(
                                id=part.call_id,
                                name=part.name,
                                response=part.response,
                            )
                        )
                    )
            if not parts:
                continue
            # Gemini's Content.role only accepts "user"/"model". Function-call results
            # (role == "tool") are conventionally sent as "user"-role content, mirroring
            # how the Anthropic provider folds tool_result blocks into a "user" turn.
            role = "user" if msg.role in ("user", "tool") else "model"
            result.append(types.Content(role=role, parts=parts))
        return result

    def _to_gemini_tools(self, tools: List[ToolDefinition]) -> List[types.Tool]:
        return [
            types.Tool(
                function_declarations=[
                    types.FunctionDeclaration(
                        name=t.name,
                        description=t.description,
                        parameters=t.parameters,
                    )
                ]
            )
            for t in tools
        ]

    @retry(
        retry=retry_if_exception(_is_retryable_error),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    async def _raw_generate(self, gemini_history, gemini_tools, system_instruction):
        # A tool_config without tools is rejected by the API, and tool-less
        # generations are a real case here (the one-shot chat title in titles.py).
        tool_config = (
            types.ToolConfig(
                function_calling_config=types.FunctionCallingConfig(mode="AUTO")
            )
            if gemini_tools
            else None
        )
        return await self.client.aio.models.generate_content_stream(
            model=self.model_name,
            contents=gemini_history,
            config=types.GenerateContentConfig(
                tools=gemini_tools or None,
                tool_config=tool_config,
                system_instruction=system_instruction,
                thinking_config=self._thinking_config(),
            ),
        )

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
        gemini_history = self._to_gemini_history(history)
        gemini_tools = self._to_gemini_tools(tools)
        response = await self._raw_generate(
            gemini_history, gemini_tools, system_instruction
        )

        last_usage = None

        async for chunk in response:
            if getattr(chunk, "usage_metadata", None):
                last_usage = chunk.usage_metadata

            if not chunk.candidates:
                continue
            cand = chunk.candidates[0]
            if not (cand.content and cand.content.parts):
                continue

            for part in cand.content.parts:
                if part.thought:
                    if part.text:
                        yield StreamChunk(thought=part.text)
                    continue

                if part.text:
                    yield StreamChunk(text=part.text)
                    continue

                if part.function_call:
                    fc = part.function_call
                    yield StreamChunk(
                        function_calls=[
                            FunctionCallData(
                                name=fc.name,
                                args=dict(fc.args),
                                call_id=getattr(fc, "id", None),
                                thought_signature=getattr(
                                    part, "thought_signature", None
                                ),
                            )
                        ]
                    )

        if last_usage is not None:
            yield StreamChunk(usage=usage_from_metadata(last_usage))
