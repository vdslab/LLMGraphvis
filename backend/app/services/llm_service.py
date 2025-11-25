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
def list_node_attributes() -> List[str]:
    """
    List all available node attributes for the network.
    
    Returns:
        List of attribute names available in the network
    """
    # This is a placeholder - actual implementation will call network_service
    return []

def list_edge_attributes() -> List[str]:
    """
    List all available edge attributes for the network.
    
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

def generate_visualization(layout_name: str = "spring", node_size_config: Dict[str, Any] = None, node_color_config: Dict[str, Any] = None, edge_width_config: Dict[str, Any] = None, edge_color_config: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Create the visualization with specific layout, size, and color settings.
    This function MUST be called to generate the final visualization.
    
    IMPORTANT: If you use `node_size_config` or `node_color_config` with a specific attribute (e.g., "degree_centrality"), 
    you MUST ensure that `calculate_centrality` has been called FIRST to compute that attribute. 
    Otherwise, the visualization will not reflect the metric.
    
    Args:
        layout_name: Name of the layout algorithm. Options: "spring", "circular", "kamada_kawai", "shell", "spectral"
        node_size_config: Configuration for node sizes. Example: {"attribute": "degree_centrality", "min": 5.0, "max": 50.0}
        node_color_config: Configuration for node colors. Example: {"attribute": "community_id", "scale_type": "CATEGORICAL"}
        edge_width_config: Configuration for edge widths. Example: {"attribute": "weight", "min": 1.0, "max": 10.0}
        edge_color_config: Configuration for edge colors. Example: {"attribute": "type", "scale_type": "CATEGORICAL"}
        
    Returns:
        Visualization data including nodes and links
    """
    # This is a placeholder - actual implementation will call network_service
    return {"nodes": [], "links": []}

