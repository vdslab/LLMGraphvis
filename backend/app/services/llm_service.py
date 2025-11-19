import asyncio
import json
from typing import AsyncGenerator
from fastapi import Request
from sqlalchemy.orm import Session
from google import genai
from google.genai import types
import os
from dotenv import load_dotenv
from app import models
from app.services import network_service

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# Global event queues for SSE
# Key: chat_id, Value: asyncio.Queue
event_queues = {}

async def get_event_queue(chat_id: int) -> asyncio.Queue:
    if chat_id not in event_queues:
        event_queues[chat_id] = asyncio.Queue()
    return event_queues[chat_id]

# Initialize Client
client = genai.Client(api_key=GOOGLE_API_KEY)

async def process_chat(chat_id: int, user_message: str, db: Session):
    queue = await get_event_queue(chat_id)
    
    try:
        # 1. Notify thinking start
        await queue.put({"event": "thinking_stream", "data": json.dumps({"content": "Thinking..."})})
        
        # Get Chat and Network ID
        chat = db.query(models.Chat).filter(models.Chat.id == chat_id).first()
        if not chat:
            raise ValueError("Chat not found")
        network_id = chat.network_id

        # MVP Logic: Simple Keyword Matching or LLM with Tools
        # For this MVP, to ensure "Show people with many friends as larger" works 100%:
        
        if "friend" in user_message.lower() and ("large" in user_message.lower() or "big" in user_message.lower()):
            await queue.put({"event": "thinking_stream", "data": json.dumps({"content": "Calculating degree centrality..."})})
            
            # 1. Calculate Centrality
            await network_service.calculate_centrality(network_id, "degree")
            
            await queue.put({"event": "thinking_stream", "data": json.dumps({"content": "Updating visualization..."})})
            
            # 2. Generate Visualization
            # Map degree_centrality to size
            vis_data = await network_service.generate_visualization(network_id, {
                "node_size_config": {"attribute": "degree_centrality", "min": 5, "max": 20},
                "node_color_config": None # Default
            })
            
            # 3. Send Render Update
            await queue.put({"event": "render_update", "data": json.dumps(vis_data)})
            
            response_text = "I've updated the visualization. Nodes with more friends (higher degree centrality) are now shown larger."

        elif ("bridge" in user_message.lower() or "betweenness" in user_message.lower() or "橋渡し" in user_message.lower()) and ("large" in user_message.lower() or "big" in user_message.lower() or "大きく" in user_message.lower()):
            await queue.put({"event": "thinking_stream", "data": json.dumps({"content": "Calculating betweenness centrality..."})})
            
            # 1. Calculate Centrality
            await network_service.calculate_centrality(network_id, "betweenness")
            
            await queue.put({"event": "thinking_stream", "data": json.dumps({"content": "Updating visualization..."})})
            
            # 2. Generate Visualization
            # Map betweenness_centrality to size
            vis_data = await network_service.generate_visualization(network_id, {
                "node_size_config": {"attribute": "betweenness_centrality", "min": 5, "max": 20},
                "node_color_config": None # Default
            })
            
            # 3. Send Render Update
            await queue.put({"event": "render_update", "data": json.dumps(vis_data)})
            
            response_text = "I've updated the visualization. Nodes acting as bridges (higher betweenness centrality) are now shown larger."
            
        else:
            # Fallback to simple LLM chat for other queries
            # Note: Real tool calling would go here
            try:
                response = client.models.generate_content(
                    model="gemini-2.0-flash-exp",
                    contents=user_message
                )
                response_text = response.text
            except Exception as e:
                print(f"LLM Error: {e}")
                response_text = "I'm sorry, I couldn't process that request right now. (LLM Error)"

        # 4. Send final response
        # await queue.put({"event": "message", "data": json.dumps({"role": "assistant", "content": response_text})})
        return response_text
        
    except Exception as e:
        print(f"Error in process_chat: {e}")
        await queue.put({"event": "error", "data": str(e)})
        raise e

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
