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

# --- Tool Definitions ---

def _get_tool_definitions() -> List[types.FunctionDeclaration]:
    """Returns the list of function declarations for the LLM."""
    return [
        types.FunctionDeclaration(
            name="list_node_attributes",
            description="List all available node attributes for the network.",
            parameters=types.Schema(type="OBJECT", properties={})
        ),
        types.FunctionDeclaration(
            name="list_edge_attributes",
            description="List all available edge attributes for the network.",
            parameters=types.Schema(type="OBJECT", properties={})
        ),
        types.FunctionDeclaration(
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
        ),
        types.FunctionDeclaration(
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
                        description="Configuration for node sizes. WARNING: The attribute MUST exist. Call calculate_centrality first if needed.",
                        properties={
                            "attribute": types.Schema(type="STRING", description="Name of the attribute (e.g., 'degree_centrality'). MUST be calculated first."),
                            "min": types.Schema(type="NUMBER"),
                            "max": types.Schema(type="NUMBER")
                        }
                    ),
                    "node_color_config": types.Schema(
                        type="OBJECT",
                        description="Configuration for node colors.",
                        properties={
                            "attribute": types.Schema(type="STRING"),
                            "scale_type": types.Schema(type="STRING", description="LINEAR, CATEGORICAL, or RANKING"),
                            "ranking_rules": types.Schema(
                                type="ARRAY",
                                description="Rules for RANKING scale_type. Processed in order. e.g. [{'top': 1, 'color': 'red'}, {'top': 5, 'color': 'blue'}] means top 1 is red, next 5 are blue.",
                                items=types.Schema(
                                    type="OBJECT",
                                    properties={
                                        "top": types.Schema(type="INTEGER", description="Number of nodes to apply this color to (taking from the top of the remaining list)."),
                                        "color": types.Schema(type="STRING", description="Color for these nodes.")
                                    }
                                )
                            ),
                            "default_color": types.Schema(type="STRING", description="Color for nodes not matching any rule.")
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
                    ),
                    "overlay_network_id": types.Schema(
                        type="INTEGER",
                        description="ID of a subgraph to overlay/highlight on the main visualization."
                    ),
                    "overlay_config": types.Schema(
                        type="OBJECT",
                        description="Configuration for overlay colors.",
                        properties={
                            "highlight_color": types.Schema(type="STRING", description="Color for the highlighted subgraph nodes/edges (default: #FF4500)."),
                            "dimmed_color": types.Schema(type="STRING", description="Color for the non-highlighted nodes/edges (default: #B0B0B0).")
                        }
                    ),
                    "custom_node_colors": types.Schema(
                        type="ARRAY",
                        description="List of specific node-color pairs. Overrides all other color settings for these nodes. Useful for highlighting specific nodes identified by the LLM.",
                        items=types.Schema(
                            type="OBJECT",
                            properties={
                                "node_id": types.Schema(type="STRING"),
                                "color": types.Schema(type="STRING")
                            },
                            required=["node_id", "color"]
                        )
                    )
                },
                required=["layout_name"]
            )
        ),
        types.FunctionDeclaration(
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
        ),
        types.FunctionDeclaration(
            name="create_ego_network",
            description="Create an ego network subgraph centered on a specific node.",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "center_node_id": types.Schema(type="STRING", description="ID of the center node."),
                    "radius": types.Schema(type="INTEGER", description="Radius of the ego network (default 1).")
                },
                required=["center_node_id"]
            )
        ),
        types.FunctionDeclaration(
            name="create_subgraph_from_nodes",
            description="Create a subgraph containing only the specified nodes.",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "node_ids": types.Schema(
                        type="ARRAY",
                        items=types.Schema(type="STRING"),
                        description="List of node IDs to include."
                    )
                },
                required=["node_ids"]
            )
        ),
        types.FunctionDeclaration(
            name="create_path_subgraph",
            description="Create a subgraph containing the shortest path between two nodes.",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "source_node_id": types.Schema(type="STRING", description="Start node ID."),
                    "target_node_id": types.Schema(type="STRING", description="End node ID.")
                },
                required=["source_node_id", "target_node_id"]
            )
        ),
        types.FunctionDeclaration(
            name="create_k_core_subgraph",
            description="Create a k-core subgraph (maximal subgraph where every node has degree >= k).",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "k": types.Schema(type="INTEGER", description="The core number k.")
                },
                required=["k"]
            )
        ),
        types.FunctionDeclaration(
            name="create_largest_component_subgraph",
            description="Create a subgraph from the largest connected component.",
            parameters=types.Schema(type="OBJECT", properties={})
        ),
        types.FunctionDeclaration(
            name="get_subgraphs",
            description="List all available subgraphs for the current network.",
            parameters=types.Schema(type="OBJECT", properties={})
        ),
        types.FunctionDeclaration(
            name="get_top_nodes",
            description="Get the top k nodes based on a centrality metric. Useful for identifying key nodes to focus on.",
            parameters=types.Schema(
                type="OBJECT",
                properties={
                    "metric": types.Schema(
                        type="STRING",
                        description="Centrality metric to use. Options: degree, betweenness, closeness, eigenvector",
                        enum=["degree", "betweenness", "closeness", "eigenvector"]
                    ),
                    "k": types.Schema(type="INTEGER", description="Number of top nodes to return (default 10).")
                },
                required=["metric"]
            )
        )
    ]

