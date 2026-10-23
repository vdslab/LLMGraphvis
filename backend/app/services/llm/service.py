import json
from typing import Any, List, Tuple

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from common import models

from . import context, emitters, engine, events, history, markup
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


def _error_reply(e: BaseException) -> str:
    """The stored reply for a failed turn: an error card, not a raw repr.

    Provider SDK errors carry a readable `message` and an HTTP code and status
    next to a repr of the whole response body; the card shows the former and
    keeps the latter as folded detail.
    """
    if hasattr(e, "exceptions"):  # an exception group: list its members
        return markup.error_block("Error", _format_exception_message(e))
    code = getattr(e, "code", None) or getattr(e, "status_code", None)
    status = getattr(e, "status", None)
    title = " ".join(
        str(part)
        for part in (type(e).__name__, code, status)
        if isinstance(part, (int, str)) and part
    )
    message = getattr(e, "message", None)
    summary = message if isinstance(message, str) and message.strip() else str(e)
    return markup.error_block(title, summary or type(e).__name__, str(e))


async def process_chat(
    chat_id: int,
    user_message: str,
    db: Session,
    *,
    resumed_from_input: bool = False,
) -> Tuple[str, List[Any], UsageData, str, str]:
    """Process a chat message with the configured LLM provider and its tools."""
    logger.info(f"Processing chat_id={chat_id}, message='{user_message[:50]}...'")
    queue = await events.get_event_queue(chat_id)
    agent = None

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
        network_large = False
        try:
            context_summary, network_large = await context.build_turn_context(
                network_id
            )
            if context_summary:
                logger.info("Injected Context Summary into System Prompt")
        except Exception as e:
            logger.warning(f"Failed to build context summary: {e}")

        # Tell the UI the turn has started. This is our status line, not the
        # model's reasoning, so it goes out as `progress` — see emitters.py.
        await emitters.emit_progress(queue, "Analyzing your request")

        # 2. Delegate to GraphVisAgent, honoring the chat's pin, else the user's default
        provider_name, model_name = engine.resolve_chat_model(chat)
        agent = engine.GraphVisAgent(
            db, provider_name=provider_name, model_name=model_name
        )

        final_response_text, execution_log, total_usage = await agent.process_turn(
            history=chat_history,
            queue=queue,
            chat_id=chat_id,
            network_id=network_id,
            context_summary=context_summary,
            network_large=network_large,
            user_text=user_message,
            resumed_from_input=resumed_from_input,
        )

        return (
            final_response_text,
            execution_log,
            total_usage,
            agent.provider_name,
            agent.provider.model_name,
        )

    except Exception as e:
        logger.exception(f"Error in process_chat: {e}")
        await queue.put({"event": "agent_error", "data": json.dumps(str(e))})

        error_reply = _error_reply(e)
        # Tokens spent before the failure were still billed.
        if agent is not None:
            return (
                error_reply,
                [],
                agent.turn_usage,
                agent.provider_name,
                agent.provider.model_name,
            )
        return error_reply, [], UsageData(), "", ""
