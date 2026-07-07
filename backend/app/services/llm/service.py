import json
from typing import Any, List, Tuple

from sqlalchemy.orm import Session

from common import models
from app.core.logging import get_logger

from . import engine, events, history, local_tools, mcp_client, context
from .providers.types import LLMTextPart, UsageData

logger = get_logger(__name__)


def _format_exception_message(e: BaseException) -> str:
    try:
        if isinstance(e, BaseExceptionGroup):
            msgs = [_format_exception_message(exc) for exc in e.exceptions]
            return "; ".join(msgs)
    except NameError:
        pass
    return f"{type(e).__name__}: {str(e)}"


async def process_chat(
    chat_id: int, user_message: str, db: Session
) -> Tuple[str, List[Any], UsageData, str, str]:
    """Process a chat message using the configured LLM provider with function calling."""
    logger.info(f"Processing chat_id={chat_id}, message='{user_message[:50]}...'")
    queue = await events.get_event_queue(chat_id)

    try:
        # 1. Setup Context
        chat = db.query(models.Chat).filter(models.Chat.id == chat_id).first()
        if not chat:
            raise ValueError("Chat not found")
        network_id = chat.network_id

        # Build base history
        chat_history = history.build_history(chat_id, user_message, db)

        # --- Context Injection ---
        try:
            context_summary = await context.build_context_summary(network_id)
            if context_summary and chat_history and chat_history[-1].role == "user":
                last_parts = chat_history[-1].parts
                if last_parts and isinstance(last_parts[0], LLMTextPart) and last_parts[0].text:
                    last_parts[0].text = f"{context_summary}\n\n{last_parts[0].text}"
                    logger.info("Injected Context Summary into User Prompt")
        except Exception as e:
            logger.warning(f"Failed to inject context summary: {e}")

        # Notify thinking start
        await queue.put(
            {
                "event": "thinking_stream",
                "data": json.dumps({"content": "Analyzing your request..."}),
            }
        )

        # 2. Delegate to GraphVisAgent, honoring this chat's pinned provider/model (if any)
        agent = engine.GraphVisAgent(db, provider_name=chat.provider, model_name=chat.model)

        final_response_text, execution_log, total_usage = await agent.process_turn(
            history=chat_history,
            queue=queue,
            chat_id=chat_id,
            network_id=network_id,
        )

        return final_response_text, execution_log, total_usage, agent.provider_name, agent.provider.model_name

    except Exception as e:
        logger.exception(f"Error in process_chat: {e}")
        await queue.put({"event": "error", "data": str(e)})

        error_msg = _format_exception_message(e)
        return f"I encountered an error: {error_msg}", [], UsageData(), "", ""
