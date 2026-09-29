"""Totals of stored LLM usage, per chat and per user (ADR 0025)."""

from collections import OrderedDict
from datetime import datetime
from typing import Any, Dict, Iterable, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.orm import Session

from common import models

_COUNTS = (
    "input_tokens",
    "output_tokens",
    "cached_input_tokens",
    "cache_write_tokens",
    "reasoning_tokens",
)


def _empty_totals() -> Dict[str, Any]:
    totals: Dict[str, Any] = {name: 0 for name in _COUNTS}
    totals.update(
        estimated_cost_usd=0.0, unpriced_count=0, task_count=0, request_count=0
    )
    return totals


def _add(totals: Dict[str, Any], row: models.LlmUsage) -> None:
    for name in _COUNTS:
        totals[name] += getattr(row, name) or 0
    if row.estimated_cost_usd is None:
        totals["unpriced_count"] += 1
    else:
        totals["estimated_cost_usd"] += row.estimated_cost_usd
    totals["task_count"] += 1
    totals["request_count"] += row.iteration_count or 1


def summarize(rows: Iterable[models.LlmUsage]) -> Dict[str, Any]:
    totals = _empty_totals()
    for row in rows:
        _add(totals, row)
    return totals


def chat_usage(db: Session, chat_id: int) -> Dict[str, Any]:
    """Every usage entry of a chat, oldest first, with their totals."""
    rows = (
        db.query(models.LlmUsage)
        .filter(models.LlmUsage.chat_id == chat_id)
        .order_by(models.LlmUsage.created_at.asc(), models.LlmUsage.id.asc())
        .all()
    )
    entries = [
        {
            "id": row.id,
            "message_id": row.message_id,
            "chat_id": row.chat_id,
            "purpose": row.purpose,
            "provider": row.provider,
            "model": row.model,
            **{name: getattr(row, name) or 0 for name in _COUNTS},
            "iteration_count": row.iteration_count or 1,
            "calls": row.calls or [],
            "estimated_cost_usd": row.estimated_cost_usd,
            "created_at": row.created_at,
        }
        for row in rows
    ]
    return {"totals": summarize(rows), "entries": entries}


def _zone(tz: Optional[str]) -> ZoneInfo:
    try:
        return ZoneInfo(tz or "UTC")
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


def user_usage(
    db: Session,
    user_id: int,
    since: Optional[datetime] = None,
    tz: Optional[str] = None,
) -> Dict[str, Any]:
    """A user's usage since `since`, totalled overall, per model, per chat and per day.

    Days are calendar days in `tz` (an IANA name; UTC when unknown). Models and
    chats are ordered by cost, then by tokens; days oldest first.
    """
    query = (
        db.query(models.LlmUsage, models.Chat.name)
        .outerjoin(models.Chat, models.Chat.id == models.LlmUsage.chat_id)
        .filter(models.LlmUsage.user_id == user_id)
    )
    if since is not None:
        query = query.filter(models.LlmUsage.created_at >= since)
    results = query.order_by(models.LlmUsage.created_at.asc()).all()

    zone = _zone(tz)
    totals = _empty_totals()
    by_model: Dict[tuple, Dict[str, Any]] = {}
    by_chat: Dict[Optional[int], Dict[str, Any]] = {}
    by_day: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()

    for row, chat_name in results:
        _add(totals, row)

        model_key = (row.provider, row.model)
        if model_key not in by_model:
            by_model[model_key] = {
                **_empty_totals(),
                "provider": row.provider,
                "model": row.model,
            }
        _add(by_model[model_key], row)

        if row.chat_id not in by_chat:
            by_chat[row.chat_id] = {
                **_empty_totals(),
                "chat_id": row.chat_id,
                "chat_name": chat_name,
            }
        _add(by_chat[row.chat_id], row)

        created = row.created_at
        day = (created.astimezone(zone) if created.tzinfo else created).date()
        key = day.isoformat()
        if key not in by_day:
            by_day[key] = {**_empty_totals(), "date": key}
        _add(by_day[key], row)

    def by_cost(item: Dict[str, Any]) -> tuple:
        return (
            -item["estimated_cost_usd"],
            -(item["input_tokens"] + item["output_tokens"]),
        )

    return {
        "since": since,
        "totals": totals,
        "by_model": sorted(by_model.values(), key=by_cost),
        "by_chat": sorted(by_chat.values(), key=by_cost),
        "by_day": list(by_day.values()),
    }
