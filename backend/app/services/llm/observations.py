"""What the model sees of a tool result (ADR 0024).

Hooks and the SSE stream receive the original result. Everything here shapes
only the observation sent back to the model, so it trades completeness for a
size that does not grow with the network.

Two budgets apply:

- `truncate_tool_result` runs on every observation, in the turn that produced
  it. Long lists and large per-node maps are cut to a preview plus an explicit
  count of what was left out, so the model never mistakes a preview for the
  whole.
- `compact_past_observation` runs when an earlier turn is replayed as history.
  Those results are re-sent on every later request, so anything over
  `PAST_OBSERVATION_CHAR_BUDGET` keeps only its scalar facts.
"""

import json
import re
from typing import Any, Dict, List

MAX_LIST_ITEMS = 15
# A mapping with more scalar entries than this is treated as a per-item table
# (node -> value) rather than a record, and summarized.
MAX_MAP_ITEMS = 40
MAP_PREVIEW_ITEMS = 15
PAST_OBSERVATION_CHAR_BUDGET = 1500
PAST_STRING_CHARS = 200
PAST_NOTE = "Earlier result shortened; re-run the tool if its detail is needed."

_OMISSION = re.compile(r"\[(\d+) items omitted for brevity\]")


def _list_cardinality(items: List[Any]) -> int:
    """Recover the original size of a list truncated by older app versions."""
    if items and isinstance(items[-1], str):
        match = _OMISSION.fullmatch(items[-1])
        if match:
            return len(items) - 1 + int(match.group(1))
    return len(items)


def _is_scalar(value: Any) -> bool:
    return value is None or isinstance(value, (str, int, float, bool))


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _summarize_map(mapping: Dict[Any, Any]) -> Dict[str, Any]:
    """Replace a large key -> scalar table with its shape and a preview.

    Numeric tables keep the highest values, which is what a question about a
    per-node metric almost always turns on; other tables keep insertion order.
    """
    values = list(mapping.values())
    summary: Dict[str, Any] = {"count": len(mapping)}
    numeric = [v for v in values if _is_number(v)]
    if numeric and len(numeric) == len(values):
        summary.update(
            {
                "min": min(numeric),
                "max": max(numeric),
                "mean": round(sum(numeric) / len(numeric), 6),
            }
        )
        ranked = sorted(mapping.items(), key=lambda kv: kv[1], reverse=True)
        summary["highest"] = dict(ranked[:MAP_PREVIEW_ITEMS])
    else:
        summary["preview"] = dict(list(mapping.items())[:MAP_PREVIEW_ITEMS])
    summary["omitted"] = len(mapping) - MAP_PREVIEW_ITEMS
    summary["note"] = (
        "Per-item table summarized for brevity; query specific items "
        "(e.g. node_get_details) if their exact values matter."
    )
    return summary


def truncate_tool_result(result: Any, max_list_items: int = MAX_LIST_ITEMS) -> Any:
    """Create the compact observation stored in history and shown to the LLM.

    A rendered graph is represented semantically instead of copying node/link
    rows into every subsequent model request.
    """
    if (
        isinstance(result, dict)
        and isinstance(result.get("nodes"), list)
        and isinstance(result.get("links"), list)
    ):
        compact = {
            "rendered": True,
            "node_count": _list_cardinality(result["nodes"]),
            "link_count": _list_cardinality(result["links"]),
        }
        compact.update(
            {
                key: truncate_tool_result(value, max_list_items)
                for key, value in result.items()
                if key not in {"nodes", "links"}
            }
        )
        return compact
    if isinstance(result, list):
        if len(result) > max_list_items:
            truncated = [
                truncate_tool_result(item, max_list_items)
                for item in result[:max_list_items]
            ]
            truncated.append(
                f"[{len(result) - max_list_items} items omitted for brevity]"
            )
            return truncated
        return [truncate_tool_result(item, max_list_items) for item in result]
    if isinstance(result, dict):
        if len(result) > MAX_MAP_ITEMS and all(_is_scalar(v) for v in result.values()):
            return _summarize_map(result)
        return {k: truncate_tool_result(v, max_list_items) for k, v in result.items()}
    return result


def serialize_observation(result: Any) -> str:
    """Text form of an observation for providers that take tool results as text.

    Non-ASCII stays literal: escaping turns each Japanese character into six
    ASCII characters (`\\u30e2`), several times the tokens of the character
    itself, and this app's data and users are largely Japanese.
    """
    if isinstance(result, str):
        return result
    return json.dumps(result, ensure_ascii=False, separators=(",", ":"), default=str)


def _describe(value: Any) -> str:
    if isinstance(value, list):
        return f"<list of {_list_cardinality(value)} omitted>"
    if isinstance(value, dict):
        keys = list(value)[:8]
        more = "..." if len(value) > len(keys) else ""
        return f"<object with keys {keys}{more} omitted>"
    return "<omitted>"


def compact_past_observation(result: Any) -> Any:
    """Shrink an already-truncated observation from an earlier turn.

    Small results pass through unchanged. Larger ones keep their scalar fields
    (ids, counts, attribute names, messages) and name what was dropped, so the
    model still knows what the call established without re-reading its detail.
    """
    try:
        size = len(json.dumps(result, ensure_ascii=False, default=str))
    except (TypeError, ValueError):
        return result
    if size <= PAST_OBSERVATION_CHAR_BUDGET:
        return result
    if not isinstance(result, dict):
        text = json.dumps(result, ensure_ascii=False, default=str)
        return {
            "summary": text[:PAST_OBSERVATION_CHAR_BUDGET],
            "note": PAST_NOTE,
        }
    compact: Dict[str, Any] = {}
    for key, value in result.items():
        if isinstance(value, str) and len(value) > PAST_STRING_CHARS:
            compact[key] = value[:PAST_STRING_CHARS] + "..."
        elif _is_scalar(value):
            compact[key] = value
        else:
            compact[key] = _describe(value)
    compact["note"] = PAST_NOTE
    return compact
