"""Keep per-node results a size the model can read (ADR 0024).

A tool that measures every node would otherwise return one entry per node,
and that result is re-sent on every later model request. These helpers turn a
full `{node: value}` map into its shape plus the entries a question usually
turns on, while always saying how much was left out.
"""

import statistics
from typing import Any, Dict, Hashable, Mapping, Optional

# Integer-valued metrics with at most this many distinct values also report
# their full histogram, which is small and often the actual answer.
MAX_DISTRIBUTION_BINS = 30


def summarize_values(values: Mapping[Hashable, float]) -> Dict[str, Any]:
    """Distribution facts about a numeric map, independent of its size."""
    numbers = [v for v in values.values() if isinstance(v, (int, float))]
    if not numbers:
        return {"count": len(values)}
    summary: Dict[str, Any] = {
        "count": len(values),
        "min": min(numbers),
        "max": max(numbers),
        "mean": round(statistics.fmean(numbers), 6),
        "median": statistics.median(numbers),
    }
    if all(float(v).is_integer() for v in numbers):
        histogram: Dict[str, int] = {}
        for v in sorted(numbers):
            key = str(int(v))
            histogram[key] = histogram.get(key, 0) + 1
        if len(histogram) <= MAX_DISTRIBUTION_BINS:
            summary["distribution"] = histogram
    return summary


def limit_values(
    values: Mapping[Hashable, Any],
    limit: Optional[int],
    *,
    ascending: bool = False,
) -> Dict[Hashable, Any]:
    """The `limit` most extreme entries, ordered; everything when limit is None."""
    ordered = sorted(values.items(), key=lambda kv: kv[1], reverse=not ascending)
    if limit is not None:
        ordered = ordered[:limit]
    return dict(ordered)


def shaped_per_node(
    values: Mapping[Hashable, Any],
    limit: Optional[int],
    *,
    key: str,
    ascending: bool = False,
) -> Dict[str, Any]:
    """`{key: limited map, summary, returned_count, omitted}` for one metric."""
    shown = limit_values(values, limit, ascending=ascending)
    return {
        key: shown,
        "summary": summarize_values(values),
        "returned_count": len(shown),
        "omitted": len(values) - len(shown),
        "order": "ascending" if ascending else "descending",
    }
