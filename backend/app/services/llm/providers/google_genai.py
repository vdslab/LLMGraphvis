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
        retryable_statuses = ["RESOURCE_EXHAUSTED", "INTERNAL", "UNAVAILABLE", "DEADLINE_EXCEEDED"]
        if str(status) in retryable_statuses:
            return True
        msg = str(exception).lower()
        if "resource exhausted" in msg or "internal server error" in msg or "service unavailable" in msg:
            return True
    except Exception:
        pass
    return False


class GoogleGenAIProvider(LLMProvider):
    def __init__(self, model_name: Optional[str] = None):
        self.client = self._initialize_client()
        self.model_name = model_name or os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    def _initialize_client(self) -> genai.Client:
        project_id = os.getenv("VERTEX_PROJECT_ID")
        location = os.getenv("VERTEX_LOCATION", "us-central1")
        api_key = os.getenv("GOOGLE_API_KEY")

        if project_id:
            msg = f"Using Vertex AI (Project: {project_id}, Location: {location})"
            logger.info(msg)
            print(msg)
            return genai.Client(vertexai=True, project=project_id, location=location)
        else:
            logger.info("Using Google AI Studio (API Key)")
            print("Using Google AI Studio (API Key)")
            return genai.Client(api_key=api_key)

    def _to_gemini_history(self, history: List[LLMMessage]) -> List[types.Content]:
        result = []
        for msg in history:
            parts = []
            for part in msg.parts:
                if isinstance(part, LLMTextPart):
                    parts.append(types.Part.from_text(text=part.text))
                elif isinstance(part, LLMFunctionCallPart):
                    parts.append(types.Part(
                        function_call=types.FunctionCall(name=part.name, args=part.args)
                    ))
                elif isinstance(part, LLMFunctionResponsePart):
                    parts.append(types.Part.from_function_response(
                        name=part.name, response=part.response
                    ))
            # Gemini's Content.role only accepts "user"/"model". Function-call results
            # (role == "tool") are conventionally sent as "user"-role content, mirroring
            # how the Anthropic provider folds tool_result blocks into a "user" turn.
            role = "user" if msg.role in ("user", "tool") else "model"
            result.append(types.Content(role=role, parts=parts))
        return result

    def _to_gemini_tools(self, tools: List[ToolDefinition]) -> List[types.Tool]:
        return [
            types.Tool(function_declarations=[
                types.FunctionDeclaration(
                    name=t.name,
                    description=t.description,
                    parameters=t.parameters,
                )
            ])
            for t in tools
        ]

    @retry(
        retry=retry_if_exception(_is_retryable_error),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    async def _raw_generate(self, gemini_history, gemini_tools, system_instruction):
        tool_config = types.ToolConfig(
            function_calling_config=types.FunctionCallingConfig(mode="AUTO")
        )
        return await self.client.aio.models.generate_content_stream(
            model=self.model_name,
            contents=gemini_history,
            config=types.GenerateContentConfig(
                tools=gemini_tools,
                tool_config=tool_config,
                system_instruction=system_instruction,
                thinking_config=types.ThinkingConfig(thinking_budget=2048)
                if "thinking" in self.model_name
                else None,
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
        response = await self._raw_generate(gemini_history, gemini_tools, system_instruction)

        in_simulated_thought = False
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
                # Native thinking (string content or boolean flag styles)
                is_thought = False
                thought_text = ""
                if hasattr(part, "thought") and isinstance(part.thought, str) and part.thought:
                    is_thought = True
                    thought_text = part.thought
                elif hasattr(part, "thought") and isinstance(part.thought, bool) and part.thought:
                    is_thought = True
                    if part.text:
                        thought_text = part.text

                if is_thought:
                    yield StreamChunk(thought=thought_text)
                    continue

                if part.text:
                    txt = part.text
                    if not in_simulated_thought:
                        if "<thought>" in txt:
                            valid_text, rest = txt.split("<thought>", 1)
                            if valid_text:
                                yield StreamChunk(text=valid_text)
                            in_simulated_thought = True
                            txt = rest
                        else:
                            yield StreamChunk(text=txt)
                            continue

                    if in_simulated_thought:
                        if "</thought>" in txt:
                            t_content, rest_text = txt.split("</thought>", 1)
                            yield StreamChunk(thought=t_content)
                            in_simulated_thought = False
                            if rest_text:
                                yield StreamChunk(text=rest_text)
                        else:
                            yield StreamChunk(thought=txt)
                    continue

                if part.function_call:
                    fc = part.function_call
                    yield StreamChunk(function_calls=[
                        FunctionCallData(name=fc.name, args=dict(fc.args))
                    ])

        if last_usage is not None:
            yield StreamChunk(usage=UsageData(
                input_tokens=last_usage.prompt_token_count or 0,
                output_tokens=last_usage.candidates_token_count or 0,
                cached_input_tokens=getattr(last_usage, "cached_content_token_count", 0) or 0,
            ))
