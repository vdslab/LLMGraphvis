import json
import os
from google import genai
from google.genai import types
from dotenv import load_dotenv
from app.core.logging import get_logger
from . import mcp_client, local_tools
from .prompts import SYSTEM_INSTRUCTION

logger = get_logger(__name__)
load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
VERTEX_PROJECT_ID = os.getenv("VERTEX_PROJECT_ID")
VERTEX_LOCATION = os.getenv("VERTEX_LOCATION", "us-central1")

if VERTEX_PROJECT_ID:
    logger.info(f"Using Vertex AI with Project ID: {VERTEX_PROJECT_ID}, Location: {VERTEX_LOCATION}")
    client = genai.Client(vertexai=True, project=VERTEX_PROJECT_ID, location=VERTEX_LOCATION)
else:
    logger.info("Using Google AI Studio with API Key")
    client = genai.Client(api_key=GOOGLE_API_KEY)

async def execute_tool_loop(initial_response, network_id, history, queue, tool_config, chat_id, db):
    """Handle the loop of tool executions."""
    current_response = initial_response
    max_iterations = 10
    iteration = 0
    
    while iteration < max_iterations:
        iteration += 1
        has_function_call = False
        
        if current_response.candidates and current_response.candidates[0].content.parts:
            for part in current_response.candidates[0].content.parts:
                if part.text:
                    await queue.put({
                        "event": "thinking_stream",
                        "data": json.dumps({"content": part.text})
                    })
                
                if hasattr(part, 'function_call') and part.function_call:
                    has_function_call = True
                    function_call = part.function_call
                    function_name = function_call.name
                    function_args = dict(function_call.args)
                    
                    # Notify start
                    logger.info(f"Executing tool: {function_name} with args: {function_args}")
                    await queue.put({
                        "event": "tool_execution",
                        "data": json.dumps({"tool": function_name, "status": "started", "args": function_args})
                    })

                    
                    try:
                        if function_name in ["switch_to_main_network", "switch_to_parent_network"]:
                             logger.info(f"Executing LOCAL tool: {function_name}")
                             context = {"chat_id": chat_id, "db": db}
                             function_result = await local_tools.execute_local_tool(function_name, function_args, context)
                        else:
                             # Inject network_id if missing and needed
                             if "network_id" not in function_args and network_id:
                                 function_args["network_id"] = network_id
                             
                             function_result = await mcp_client.execute_tool(function_name, function_args)
                             
                        status = "completed"
                        error_msg = None
                    except Exception as e:
                        logger.error(f"Tool execution failed: {e}")
                        import traceback
                        traceback.print_exc()
                        error_msg = str(e)
                        function_result = {"error": error_msg}
                        status = "failed"
                    
                    
                    # Logic to identify visualization updates and send render_update event
                    if status == "completed" and isinstance(function_result, dict):
                        vis_data = None
                        if function_name == "generate_visualization":
                            vis_data = function_result
                        elif function_name == "initialize_network" and "network" in function_result:
                            vis_data = function_result["network"]
                        
                        if vis_data:
                            logger.info(f"Emitting render_update for {function_name}")
                            await queue.put({
                                "event": "render_update",
                                "data": json.dumps(vis_data)
                            })

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
                    
                    # Re-fetch tool definitions (or we could pass them in to avoid re-fetching)
                    mcp_tools = await mcp_client.get_tools_as_gemini_functions()
                    local_tool_defs = local_tools.get_local_tools()
                    all_tools = mcp_tools + local_tool_defs

                    current_response = await client.aio.models.generate_content(
                        model="gemini-2.5-flash",
                        contents=history,
                        config=types.GenerateContentConfig(
                            system_instruction=SYSTEM_INSTRUCTION,
                            tools=all_tools,
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
