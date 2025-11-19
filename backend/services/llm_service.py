import asyncio
import json
from typing import AsyncGenerator
from fastapi import Request
from sqlalchemy.orm import Session
from google import genai
from google.genai import types
import os
from dotenv import load_dotenv
import models
from services import network_service

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# Global event queues for SSE
# Key: chat_id, Value: asyncio.Queue
event_queues = {}

async def get_event_queue(chat_id: int) -> asyncio.Queue:
    if chat_id not in event_queues:
        event_queues[chat_id] = asyncio.Queue()
    return event_queues[chat_id]

async def process_chat(chat_id: int, user_message: str, db: Session):
    queue = await get_event_queue(chat_id)
    
    # 1. Notify: Thinking
    await queue.put({"event": "thinking_stream", "data": json.dumps({"content": "Thinking..."})})
    
    try:
        # 1. Notify thinking start
        await queue.put({"event": "thinking_stream", "data": "ユーザーの意図を解釈中..."})
        
        # 2. Call LLM (simplified for now)
        # In a real implementation, we would use the tools and history
        response = client.models.generate_content(
            model="gemini-2.0-flash-exp",
            contents=user_message,
            config=types.GenerateContentConfig(
                tools=[], # TODO: Add tools
            )
        )
        
        # 3. Simulate tool execution (placeholder)
        # await queue.put({"event": "tool_execution", "data": {"tool": "list_attributes", "status": "started"}})
        # await asyncio.sleep(1)
        # await queue.put({"event": "tool_execution", "data": {"tool": "list_attributes", "status": "completed"}})
        
        # 4. Send final response
        await queue.put({"event": "message", "data": {"role": "assistant", "content": response.text}})
        
    except Exception as e:
        await queue.put({"event": "error", "data": str(e)})

async def event_generator(chat_id: int, request: Request) -> AsyncGenerator[dict, None]:
    queue = await get_event_queue(chat_id)
    
    while True:
        if await request.is_disconnected():
            break
            
        try:
            # Wait for event with timeout to allow checking for disconnect
            event = await asyncio.wait_for(queue.get(), timeout=1.0)
            yield event
        except asyncio.TimeoutError:
            continue
