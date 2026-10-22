"""Persisting and reporting LLM token usage (ADR 0025)."""

from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from common import models

from .pricing import estimate_cost_usd
from .providers.types import TurnUsage, UsageData

PURPOSE_AGENT_TURN = "agent_turn"
PURPOSE_TITLE = "title"


def usage_payload(usage: UsageData, provider: str, model: str) -> Dict[str, Any]:
    """The usage counts, estimated cost and model, as sent to the frontend."""
    return {
        **usage.as_dict(),
        "estimated_cost_usd": estimate_cost_usd(model, usage, provider=provider),
        "provider": provider,
        "model": model,
    }


def record_usage(
    db: Session,
    usage: UsageData,
    *,
    provider: str,
    model: str,
    chat_id: Optional[int] = None,
    message_id: Optional[int] = None,
    purpose: str = PURPOSE_AGENT_TURN,
) -> Optional[models.LlmUsage]:
    """Store one task's usage. Returns None, storing nothing, if no tokens were used.

    The caller commits. `user_id` is taken from the chat so every row can be
    totalled per user even after its message is gone.
    """
    if usage.is_empty or not provider:
        return None
    user_id = None
    if chat_id is not None:
        user_id = (
            db.query(models.Chat.user_id).filter(models.Chat.id == chat_id).scalar()
        )
    calls = usage.calls if isinstance(usage, TurnUsage) else [usage.as_dict()]
    row = models.LlmUsage(
        message_id=message_id,
        chat_id=chat_id,
        user_id=user_id,
        purpose=purpose,
        provider=provider,
        model=model,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        cached_input_tokens=usage.cached_input_tokens,
        cache_write_tokens=usage.cache_write_tokens,
        reasoning_tokens=usage.reasoning_tokens,
        iteration_count=max(len(calls), 1),
        calls=calls,
        estimated_cost_usd=estimate_cost_usd(model, usage, provider=provider),
    )
    db.add(row)
    return row
