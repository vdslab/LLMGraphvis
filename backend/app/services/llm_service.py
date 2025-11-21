import asyncio
import json
from typing import AsyncGenerator, Dict, Any, List
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

# Initialize Gemini Client
client = genai.Client(api_key=GOOGLE_API_KEY)

# Define tools for network operations
def list_attributes() -> List[str]:
    """
    List all available node attributes for the network.
    
    Returns:
        List of attribute names available in the network
    """
    # This is a placeholder - actual implementation will call network_service
    return []

def visualize_centrality(centrality_type: str) -> Dict[str, Any]:
    """
    Calculate a specific centrality measure and immediately visualize it by mapping it to node size.
    
    Args:
        centrality_type: Type of centrality to calculate. Options: "degree", "betweenness", "closeness", "eigenvector"
        
    Returns:
        Status message indicating success or failure
    """
    # This is a placeholder - actual implementation will call network_service
    return {"status": "success"}

# System instruction for the LLM
SYSTEM_INSTRUCTION = """You are a network visualization assistant. You help users analyze and visualize network graphs.

You have access to tools that can manipulate and visualize the network.
IMPORTANT: You do NOT need to ask for the network ID. The system automatically applies your actions to the current network.

CRITICAL RULES:
1. When a user requests to see "friends", "connections", "popular nodes", or "bridges", you MUST use the `visualize_centrality` tool.
2. Do NOT describe what you are going to do before calling the tool. Call the tool first.
3. Only after the tool has executed should you explain what you did.

Specific Mappings:
- "friends", "connections", "popular" -> Use `visualize_centrality(centrality_type="degree")`
- "bridge", "connector", "between" -> Use `visualize_centrality(centrality_type="betweenness")`
- "influential", "pagerank" -> Use `visualize_centrality(centrality_type="eigenvector")`

Example:
User: "Show people with many friends as larger"
Assistant: [Calls visualize_centrality(centrality_type="degree")] -> "I have calculated degree centrality and updated the node sizes to reflect the number of connections."
"""

async def process_chat(chat_id: int, user_message: str, db: Session) -> str:
    """Process a chat message using Gemini API with function calling"""
    queue = await get_event_queue(chat_id)
    
    try:
        # Get Chat and Network ID
        chat = db.query(models.Chat).filter(models.Chat.id == chat_id).first()
        if not chat:
            raise ValueError("Chat not found")
        network_id = chat.network_id
        
        # Get chat history
        messages = db.query(models.ChatMessage).filter(
            models.ChatMessage.chat_id == chat_id
        ).order_by(models.ChatMessage.created_at.asc()).all()
        
        # Build conversation history
        history = []
        for msg in messages:
            history.append(types.Content(
                role=msg.role,
                parts=[types.Part.from_text(text=msg.content)]
            ))
        
        # Add current user message
        history.append(types.Content(
            role="user",
            parts=[types.Part.from_text(text=user_message)]
        ))
        
        # Notify thinking start
        await queue.put({
            "event": "thinking_stream",
            "data": json.dumps({"content": "Analyzing your request..."})
        })
        
        # Create tools list - these will be actual Python functions
        tools = [list_attributes, visualize_centrality]
        
        # Call Gemini with function calling
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=history,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                tools=tools,
                tool_config=types.ToolConfig(
                    function_calling_config=types.FunctionCallingConfig(
                        mode="ANY"
                    )
                ),
                temperature=0.7,
            )
        )
        
        # Process function calls if any
        print(f"DEBUG: Gemini Response: {response.candidates[0].content}")
        if response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                # Check if this part is a function call
                if hasattr(part, 'function_call') and part.function_call:
                    function_call = part.function_call
                    function_name = function_call.name
                    function_args = dict(function_call.args)
                    
                    # Add network_id to args if not present
                    if 'network_id' not in function_args:
                        function_args['network_id'] = network_id
                    
                    # Notify tool execution start
                    await queue.put({
                        "event": "tool_execution",
                        "data": json.dumps({
                            "tool": function_name,
                            "status": "started",
                            "args": function_args
                        })
                    })
                    
                    # Execute the actual network service call
                    try:
                        if function_name == "list_attributes":
                            result = await network_service.list_attributes(network_id)
                            function_result = result
                            
                        elif function_name == "visualize_centrality":
                            centrality_type = function_args.get("centrality_type", "degree")
                            
                            # 1. Calculate Centrality
                            await queue.put({
                                "event": "thinking_stream",
                                "data": json.dumps({"content": f"Calculating {centrality_type} centrality..."})
                            })
                            await network_service.calculate_centrality(network_id, centrality_type)
                            
                            # 2. Generate Visualization
                            await queue.put({
                                "event": "thinking_stream",
                                "data": json.dumps({"content": "Updating visualization..."})
                            })
                            
                            vis_config = {
                                "layout_name": "spring",
                                "node_size_config": {
                                    "attribute": f"{centrality_type}_centrality",
                                    "min": 5.0,
                                    "max": 20.0
                                }
                            }
                            
                            vis_data = await network_service.generate_visualization(network_id, vis_config)
                            
                            # Send render update
                            await queue.put({
                                "event": "render_update",
                                "data": json.dumps(vis_data)
                            })
                            
                            function_result = {"status": "success", "message": f"Calculated {centrality_type} centrality and updated visualization."}
                            
                        else:
                            function_result = {"error": f"Unknown function: {function_name}"}
                        
                        # Notify tool execution complete
                        await queue.put({
                            "event": "tool_execution",
                            "data": json.dumps({
                                "tool": function_name,
                                "status": "completed"
                            })
                        })
                        
                    except Exception as e:
                        error_msg = str(e)
                        await queue.put({
                            "event": "tool_execution",
                            "data": json.dumps({
                                "tool": function_name,
                                "status": "failed",
                                "error": error_msg
                            })
                        })
                        function_result = {"error": error_msg}
                    
                    # Continue conversation with function result
                    history.append(response.candidates[0].content)
                    history.append(types.Content(
                        role="user",
                        parts=[types.Part.from_function_response(
                            name=function_name,
                            response=function_result
                        )]
                    ))
                    
                    # Get final response from LLM
                    final_response = client.models.generate_content(
                        model="gemini-2.5-flash",
                        contents=history,
                        config=types.GenerateContentConfig(
                            system_instruction=SYSTEM_INSTRUCTION,
                            temperature=0.7,
                        )
                    )
                    
                    response_text = final_response.text
                else:
                    # No function call, just text response
                    response_text = response.text
        else:
            response_text = response.text
        
        return response_text
        
    except Exception as e:
        print(f"Error in process_chat: {e}")
        import traceback
        traceback.print_exc()
        await queue.put({"event": "error", "data": str(e)})
        return f"I encountered an error: {str(e)}"

async def event_generator(chat_id: int, request: Request) -> AsyncGenerator[dict, None]:
    """Generate SSE events for a chat"""
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