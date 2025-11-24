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
from app.core.logging import get_logger

logger = get_logger(__name__)

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

def calculate_centrality(centrality_type: str) -> Dict[str, Any]:
    """
    Calculate centrality metrics to identify important nodes.
    Use this for requests about: "popular", "friends", "connections" (degree), "bridges", "connectors" (betweenness), "influential" (eigenvector).
    
    Args:
        centrality_type: Type of centrality. Options: "degree", "betweenness", "closeness", "eigenvector"
        
    Returns:
        Status message indicating success or failure
    """
    # This is a placeholder - actual implementation will call network_service
    return {"status": "success"}

def update_visualization(layout_name: str = "spring", node_size_config: Dict[str, Any] = None, node_color_config: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Update the visual appearance (size, color, layout).
    
    IMPORTANT: If you use `node_size_config` or `node_color_config` with a specific attribute (e.g., "degree_centrality"), 
    you MUST ensure that `calculate_centrality` has been called FIRST to compute that attribute. 
    Otherwise, the visualization will not reflect the metric.
    
    Args:
        layout_name: Name of the layout algorithm. Options: "spring", "circular", "kamada_kawai", "shell", "spectral"
        node_size_config: Configuration for node sizes. Example: {"attribute": "degree_centrality", "min": 5.0, "max": 20.0}
        node_color_config: Configuration for node colors. Example: {"attribute": "community_id", "scale_type": "CATEGORICAL"}
        
    Returns:
        Visualization data including nodes and links
    """
    # This is a placeholder - actual implementation will call network_service
    return {"nodes": [], "links": []}

def apply_layout(layout_name: str) -> Dict[str, Any]:
    """
    Apply a specific layout algorithm to arrange the nodes in the visualization.
    
    Args:
        layout_name: Name of the layout algorithm. Options: "spring", "circular", "kamada_kawai", "shell", "spectral"
        
    Returns:
        Status message indicating success or failure
    """
    # This is a placeholder - actual implementation will call network_service
    return {"status": "success"}

# System instruction for the LLM
SYSTEM_INSTRUCTION = """You are a network visualization assistant.

User Request: "Show popular nodes" (or friends, connections)
Step 1: Call `calculate_centrality(centrality_type='degree')`
Step 2: Call `update_visualization(node_size_config={'attribute': 'degree_centrality', ...})`

User Request: "Show bridges"
Step 1: Call `calculate_centrality(centrality_type='betweenness')`
Step 2: Call `update_visualization(node_size_config={'attribute': 'betweenness_centrality', ...})`

User Request: "Show influential nodes"
Step 1: Call `calculate_centrality(centrality_type='eigenvector')`
Step 2: Call `update_visualization(node_size_config={'attribute': 'eigenvector_centrality', ...})`

ALWAYS perform Step 1 before Step 2.
"""

async def process_chat(chat_id: int, user_message: str, db: Session) -> str:
    """Process a chat message using Gemini API with function calling"""
    logger.info(f"Processing chat_id={chat_id}, message='{user_message[:50]}...'")
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
            role = "user" if msg.role == "user" else "model"
            history.append(types.Content(role=role, parts=[types.Part(text=msg.content)]))
        
        # Add current user message
        history.append(types.Content(role="user", parts=[types.Part(text=user_message)]))
        
        # Inject few-shot examples to guide the model
        # Example 1: Popular nodes (Degree)
        example_1 = [
            types.Content(role="user", parts=[types.Part(text="Show popular nodes")]),
            types.Content(role="model", parts=[types.Part(function_call=types.FunctionCall(name="calculate_centrality", args={"centrality_type": "degree"}))]),
            types.Content(role="function", parts=[types.Part(function_response=types.FunctionResponse(name="calculate_centrality", response={"status": "success", "message": "Calculated degree centrality."}))]),
            types.Content(role="model", parts=[types.Part(function_call=types.FunctionCall(name="update_visualization", args={"node_size_config": {"attribute": "degree_centrality", "min": 5, "max": 20}}))]),
            types.Content(role="function", parts=[types.Part(function_response=types.FunctionResponse(name="update_visualization", response={"status": "success", "message": "Visualization updated."}))])
        ]
        
        # Example 2: Bridges (Betweenness)
        example_2 = [
            types.Content(role="user", parts=[types.Part(text="Show bridges")]),
            types.Content(role="model", parts=[types.Part(function_call=types.FunctionCall(name="calculate_centrality", args={"centrality_type": "betweenness"}))]),
            types.Content(role="function", parts=[types.Part(function_response=types.FunctionResponse(name="calculate_centrality", response={"status": "success", "message": "Calculated betweenness centrality."}))]),
            types.Content(role="model", parts=[types.Part(function_call=types.FunctionCall(name="update_visualization", args={"node_size_config": {"attribute": "betweenness_centrality", "min": 5, "max": 20}}))]),
            types.Content(role="function", parts=[types.Part(function_response=types.FunctionResponse(name="update_visualization", response={"status": "success", "message": "Visualization updated."}))])
        ]
        
        # Insert examples at the beginning of history
        # Note: We insert them before the actual user conversation to set the pattern
        history = example_1 + example_2 + history

        # Notify thinking start
        await queue.put({
            "event": "thinking_stream",
            "data": json.dumps({"content": "Analyzing your request..."})
        })
        
        # Call Gemini with function calling
        logger.info("Calling Gemini API...")
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=history,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                temperature=0.7,
            ),
            tools=[
                list_attributes,
                calculate_centrality,
                update_visualization,
                apply_layout
            ],
            tool_config=types.ToolConfig(
                function_calling_config=types.FunctionCallingConfig(
                    mode="AUTO"
                )
            )
        )
        
        # Process function calls if any
        logger.info(f"Gemini Response: {response.candidates[0].content}")
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
                    logger.info(f"Executing tool: {function_name} with args: {function_args}")
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
                            
                        elif function_name == "calculate_centrality":
                            centrality_type = function_args.get("centrality_type", "degree")
                            
                            await queue.put({
                                "event": "thinking_stream",
                                "data": json.dumps({"content": f"Calculating {centrality_type} centrality..."})
                            })
                            await network_service.calculate_centrality(network_id, centrality_type)
                            
                            function_result = {"status": "success", "message": f"Calculated {centrality_type} centrality."}

                        elif function_name == "update_visualization":
                            vis_config = {
                                "layout_name": function_args.get("layout_name", "spring"),
                                "node_size_config": function_args.get("node_size_config"),
                                "node_color_config": function_args.get("node_color_config")
                            }
                            
                            await queue.put({
                                "event": "thinking_stream",
                                "data": json.dumps({"content": "Updating visualization..."})
                            })
                            
                            vis_data = await network_service.generate_visualization(network_id, vis_config)
                            
                            # Send render update
                            await queue.put({
                                "event": "render_update",
                                "data": json.dumps(vis_data)
                            })
                            
                            function_result = {"status": "success", "message": "Visualization updated."}
                        
                        elif function_name == "apply_layout":
                            layout_name = function_args.get("layout_name", "spring")
                            
                            # 1. Calculate Layout
                            await queue.put({
                                "event": "thinking_stream",
                                "data": json.dumps({"content": f"Calculating {layout_name} layout..."})
                            })
                            await network_service.calculate_layout(network_id, layout_name)
                            
                            # 2. Generate Visualization
                            await queue.put({
                                "event": "thinking_stream",
                                "data": json.dumps({"content": "Updating visualization..."})
                            })
                            
                            vis_config = {
                                "layout_name": layout_name,
                                # Keep existing size config? We don't know it here.
                                # For now, reset size or keep default?
                                # Let's just pass layout_name. Visualizer will use default size/color if not provided.
                            }
                            
                            vis_data = await network_service.generate_visualization(network_id, vis_config)
                            
                            # Send render update
                            await queue.put({
                                "event": "render_update",
                                "data": json.dumps(vis_data)
                            })
                            
                            function_result = {"status": "success", "message": f"Applied {layout_name} layout."}
                            
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
                        logger.error(f"Tool execution failed: {e}")
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
        
        if not response_text:
            response_text = "I have processed your request."
            
        return response_text
        
    except Exception as e:
        logger.error(f"Error in process_chat: {e}")
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