# --- System Instruction ---

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

User Request: "Color the top 2 nodes by degree blue, and the rest gray"
Step 1: Call `calculate_centrality(centrality_type='degree')` (if not already done)
Step 2: Call `generate_visualization(layout_name='spring', node_color_config={'attribute': 'degree_centrality', 'scale_type': 'RANKING', 'ranking_rules': [{'top': 2, 'color': 'blue'}], 'default_color': 'gray'})`

User Request: "Create an ego network for the most central node"
Step 1: Call `get_top_nodes(metric='degree', k=1)` to find the node ID (e.g., 'n1').
Step 2: Call `create_ego_network(center_node_id='n1', radius=1)`
Step 3: Call `generate_visualization(overlay_network_id=subgraph_id)`

User Request: "Create a subgraph for the top 3 nodes by betweenness"
Step 1: Call `get_top_nodes(metric='betweenness', k=3)` to get node IDs (e.g., ['n1', 'n2', 'n3']).
Step 2: Call `create_subgraph_from_nodes(node_ids=['n1', 'n2', 'n3'])`
Step 3: Call `generate_visualization(overlay_network_id=subgraph_id)`

User Request: "Color the most central node Red, its neighbors Blue, and the rest Gray"
Step 1: Call `get_top_nodes(metric='degree', k=1)` -> 'n1'
Step 2: Call `create_ego_network(center_node_id='n1', radius=1)` -> subgraph_id
Step 3: Call `generate_visualization(
    overlay_network_id=subgraph_id,
    custom_node_colors=[{'node_id': 'n1', 'color': 'red'}],
    overlay_config={'highlight_color': 'blue', 'dimmed_color': 'gray'}
)`

ALWAYS follow this pattern: List -> Calculate (if needed) -> List -> Create Visualization.

CRITICAL RULES:
1. You MUST call `calculate_centrality` BEFORE trying to visualize centrality (degree, betweenness, etc.). The attributes 'degree_centrality', 'betweenness_centrality', etc. DO NOT EXIST until you calculate them.
2. You CANNOT skip the calculation step if the user asks for a metric that hasn't been calculated yet.
3. Always verify available attributes with `list_node_attributes` before generating visualization.

IMPORTANT: Maintain Context
When calling `generate_visualization`, you MUST maintain the previous visualization state unless the user explicitly asks to change it.
- If the user previously asked for "circular layout", KEEP `layout_name='circular'` in subsequent calls.
- If the user previously asked to size nodes by "degree", KEEP `node_size_config={'attribute': 'degree_centrality', ...}`.
- If the user previously asked to color nodes by "community", KEEP `node_color_config={'attribute': 'community_id', ...}`.
- DO NOT revert to defaults ("spring" layout, etc.) unless the user's new request specifically conflicts with the previous state or requires a reset.
- Infer the current state from the conversation history.

