import json
import os
import traceback
from typing import Any, Tuple, Optional, Dict, List
from google import genai
from google.genai import types
from dotenv import load_dotenv
from app import models
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

async def _consume_stream(response: Any, queue: any) -> Tuple[str, Any]:
    """
    Consumes the response stream (or static response), emits chunks, and aggregates content.
    Returns (aggregated_text, function_call_object).
    """
    final_text = ""
    full_function_call = None
    
    if hasattr(response, '__aiter__'):  # Stream
        logger.info("Stream detected. Starting to consume response stream...")
        try:
            async for chunk in response:
                if chunk.candidates:
                    candidate = chunk.candidates[0]
                    for part in candidate.content.parts:
                        if part.text:
                            final_text += part.text
                            # Send text chunk to frontend
                            await queue.put({
                                "event": "message_chunk",
                                "data": json.dumps({"content": part.text})
                            })
                        if part.function_call:
                            if full_function_call is None:
                                full_function_call = part.function_call
                            else:
                                # Assuming simple aggregation or complete call per chunk/final chunk
                                # For robustness with partials, we might need more logic, 
                                # but SDK typically handles this or provides enough in one chunk.
                                pass 
        except Exception as e:
            logger.error(f"Error while consuming stream: {e}")
            logger.error(traceback.format_exc())
            raise e
    else:
        # Static response
        if response.candidates:
            content = response.candidates[0].content
            for part in content.parts:
                if part.text:
                    final_text += part.text
                    await queue.put({
                        "event": "message_chunk",
                        "data": json.dumps({"content": part.text})
                    })
                if part.function_call:
                    full_function_call = part.function_call

    return final_text, full_function_call

async def _handle_tool_execution(function_name: str, function_args: Dict[str, Any], network_id: int, chat_id: int, db: Any) -> Tuple[Any, str, Optional[str]]:
    """
    Executes the tool (Local or MCP).
    Returns (result, status, error_message).
    """
    try:
        if function_name in ["switch_to_main_network", "switch_to_parent_network"]:
            logger.info(f"Executing LOCAL tool: {function_name}")
            context = {"chat_id": chat_id, "db": db}
            result = await local_tools.execute_local_tool(function_name, function_args, context)
        else:
            # Inject network_id if missing and needed
            if "network_id" not in function_args and network_id:
                function_args["network_id"] = network_id
            
            result = await mcp_client.execute_tool(function_name, function_args)
            
        return result, "completed", None
    except Exception as e:
        logger.error(f"Tool execution failed: {e}")
        traceback.print_exc()
        return {"error": str(e)}, "failed", str(e)

async def _handle_visualization_update(function_name: str, function_result: Any, network_id: int, chat_id: int, db: Any, queue: Any) -> int:
    """
    Handles context switching, visualization persistence, and emitting render updates.
    Returns the (potentially new) network_id.
    """
    if not isinstance(function_result, dict):
        return network_id

    # 1. Context Switching
    if "new_network_id" in function_result and function_result["new_network_id"] != network_id:
        new_id = function_result["new_network_id"]
        logger.info(f"Context switch detected: {network_id} -> {new_id}")
        
        # Update Database
        try:
            chat = db.query(models.Chat).filter(models.Chat.id == chat_id).first()
            if chat:
                chat.network_id = new_id
                db.commit()
                logger.info(f"Updated Chat {chat_id} context to Network {new_id}")
        except Exception as e:
            logger.error(f"Failed to update chat context: {e}")
        
        # Auto-generate visualization for new network
        logger.info(f"Auto-generating visualization for new network {new_id}")
        try:
            vis_data_result = await mcp_client.execute_tool("generate_visualization", {"network_id": new_id})
            if isinstance(vis_data_result, dict) and "nodes" in vis_data_result:
                logger.info(f"Emitting render_update for auto-generated visualization of network {new_id}")
                await queue.put({
                    "event": "render_update",
                    "data": json.dumps(vis_data_result)
                })
        except Exception as e:
            logger.error(f"Failed to auto-generate visualization for network {new_id}: {e}")
        
        return new_id

    # 2. Visualization Logic for current results
    vis_data = None
    if function_name == "generate_visualization":
        vis_data = function_result
    elif function_name == "initialize_network" and "network" in function_result:
        vis_data = function_result["network"]
    
    if vis_data and isinstance(vis_data, dict) and "nodes" in vis_data and "links" in vis_data:
        logger.info(f"Emitting render_update for {function_name}")
        
        # Save visualization state to DB
        try:
             chat = db.query(models.Chat).filter(models.Chat.id == chat_id).first()
             if chat:
                 chat.visualization_state = vis_data
                 db.commit()
                 logger.info(f"Saved visualization state for chat_id={chat_id}")
        except Exception as e:
             logger.error(f"Failed to save visualization state: {e}")

        await queue.put({
            "event": "render_update",
            "data": json.dumps(vis_data)
        })
    else:
        # Not a visualization result, or invalid
        pass

    return network_id

async def execute_tool_loop(initial_response, network_id, history, queue, tool_config, chat_id, db):
    """Handle the loop of tool executions."""
    current_response = initial_response
    max_iterations = 10
    iteration = 0
    final_text_content = ""

    while iteration < max_iterations:
        iteration += 1
        
        # 1. Consume Response (Stream or Static)
        chunk_text, full_function_call = await _consume_stream(current_response, queue)
        if chunk_text:
            final_text_content += chunk_text
        
        if not full_function_call:
            # Done - no tool call
            if not final_text_content:
                return "I have processed your request."
            return final_text_content

        # 2. Prepare Tool Execution
        function_name = full_function_call.name
        function_args = dict(full_function_call.args)
        
        logger.info(f"Executing tool: {function_name} with args: {function_args}")
        await queue.put({
            "event": "tool_execution",
            "data": json.dumps({"tool": function_name, "status": "started", "args": function_args})
        })
        
        # 3. Execute Tool
        result, status, error_msg = await _handle_tool_execution(function_name, function_args, network_id, chat_id, db)
        
        # 4. Handle Visualizations / Side Effects
        if status == "completed":
            network_id = await _handle_visualization_update(function_name, result, network_id, chat_id, db, queue)
        
        # Notify Tool End
        await queue.put({
            "event": "tool_execution",
            "data": json.dumps({"tool": function_name, "status": status, "error": error_msg})
        })
        
        # 5. Update History
        # Reconstruct Content for history (User/Model parts)
        model_parts = []
        if chunk_text:
            model_parts.append(types.Part.from_text(text=chunk_text))
        # Ensure name and args are set for history reconstruction
        model_parts.append(types.Part.from_function_call(name=function_name, args=full_function_call.args))
        
        history.append(types.Content(role="model", parts=model_parts))
        history.append(types.Content(
            role="user",
            parts=[types.Part.from_function_response(name=function_name, response=result)]
        ))
        
        # 6. Next Iteration
        logger.info("--- Gemini API Request (Tool Loop) ---")
        try:
            mcp_tools = await mcp_client.get_tools_as_gemini_functions()
            local_tool_defs = local_tools.get_local_tools()
            all_tools = mcp_tools + local_tool_defs

            current_response = await client.aio.models.generate_content_stream(
                model="gemini-2.5-flash",
                contents=history,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_INSTRUCTION,
                    tools=all_tools,
                    tool_config=tool_config,
                    temperature=0.1,
                )
            )
        except Exception as e:
            logger.error(f"Error generating next content: {e}")
            break # Exit loop on generation error
            
    return final_text_content
