import asyncio
import json
from typing import AsyncGenerator
from fastapi import Request

# Global event broadcasters
# Key: chat_id, Value: Broadcaster
# Trigger reload
event_broadcasters = {}

class Broadcaster:
    def __init__(self):
        self._subscribers = set()

    async def subscribe(self) -> asyncio.Queue:
        queue = asyncio.Queue()
        self._subscribers.add(queue)
        return queue

    async def unsubscribe(self, queue: asyncio.Queue):
        if queue in self._subscribers:
            self._subscribers.remove(queue)

    async def put(self, event: dict):
        """Broadcast event to all subscribers"""
        if not self._subscribers:
            return
        
        # Create tasks for putting to all queues to avoid blocking
        for queue in self._subscribers:
            await queue.put(event)

async def get_event_queue(chat_id: int) -> Broadcaster:
    """
    Returns a Broadcaster object.
    Maintains compatibility with code calling queue.put() 
    because Broadcaster has a put() method.
    """
    if chat_id not in event_broadcasters:
        event_broadcasters[chat_id] = Broadcaster()
    return event_broadcasters[chat_id]

async def event_generator(chat_id: int, request: Request) -> AsyncGenerator[dict, None]:
    """Generate SSE events for a chat"""
    broadcaster = await get_event_queue(chat_id)
    queue = await broadcaster.subscribe()
    
    try:
        while True:
            if await request.is_disconnected(): break
            try:
                event = await asyncio.wait_for(queue.get(), timeout=1.0)
                yield event
            except asyncio.TimeoutError:
                continue
    finally:
        await broadcaster.unsubscribe(queue)
