"""SSE event emitters.

Extracted from `GraphVisAgent` so that hooks — which have a queue but no agent
instance — emit the exact same event shapes the engine does. The frontend
contract lives here: see `frontend/src/hooks/useChatConnection.js` for the
consumer side of each event name.
"""

import json
from typing import Any, Dict

from .providers.types import UsageData


async def emit_message_chunk(queue: Any, text: str) -> None:
    await queue.put({"event": "message_chunk", "data": json.dumps({"content": text})})


async def emit_thinking_chunk(queue: Any, text: str) -> None:
    await queue.put({"event": "thinking_stream", "data": json.dumps({"content": text})})


async def emit_tool_event(
    queue: Any, tool: str, status: str, args_or_error: Any
) -> None:
    data: Dict[str, Any] = {"tool": tool, "status": status}
    if status == "started":
        data["args"] = args_or_error
    else:
        data["error"] = args_or_error
    await queue.put({"event": "tool_execution", "data": json.dumps(data)})


async def emit_render_update(queue: Any, vis_data: Dict) -> None:
    await queue.put({"event": "render_update", "data": json.dumps(vis_data)})


async def emit_usage_update(
    queue: Any, usage: UsageData, provider_name: str, model_name: str
) -> None:
    from .pricing import estimate_cost_usd

    cost = estimate_cost_usd(
        model_name,
        usage.input_tokens,
        usage.output_tokens,
        usage.cached_input_tokens,
        provider=provider_name,
    )
    await queue.put(
        {
            "event": "usage_update",
            "data": json.dumps(
                {
                    "input_tokens": usage.input_tokens,
                    "output_tokens": usage.output_tokens,
                    "cached_input_tokens": usage.cached_input_tokens,
                    "estimated_cost_usd": cost,
                    "provider": provider_name,
                    "model": model_name,
                }
            ),
        }
    )
