"""Structured trace of one agent turn, appended as JSONL (ADR 0032).

Each line is one event; `turn_id` groups the events of a turn and `seq` orders
them. The trace only observes: a write that fails is logged and dropped, never
raised into the turn. `scripts/analyze_turns.py` reads these files.

Environment:
    AGENT_TRACE=0      disable tracing
    AGENT_TRACE_DIR    directory for `<YYYY-MM-DD>.jsonl` (default `backend/logs/turns`)
"""

import json
import os
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from app.core.logging import get_logger

logger = get_logger(__name__)

_DEFAULT_DIR = Path(__file__).resolve().parents[3] / "logs" / "turns"
# Long enough to read what the model said or a tool returned, short enough that
# a trace stays an index into the conversation rather than a copy of it.
TEXT_LIMIT = 600
VALUE_LIMIT = 1200

_write_lock = threading.Lock()


def enabled() -> bool:
    value = os.getenv("AGENT_TRACE", "1").strip().lower()
    return value not in {"0", "false", "off", "no"}


def trace_dir() -> Path:
    configured = os.getenv("AGENT_TRACE_DIR")
    return Path(configured) if configured else _DEFAULT_DIR


def clip(text: Optional[str], limit: int = TEXT_LIMIT) -> Optional[str]:
    if text is None:
        return None
    if len(text) <= limit:
        return text
    return f"{text[:limit]}… (+{len(text) - limit} chars)"


def clip_value(value: Any, limit: int = VALUE_LIMIT) -> Any:
    """A JSON-safe value, replaced by a clipped string when it is too large."""
    try:
        encoded = json.dumps(value, ensure_ascii=False, default=str)
    except Exception:
        return clip(repr(value), limit)
    if len(encoded) <= limit:
        return json.loads(encoded)
    return clip(encoded, limit)


class TurnTrace:
    """Appends the events of one turn to the day's trace file."""

    def __init__(self, chat_id: Any = None, network_id: Any = None) -> None:
        self.turn_id = uuid.uuid4().hex[:12]
        self.chat_id = chat_id
        self.network_id = network_id
        self._seq = 0
        self._started = time.monotonic()
        self.active = enabled()

    def elapsed_ms(self) -> int:
        return int((time.monotonic() - self._started) * 1000)

    def emit(self, event: str, **fields: Any) -> None:
        if not self.active:
            return
        self._seq += 1
        record: Dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "turn_id": self.turn_id,
            "seq": self._seq,
            "event": event,
            "chat_id": self.chat_id,
            "network_id": self.network_id,
            "elapsed_ms": self.elapsed_ms(),
            **fields,
        }
        try:
            line = json.dumps(record, ensure_ascii=False, default=str)
            directory = trace_dir()
            directory.mkdir(parents=True, exist_ok=True)
            path = directory / f"{datetime.now().strftime('%Y-%m-%d')}.jsonl"
            with _write_lock, path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        except Exception as exc:  # Observability must never break a turn.
            logger.warning("Turn trace write failed (%s); disabling for this turn", exc)
            self.active = False


class _NullTrace(TurnTrace):
    def __init__(self) -> None:
        super().__init__()
        self.active = False


NULL_TRACE = _NullTrace()