def calculate_layout(layout_name: str) -> Dict[str, Any]:
    """
    Calculate and save a specific layout algorithm to arrange the nodes.
    
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
Step 1: Call `list_node_attributes()` to see what's available.
Step 2: Call `calculate_centrality(centrality_type='degree')`
Step 3: Call `list_node_attributes()` AGAIN to confirm the new attribute is available.
Step 4: Call `generate_visualization(layout_name='spring', node_size_config={'attribute': 'degree_centrality', ...})`

User Request: "Show bridges"
Step 1: Call `list_node_attributes()`
Step 2: Call `calculate_centrality(centrality_type='betweenness')`
Step 3: Call `list_node_attributes()`
Step 4: Call `generate_visualization(layout_name='spring', node_size_config={'attribute': 'betweenness_centrality', ...})`

User Request: "Apply circular layout"
Step 1: Call `list_node_attributes()`
Step 2: Call `calculate_layout(layout_name='circular')`
Step 3: Call `list_node_attributes()`
Step 4: Call `generate_visualization(layout_name='circular')`

User Request: "Show edge weights"
Step 1: Call `list_edge_attributes()`
Step 2: Call `generate_visualization(edge_width_config={'attribute': 'weight', 'min': 1, 'max': 5})`

ALWAYS follow this pattern: List -> Calculate (if needed) -> List -> Create Visualization.

IMPORTANT: Maintain Context
When calling `generate_visualization`, you MUST maintain the previous visualization state unless the user explicitly asks to change it.
- If the user previously asked for "circular layout", KEEP `layout_name='circular'` in subsequent calls.
- If the user previously asked to size nodes by "degree", KEEP `node_size_config={'attribute': 'degree_centrality', ...}`.
- If the user previously asked to color nodes by "community", KEEP `node_color_config={'attribute': 'community_id', ...}`.
- DO NOT revert to defaults ("spring" layout, etc.) unless the user's new request specifically conflicts with the previous state or requires a reset.
- Infer the current state from the conversation history.
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
            types.Content(role="model", parts=[types.Part(function_call=types.FunctionCall(name="list_node_attributes", args={}))]),
            types.Content(role="function", parts=[types.Part(function_response=types.FunctionResponse(name="list_node_attributes", response={"attributes": ["weight"]}))]),
            types.Content(role="model", parts=[types.Part(function_call=types.FunctionCall(name="calculate_centrality", args={"centrality_type": "degree"}))]),
            types.Content(role="function", parts=[types.Part(function_response=types.FunctionResponse(name="calculate_centrality", response={"status": "success", "message": "Calculated degree centrality."}))]),
            types.Content(role="model", parts=[types.Part(function_call=types.FunctionCall(name="list_node_attributes", args={}))]),
            types.Content(role="function", parts=[types.Part(function_response=types.FunctionResponse(name="list_node_attributes", response={"attributes": ["weight", "degree_centrality"]}))]),
            types.Content(role="model", parts=[types.Part(function_call=types.FunctionCall(name="generate_visualization", args={"layout_name": "spring", "node_size_config": {"attribute": "degree_centrality", "min": 5, "max": 50}}))]),
            types.Content(role="function", parts=[types.Part(function_response=types.FunctionResponse(name="generate_visualization", response={"status": "success", "message": "Visualization created."}))])
        ]
        
        # Example 2: Bridges (Betweenness)
        example_2 = [
            types.Content(role="user", parts=[types.Part(text="Show bridges")]),
            types.Content(role="model", parts=[types.Part(function_call=types.FunctionCall(name="list_node_attributes", args={}))]),
            types.Content(role="function", parts=[types.Part(function_response=types.FunctionResponse(name="list_node_attributes", response={"attributes": ["weight"]}))]),
            types.Content(role="model", parts=[types.Part(function_call=types.FunctionCall(name="calculate_centrality", args={"centrality_type": "betweenness"}))]),
            types.Content(role="function", parts=[types.Part(function_response=types.FunctionResponse(name="calculate_centrality", response={"status": "success", "message": "Calculated betweenness centrality."}))]),
            types.Content(role="model", parts=[types.Part(function_call=types.FunctionCall(name="list_node_attributes", args={}))]),
            types.Content(role="function", parts=[types.Part(function_response=types.FunctionResponse(name="list_node_attributes", response={"attributes": ["weight", "betweenness_centrality"]}))]),
            types.Content(role="model", parts=[types.Part(function_call=types.FunctionCall(name="generate_visualization", args={"layout_name": "spring", "node_size_config": {"attribute": "betweenness_centrality", "min": 5, "max": 50}}))]),
            types.Content(role="function", parts=[types.Part(function_response=types.FunctionResponse(name="generate_visualization", response={"status": "success", "message": "Visualization created."}))])
        ]
        
        # Insert examples at the beginning of history
        # Note: We insert them before the actual user conversation to set the pattern
        history = example_1 + example_2 + history

        # Notify thinking start
        await queue.put({
            "event": "thinking_stream",
            "data": json.dumps({"content": "Analyzing your request..."})
        })
        
        # Define tools using explicit FunctionDeclaration
        list_node_attributes_tool = types.FunctionDeclaration(
            name="list_node_attributes",
            description="List all available node attributes for the network.",
            parameters=types.Schema(
                type="OBJECT",
                properties={},
            )
        )

        list_edge_attributes_tool = types.FunctionDeclaration(
            name="list_edge_attributes",
            description="List all available edge attributes for the network.",
            parameters=types.Schema(
                type="OBJECT",
                properties={},
            )
        )

        calculate_centrality_tool = types.FunctionDeclaration(
            name="calculate_centrality",
            description="Calculate centrality metrics to identify important nodes.",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "centrality_type": types.Schema(
                        type="STRING",
                        description="Type of centrality. Options: degree, betweenness, closeness, eigenvector",
                        enum=["degree", "betweenness", "closeness", "eigenvector"]
                    )
                },
                required=["centrality_type"]
            )
        )

        generate_visualization_tool = types.FunctionDeclaration(
            name="generate_visualization",
            description="Create the visualization with specific layout, size, and color settings.",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "layout_name": types.Schema(
                        type="STRING",
                        description="Name of the layout algorithm.",
                        enum=["spring", "circular", "kamada_kawai", "shell", "spectral"]
                    ),
                    "node_size_config": types.Schema(
                        type="OBJECT",
                        description="Configuration for node sizes.",
                        properties={
                            "attribute": types.Schema(type="STRING"),
                            "min": types.Schema(type="NUMBER"),
                            "max": types.Schema(type="NUMBER")
                        }
                    ),
                    "node_color_config": types.Schema(
                        type="OBJECT",
                        description="Configuration for node colors.",
                        properties={
                            "attribute": types.Schema(type="STRING"),
                            "scale_type": types.Schema(type="STRING")
                        }
                    ),
                    "edge_width_config": types.Schema(
                        type="OBJECT",
                        description="Configuration for edge widths.",
                        properties={
                            "attribute": types.Schema(type="STRING"),
                            "min": types.Schema(type="NUMBER"),
                            "max": types.Schema(type="NUMBER")
                        }
                    ),
                    "edge_color_config": types.Schema(
                        type="OBJECT",
                        description="Configuration for edge colors.",
                        properties={
                            "attribute": types.Schema(type="STRING"),
                            "scale_type": types.Schema(type="STRING")
                        }
                    )
                },
                required=["layout_name"]
            )
        )

        calculate_layout_tool = types.FunctionDeclaration(
            name="calculate_layout",
            description="Calculate and save a specific layout algorithm to arrange the nodes.",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "layout_name": types.Schema(
                        type="STRING",
                        description="Name of the layout algorithm.",
                        enum=["spring", "circular", "kamada_kawai", "shell", "spectral"]
                    )
                },
                required=["layout_name"]
            )
        )

        # Call Gemini with function calling
        logger.info("Calling Gemini API...")
        response = await client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=history,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                tools=[types.Tool(
                    function_declarations=[
                        list_node_attributes_tool,
                        list_edge_attributes_tool,
                        calculate_centrality_tool,
                        generate_visualization_tool,
                        calculate_layout_tool
                    ]
                )],
                tool_config=types.ToolConfig(
                    function_calling_config=types.FunctionCallingConfig(
                        mode="AUTO"
                    )
                ),
                temperature=0.7,
            )
        )
        
        # Process function calls if any
        logger.info(f"Gemini Response: {response.candidates[0].content}")
        print(f"DEBUG: Gemini Response: {response.candidates[0].content}")
        
        # Loop to handle multiple sequential tool calls
        current_response = response
        max_iterations = 10  # Prevent infinite loops
        iteration = 0
        
        while iteration < max_iterations:
            iteration += 1
            has_function_call = False
            
            if current_response.candidates[0].content.parts:
                for part in current_response.candidates[0].content.parts:
                    # Check if this part is a function call
                    if hasattr(part, 'function_call') and part.function_call:
                        has_function_call = True
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
                            if function_name == "list_node_attributes":
                                result = await network_service.list_node_attributes(network_id)
                                function_result = {"attributes": result}

                            elif function_name == "list_edge_attributes":
                                result = await network_service.list_edge_attributes(network_id)
                                function_result = {"attributes": result}
                                
                            elif function_name == "calculate_centrality":
                                centrality_type = function_args.get("centrality_type", "degree")
                                
                                await queue.put({
                                    "event": "thinking_stream",
                                    "data": json.dumps({"content": f"Calculating {centrality_type} centrality..."})
                                })
                                await network_service.calculate_centrality(network_id, centrality_type)
                                
                                function_result = {"status": "success", "message": f"Calculated {centrality_type} centrality."}

                            elif function_name == "generate_visualization":
                                vis_config = {
                                    "layout_name": function_args.get("layout_name", "spring"),
                                    "node_size_config": function_args.get("node_size_config"),
                                    "node_color_config": function_args.get("node_color_config"),
                                    "edge_width_config": function_args.get("edge_width_config"),
                                    "edge_color_config": function_args.get("edge_color_config")
                                }
                                
                                await queue.put({
                                    "event": "thinking_stream",
                                    "data": json.dumps({"content": "Creating visualization..."})
                                })
                                
                                vis_data = await network_service.generate_visualization(network_id, vis_config)
                                
                                # Send render update
                                await queue.put({
                                    "event": "render_update",
                                    "data": json.dumps(vis_data)
                                })
                                
                                function_result = {"status": "success", "message": "Visualization created."}
                            
                            elif function_name == "calculate_layout":
                                layout_name = function_args.get("layout_name", "spring")
                                
                                # 1. Calculate Layout
                                await queue.put({
                                    "event": "thinking_stream",
                                    "data": json.dumps({"content": f"Calculating {layout_name} layout..."})
                                })
                                await network_service.calculate_layout(network_id, layout_name)
                                
                                function_result = {"status": "success", "message": f"Calculated {layout_name} layout."}
                                
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
                        history.append(current_response.candidates[0].content)
                        history.append(types.Content(
                            role="user",
                            parts=[types.Part.from_function_response(
                                name=function_name,
                                response=function_result
                            )]
                        ))
                        
                        # Get next response from LLM
                        current_response = await client.aio.models.generate_content(
                            model="gemini-2.5-flash",
                            contents=history,
                            config=types.GenerateContentConfig(
                                system_instruction=SYSTEM_INSTRUCTION,
                                temperature=0.7,
                                tools=[types.Tool(
                                    function_declarations=[
                                        list_node_attributes_tool,
                                        list_edge_attributes_tool,
                                        calculate_centrality_tool,
                                        generate_visualization_tool,
                                        calculate_layout_tool
                                    ]
                                )],
                                tool_config=types.ToolConfig(
                                    function_calling_config=types.FunctionCallingConfig(
                                        mode="AUTO"
                                    )
                                )
                            )
                        )
                        logger.info(f"Gemini Response (iteration {iteration}): {current_response.candidates[0].content}")
                        print(f"DEBUG: Gemini Response (iteration {iteration}): {current_response.candidates[0].content}")
                        break  # Process one function call per iteration
            
            if not has_function_call:
                # No more function calls, extract text response
                response_text = current_response.text if current_response.text else "I have processed your request."
                break
        
        if iteration >= max_iterations:
            response_text = "I've completed the requested operations."
        
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