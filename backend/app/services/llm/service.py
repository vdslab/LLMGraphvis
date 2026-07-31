import json
from typing import Any, List, Tuple

from sqlalchemy.orm import Session

from common import models
from app.core.logging import get_logger

from . import engine, emitters, events, history, local_tools, mcp_client, context
from .providers.types import UsageData

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
        # The summary is appended to the system prompt (see engine.process_turn)
        # so the agent always knows the current network's contents, regardless
        # of what the user asked.
        context_summary = ""
        try:
            context_summary = await context.build_context_summary(network_id)
            if context_summary:
                logger.info("Injected Context Summary into System Prompt")
        except Exception as e:
            logger.warning(f"Failed to build context summary: {e}")

        # Tell the UI the turn has started. This is our status line, not the
        # model's reasoning, so it goes out as `progress` — see emitters.py.
        await emitters.emit_progress(queue, "Analyzing your request")

        # 2. Delegate to GraphVisAgent, honoring this chat's pinned provider/model (if any)
        agent = engine.GraphVisAgent(db, provider_name=chat.provider, model_name=chat.model)

        final_response_text, execution_log, total_usage = await agent.process_turn(
            history=chat_history,
            queue=queue,
            chat_id=chat_id,
            network_id=network_id,
            context_summary=context_summary,
            user_text=user_message,
        )

        return final_response_text, execution_log, total_usage, agent.provider_name, agent.provider.model_name

    except Exception as e:
        logger.exception(f"Error in process_chat: {e}")
        await queue.put({"event": "error", "data": json.dumps(str(e))})

        error_msg = _format_exception_message(e)
        return f"I encountered an error: {error_msg}", [], UsageData(), "", ""
