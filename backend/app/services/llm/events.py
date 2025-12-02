import asyncio
import json
from typing import AsyncGenerator
from fastapi import Request

# Global event queues for SSE
# Key: chat_id, Value: asyncio.Queue
event_queues = {}

async def get_event_queue(chat_id: int) -> asyncio.Queue:
    if chat_id not in event_queues:
        event_queues[chat_id] = asyncio.Queue()
    return event_queues[chat_id]

async def event_generator(chat_id: int, request: Request) -> AsyncGenerator[dict, None]:
    """Generate SSE events for a chat"""
    queue = await get_event_queue(chat_id)
    while True:
        if await request.is_disconnected(): break
        try:
            event = await asyncio.wait_for(queue.get(), timeout=1.0)
            yield event
        except asyncio.TimeoutError:
            continue