IMPORTANT: Final Response
After completing the tool execution loop, provide a final response to the user. This response MUST include:
1. A summary of the actions you took (e.g., "I calculated degree centrality...").
2. The reasoning behind your decisions (e.g., "...to identify the most connected nodes in the network.").
3. Explain WHY you chose specific parameters or tools.

CRITICAL: Language Matching
You MUST respond in the same language as the user's input.
- If the user asks in Japanese, respond in Japanese.
- If the user asks in English, respond in English.
"""

# --- Main Logic ---

async def process_chat(chat_id: int, user_message: str, db: Session) -> str:
    """Process a chat message using Gemini API with function calling"""
    logger.info(f"Processing chat_id={chat_id}, message='{user_message[:50]}...'")
    queue = await get_event_queue(chat_id)
    
    try:
        # 1. Setup Context
        chat = db.query(models.Chat).filter(models.Chat.id == chat_id).first()
        if not chat: raise ValueError("Chat not found")
        network_id = chat.network_id
        
        history = _build_history(chat_id, user_message, db)
        
        
        # Notify thinking start
        await queue.put({
            "event": "thinking_stream",
            "data": json.dumps({"content": "Analyzing your request..."})
        })
        
        # 2. Initial LLM Call
        tools = _get_tool_definitions()
        tool_config = types.ToolConfig(function_calling_config=types.FunctionCallingConfig(mode="AUTO"))
        
        logger.info("Calling Gemini API...")
        
        # Log Request Details
        logger.info(f"--- Gemini API Request ---")
        logger.info(f"Model: gemini-2.5-flash")
        logger.info(f"System Instruction: {SYSTEM_INSTRUCTION[:100]}...")
        logger.info(f"Tools: {[t.name for t in tools]}")
        logger.info(f"History (Last 2): {history[-2:] if len(history) > 1 else history}")
        
        response = await client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=history,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                tools=[types.Tool(function_declarations=tools)],
                tool_config=tool_config,
                temperature=0.1,
            )
        )
        
        # Log Response Details
        logger.info(f"--- Gemini API Response ---")
        if response.candidates:
            for i, candidate in enumerate(response.candidates):
                logger.info(f"Candidate {i}:")
                for part in candidate.content.parts:
                    if part.text:
                        logger.info(f"  Text: {part.text[:200]}..." if len(part.text) > 200 else f"  Text: {part.text}")
                    if part.function_call:
                        logger.info(f"  Function Call: {part.function_call.name}({part.function_call.args})")
        else:
            logger.info("No candidates in response.")
        
        # 3. Tool Execution Loop
        final_response_text = await _execute_tool_loop(response, network_id, history, queue, tools, tool_config, chat_id, db)
        return final_response_text
        
    except Exception as e:
        logger.error(f"Error in process_chat: {e}")
        import traceback
        traceback.print_exc()
        await queue.put({"event": "error", "data": str(e)})
        return f"I encountered an error: {str(e)}"

def _build_history(chat_id: int, user_message: str, db: Session) -> List[types.Content]:
    """Build conversation history with few-shot examples."""
    messages = db.query(models.ChatMessage).filter(
        models.ChatMessage.chat_id == chat_id
    ).order_by(models.ChatMessage.created_at.asc()).all()
    
    history = []
    for msg in messages:
        role = "user" if msg.role == "user" else "model"
        history.append(types.Content(role=role, parts=[types.Part(text=msg.content)]))
    
    # Check if the last message in history is the same as the user_message
    # This prevents duplication if the message was already saved to DB and fetched
    if not history or history[-1].parts[0].text != user_message:
        history.append(types.Content(role="user", parts=[types.Part(text=user_message)]))
    
    # Few-shot examples (Condensed for brevity in this refactor, but kept same logic)
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
    
    # We can add more examples if needed, but keeping it clean.
    return example_1 + history

async def _execute_tool_loop(initial_response, network_id, history, queue, tools, tool_config, chat_id, db):
    """Handle the loop of tool executions."""
    current_response = initial_response
    max_iterations = 10
    iteration = 0
    
    while iteration < max_iterations:
        iteration += 1
        has_function_call = False
        
        if current_response.candidates[0].content.parts:
            for part in current_response.candidates[0].content.parts:
                if hasattr(part, 'function_call') and part.function_call:
                    has_function_call = True
                    function_call = part.function_call
                    function_name = function_call.name
                    function_args = dict(function_call.args)
                    
                    if 'network_id' not in function_args:
                        function_args['network_id'] = network_id
                    
                    # Notify start
                    logger.info(f"Executing tool: {function_name} with args: {function_args}")
                    await queue.put({
                        "event": "tool_execution",
                        "data": json.dumps({"tool": function_name, "status": "started", "args": function_args})
                    })
                    
                    # Execute
                    try:
                        function_result = await _execute_single_tool(function_name, function_args, network_id, queue, chat_id, db)
                        status = "completed"
                        error_msg = None
                    except Exception as e:
                        logger.error(f"Tool execution failed: {e}")
                        error_msg = str(e)
                        function_result = {"error": error_msg}
                        status = "failed"
                    
                    # Notify end
                    await queue.put({
                        "event": "tool_execution",
                        "data": json.dumps({"tool": function_name, "status": status, "error": error_msg})
                    })
                    
                    # Update history and get next response
                    history.append(current_response.candidates[0].content)
                    history.append(types.Content(
                        role="user",
                        parts=[types.Part.from_function_response(name=function_name, response=function_result)]
                    ))
                    
                    # Log Request Details (Tool Loop)
                    logger.info(f"--- Gemini API Request (Tool Loop) ---")
                    logger.info(f"Tool Output: {function_result}")
                    
                    current_response = await client.aio.models.generate_content(
                        model="gemini-2.5-flash",
                        contents=history,
                        config=types.GenerateContentConfig(
                            system_instruction=SYSTEM_INSTRUCTION,
                            tools=[types.Tool(function_declarations=tools)],
                            tool_config=tool_config,
                            temperature=0.1,
                        )
                    )

                    # Log Response Details (Tool Loop)
                    logger.info(f"--- Gemini API Response (Tool Loop) ---")
                    if current_response.candidates:
                        for i, candidate in enumerate(current_response.candidates):
                            logger.info(f"Candidate {i}:")
                            for part in candidate.content.parts:
                                if part.text:
                                    logger.info(f"  Text: {part.text[:200]}..." if len(part.text) > 200 else f"  Text: {part.text}")
                                if part.function_call:
                                    logger.info(f"  Function Call: {part.function_call.name}({part.function_call.args})")
                    else:
                        logger.info("No candidates in response.")
                    break # Process one at a time
        
        if not has_function_call:
            # If no function call, check if we should have called one.
            # For now, just return the text.
            return current_response.text if current_response.text else "I have processed your request."
            
    return "I've completed the requested operations."

async def _execute_single_tool(function_name, function_args, network_id, queue, chat_id, db):
    """Execute a single tool and return the result."""
    if function_name == "list_node_attributes":
        result = await network_service.list_node_attributes(network_id)
        return {"attributes": result}

    elif function_name == "list_edge_attributes":
        result = await network_service.list_edge_attributes(network_id)
        return {"attributes": result}
        
    elif function_name == "calculate_centrality":
        centrality_type = function_args.get("centrality_type", "degree")
        await queue.put({"event": "thinking_stream", "data": json.dumps({"content": f"Calculating {centrality_type} centrality..."})})
        await network_service.calculate_centrality(network_id, centrality_type)
        return {"status": "success", "message": f"Calculated {centrality_type} centrality."}

    elif function_name == "generate_visualization":
        vis_config = {
            "layout_name": function_args.get("layout_name", "spring"),
            "node_size_config": function_args.get("node_size_config"),
            "node_color_config": function_args.get("node_color_config"),
            "edge_width_config": function_args.get("edge_width_config"),
            "edge_color_config": function_args.get("edge_color_config"),
            "overlay_network_id": function_args.get("overlay_network_id"),
            "overlay_config": function_args.get("overlay_config"),
            "custom_node_colors": function_args.get("custom_node_colors")
        }
        await queue.put({"event": "thinking_stream", "data": json.dumps({"content": "Creating visualization..."})})
        vis_data = await network_service.generate_visualization(network_id, vis_config)
        
        await queue.put({"event": "render_update", "data": json.dumps(vis_data)})
        return {"status": "success", "message": "Visualization created."}
    
    elif function_name == "calculate_layout":
        layout_name = function_args.get("layout_name", "spring")
        await queue.put({"event": "thinking_stream", "data": json.dumps({"content": f"Calculating {layout_name} layout..."})})
        await network_service.calculate_layout(network_id, layout_name)
        return {"status": "success", "message": f"Calculated {layout_name} layout."}

    elif function_name == "create_ego_network":
        center_node_id = function_args.get("center_node_id")
        radius = function_args.get("radius", 1)
        await queue.put({"event": "thinking_stream", "data": json.dumps({"content": f"Creating ego network for {center_node_id}..."})})
        result = await network_service.create_ego_network(network_id, center_node_id, radius)
        return {"status": "success", "message": f"Created ego network: {result['name']}", "subgraph_id": result['new_network_id']}

    elif function_name == "create_subgraph_from_nodes":
        node_ids = function_args.get("node_ids")
        await queue.put({"event": "thinking_stream", "data": json.dumps({"content": f"Creating subgraph from {len(node_ids)} nodes..."})})
        result = await network_service.create_subgraph_from_nodes(network_id, node_ids)
        return {"status": "success", "message": f"Created subgraph: {result['name']}", "subgraph_id": result['new_network_id']}

    elif function_name == "create_path_subgraph":
        source_node_id = function_args.get("source_node_id")
        target_node_id = function_args.get("target_node_id")
        await queue.put({"event": "thinking_stream", "data": json.dumps({"content": f"Creating path subgraph from {source_node_id} to {target_node_id}..."})})
        result = await network_service.create_path_subgraph(network_id, source_node_id, target_node_id)
        return {"status": "success", "message": f"Created path subgraph: {result['name']}", "subgraph_id": result['new_network_id']}

    elif function_name == "create_k_core_subgraph":
        k = function_args.get("k")
        await queue.put({"event": "thinking_stream", "data": json.dumps({"content": f"Creating {k}-core subgraph..."})})
        result = await network_service.create_k_core_subgraph(network_id, k)
        return {"status": "success", "message": f"Created k-core subgraph: {result['name']}", "subgraph_id": result['new_network_id']}

    elif function_name == "create_largest_component_subgraph":
        await queue.put({"event": "thinking_stream", "data": json.dumps({"content": "Creating largest component subgraph..."})})
        result = await network_service.create_largest_component_subgraph(network_id)
        return {"status": "success", "message": f"Created largest component subgraph: {result['name']}", "subgraph_id": result['new_network_id']}

    elif function_name == "get_subgraphs":
        result = await network_service.get_subgraphs(network_id)
        return {"subgraphs": result}

    elif function_name == "get_top_nodes":
        metric = function_args.get("metric")
        k = function_args.get("k", 10)
        await queue.put({"event": "thinking_stream", "data": json.dumps({"content": f"Finding top {k} nodes by {metric} centrality..."})})
        result = await network_service.get_top_nodes(network_id, metric, k)
        return {"top_nodes": result}
        
    else:
        raise ValueError(f"Unknown function: {function_name}")

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