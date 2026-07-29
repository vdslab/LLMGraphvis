import asyncio
import time
from collections import deque
from typing import AsyncGenerator

from fastapi import Request

# Global event broadcasters
# Key: chat_id, Value: Broadcaster
event_broadcasters = {}

# Events emitted before the first subscriber connects are buffered up to this
# many entries and replayed on subscribe, so the client doesn't lose the
# beginning of a stream that started between POST /process and GET /stream.
PENDING_BUFFER_SIZE = 200

# Broadcasters idle longer than this are pruned from event_broadcasters.
# Producers hold a direct reference for the duration of a background task,
# so eviction must wait until the task is certainly finished.
IDLE_EVICTION_SECONDS = 3600


class Broadcaster:
    def __init__(self):
        self._subscribers = set()
        self._pending = deque(maxlen=PENDING_BUFFER_SIZE)
        self.last_activity = time.monotonic()

    async def subscribe(self) -> asyncio.Queue:
        self.last_activity = time.monotonic()
        queue = asyncio.Queue()
        # Replay events emitted while nobody was listening.
        while self._pending:
            queue.put_nowait(self._pending.popleft())
        self._subscribers.add(queue)
        return queue

    async def unsubscribe(self, queue: asyncio.Queue):
        self.last_activity = time.monotonic()
        if queue in self._subscribers:
            self._subscribers.remove(queue)

    async def put(self, event: dict):
        """Broadcast event to all subscribers"""
        self.last_activity = time.monotonic()
        if not self._subscribers:
            self._pending.append(event)
            return

        # Create tasks for putting to all queues to avoid blocking
        for queue in self._subscribers:
            await queue.put(event)


def _prune_idle_broadcasters():
    now = time.monotonic()
    for chat_id in list(event_broadcasters):
        broadcaster = event_broadcasters[chat_id]
        if (
            not broadcaster._subscribers
            and now - broadcaster.last_activity > IDLE_EVICTION_SECONDS
        ):
            del event_broadcasters[chat_id]


async def get_event_queue(chat_id: int) -> Broadcaster:
    """
    Returns a Broadcaster object.
    Maintains compatibility with code calling queue.put()
    because Broadcaster has a put() method.
    """
    _prune_idle_broadcasters()
    if chat_id not in event_broadcasters:
        event_broadcasters[chat_id] = Broadcaster()
    return event_broadcasters[chat_id]


async def event_generator(chat_id: int, request: Request) -> AsyncGenerator[dict, None]:
    """Generate SSE events for a chat"""
    broadcaster = await get_event_queue(chat_id)
    queue = await broadcaster.subscribe()

    try:
        while True:
            if await request.is_disconnected():
                break
            try:
                event = await asyncio.wait_for(queue.get(), timeout=1.0)
                yield event
            except asyncio.TimeoutError:
                continue
    finally:
        await broadcaster.unsubscribe(queue)
