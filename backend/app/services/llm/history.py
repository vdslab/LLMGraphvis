from typing import List

from sqlalchemy.orm import Session

from common import models
from .providers.types import (
    LLMFunctionCallPart,
    LLMFunctionResponsePart,
    LLMMessage,
    LLMTextPart,
)
from .engine import _truncate_tool_result


def build_history(chat_id: int, user_message: str, db: Session) -> List[LLMMessage]:
    """Build conversation history from the database."""
    messages = (
        db.query(models.ChatMessage)
        .filter(models.ChatMessage.chat_id == chat_id)
        .order_by(models.ChatMessage.created_at.asc())
        .all()
    )

    history: List[LLMMessage] = []
    for msg in messages:
        role = "user" if msg.role == "user" else "model"

        # 1. Expand intermediate tool steps from ToolExecution table
        if msg.role == "model" and getattr(msg, "tool_executions", None):
            try:
                executions = sorted(msg.tool_executions, key=lambda x: x.id)

                steps = []
                current_step = None
                for exc in executions:
                    if current_step is None or exc.thought != current_step["thought"]:
                        if current_step:
                            steps.append(current_step)
                        current_step = {"thought": exc.thought, "tool_calls": []}
                    current_step["tool_calls"].append(exc)
                if current_step:
                    steps.append(current_step)

                for step in steps:
                    model_parts = []
                    tool_parts = []
                    for exc in step["tool_calls"]:
                        # Synthetic call ID for Anthropic tool_use/tool_result pairing
                        call_id = f"toolu_{exc.id}"
                        model_parts.append(LLMFunctionCallPart(
                            name=exc.tool_name,
                            args=exc.arguments,
                            call_id=call_id,
                        ))
                        result_data = exc.result
                        if exc.status == "failed":
                            result_data = {"error": exc.error}
                        else:
                            result_data = _truncate_tool_result(result_data)
                        tool_parts.append(LLMFunctionResponsePart(
                            name=exc.tool_name,
                            response=result_data,
                            call_id=call_id,
                        ))

                    if model_parts:
                        history.append(LLMMessage(role="model", parts=model_parts))
                    if tool_parts:
                        history.append(LLMMessage(role="tool", parts=tool_parts))

            except Exception as e:
                from app.core.logging import get_logger
                get_logger(__name__).warning(
                    f"Failed to expand tool_executions for msg {msg.id}: {e}"
                )

        # 2. Legacy meta_data check (backward compatibility)
        elif msg.role == "model" and msg.meta_data and isinstance(msg.meta_data, list):
            try:
                for i, step in enumerate(msg.meta_data):
                    model_parts = []
                    tool_parts = []
                    tool_calls_data = step.get("tool_calls", [])
                    for j, tc in enumerate(tool_calls_data):
                        call_id = f"legacy_{msg.id}_{i}_{j}"
                        model_parts.append(LLMFunctionCallPart(
                            name=tc["name"],
                            args=tc["args"],
                            call_id=call_id,
                        ))
                        result_data = tc.get("result")
                        if tc.get("status") == "failed":
                            result_data = {"error": tc.get("error")}
                        else:
                            result_data = _truncate_tool_result(result_data)
                        tool_parts.append(LLMFunctionResponsePart(
                            name=tc["name"],
                            response=result_data,
                            call_id=call_id,
                        ))

                    if model_parts:
                        history.append(LLMMessage(role="model", parts=model_parts))
                    if tool_parts:
                        history.append(LLMMessage(role="tool", parts=tool_parts))

            except Exception as e:
                from app.core.logging import get_logger
                get_logger(__name__).warning(
                    f"Failed to expand message metadata for msg {msg.id}: {e}"
                )

        # 3. Add the final message content
        if msg.content:
            history.append(LLMMessage(role=role, parts=[LLMTextPart(text=msg.content)]))

    # Append the current user message if not already present
    last_part = history[-1].parts[0] if (history and history[-1].parts) else None
    if not history or not (isinstance(last_part, LLMTextPart) and last_part.text == user_message):
        history.append(LLMMessage(role="user", parts=[LLMTextPart(text=user_message)]))

    return history
