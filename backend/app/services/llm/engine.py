import json
import os
import re
import traceback
from typing import Any, Dict, Optional, Tuple

from dotenv import load_dotenv
from google import genai
from google.genai import types

from common import models
from app.core.logging import get_logger

from . import local_tools, mcp_client
from .prompts import SYSTEM_INSTRUCTION

logger = get_logger(__name__)
load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
VERTEX_PROJECT_ID = os.getenv("VERTEX_PROJECT_ID")
VERTEX_LOCATION = os.getenv("VERTEX_LOCATION", "us-central1")

if VERTEX_PROJECT_ID:
    logger.info(
        f"Using Vertex AI with Project ID: {VERTEX_PROJECT_ID}, Location: {VERTEX_LOCATION}"
    )
    client = genai.Client(
        vertexai=True, project=VERTEX_PROJECT_ID, location=VERTEX_LOCATION
    )
else:
    logger.info("Using Google AI Studio with API Key")
    client = genai.Client(api_key=GOOGLE_API_KEY)


async def _consume_stream(response: Any, queue: any) -> Tuple[str, list[Any]]:
    """
    Consumes the response stream (or static response), emits chunks, and aggregates content.
    Returns (aggregated_text, list_of_function_call_objects).
    """
    final_text = ""
    # We now collect a LIST of function calls
    all_function_calls = []

    if hasattr(response, "__aiter__"):  # Stream
        logger.info("Stream detected. Starting to consume response stream...")
        try:
            async for chunk in response:
                if chunk.candidates:
                    candidate = chunk.candidates[0]
                    for part in candidate.content.parts:
                        if part.text:
                            final_text += part.text
                            # Send text chunk to frontend
                            await queue.put(
                                {
                                    "event": "message_chunk",
                                    "data": json.dumps({"content": part.text}),
                                }
                            )
                        if part.function_call:
                            all_function_calls.append(part.function_call)
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
                    await queue.put(
                        {
                            "event": "message_chunk",
                            "data": json.dumps({"content": part.text}),
                        }
                    )
                if part.function_call:
                    all_function_calls.append(part.function_call)

    return final_text, all_function_calls


async def _handle_tool_execution(
    function_name: str,
    function_args: Dict[str, Any],
    network_id: int,
    chat_id: int,
    db: Any,
) -> Tuple[Any, str, Optional[str]]:
    """
    Executes the tool (Local or MCP).
    Returns (result, status, error_message).
    """
    try:
        if function_name in ["switch_to_main_network", "switch_to_parent_network"]:
            logger.info(f"Executing LOCAL tool: {function_name}")
            context = {"chat_id": chat_id, "db": db}
            result = await local_tools.execute_local_tool(
                function_name, function_args, context
            )
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


async def _handle_visualization_update(
    function_name: str,
    function_result: Any,
    network_id: int,
    chat_id: int,
    db: Any,
    queue: Any,
) -> int:
    """
    Handles context switching, visualization persistence, and emitting render updates.
    Returns the (potentially new) network_id.
    """
    if not isinstance(function_result, dict):
        return network_id

    # 1. Context Switching
    if (
        "new_network_id" in function_result
        and function_result["new_network_id"] != network_id
    ):
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
            vis_data_result = await mcp_client.execute_tool(
                "generate_visualization", {"network_id": new_id}
            )
            if isinstance(vis_data_result, dict) and "nodes" in vis_data_result:
                logger.info(
                    f"Emitting render_update for auto-generated visualization of network {new_id}"
                )
                await queue.put(
                    {"event": "render_update", "data": json.dumps(vis_data_result)}
                )
        except Exception as e:
            logger.error(
                f"Failed to auto-generate visualization for network {new_id}: {e}"
            )

        return new_id

    # 2. Visualization Logic for current results
    vis_data = None
    if function_name == "generate_visualization":
        vis_data = function_result
    elif function_name == "initialize_network" and "network" in function_result:
        vis_data = function_result["network"]

    if (
        vis_data
        and isinstance(vis_data, dict)
        and "nodes" in vis_data
        and "links" in vis_data
    ):
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

        await queue.put({"event": "render_update", "data": json.dumps(vis_data)})
    else:
        # Not a visualization result, or invalid
        pass

    return network_id


async def execute_tool_loop(
    initial_response, network_id, history, queue, tool_config, chat_id, db
):
    """Handle the loop of tool executions."""
    current_response = initial_response
    max_iterations = 10
    iteration = 0
    final_text_content = ""

    while iteration < max_iterations:
        iteration += 1

        # 1. Consume Response (Stream or Static)
        # Returns all accumulated text and A LIST of function calls
        chunk_text, function_calls = await _consume_stream(current_response, queue)
        
        if chunk_text:
            final_text_content += chunk_text

        if not function_calls:
            # Check for "Lazy Intent" (stating action without calling tool)
            # Pattern catches: "I will analyze", "I'm going to check", "Let's visualize", etc.
            lazy_pattern = r"(?i)\b(i will|i'm going to|let's|now i will|proceeding to)\s+(?:\w+\s+){0,3}(?:analyze|check|calculate|get|retrieve|visualize|examine|update|create)"
            
            # Prevent infinite retry loops - check history for recent system alerts
            retry_count_in_turn = sum(1 for part in history[-2:] if "SYSTEM_ALERT" in str(part)) if hasattr(history, '__iter__') else 0
            
            if re.search(lazy_pattern, final_text_content) and retry_count_in_turn < 2:
                logger.warning(f"Lazy response detected: '{final_text_content[:100]}...' - RETRYING")
                
                # Add the lazy text to history as usual (so the model sees what it wrote)
                history.append(types.Content(role="model", parts=[types.Part.from_text(text=final_text_content)]))
                
                # Add a strong system prompt as a "user" message to force correction
                alert_msg = (
                    "SYSTEM_ALERT: You stated an intent to act (e.g., 'I will...'), but issued NO tool calls. "
                    "Do not plan. EXECUTE the tool call immediately. "
                    "If you need to analyze the network, call 'get_network_structure_tool' or 'list_node_attributes' NOW."
                )
                history.append(types.Content(role="user", parts=[types.Part.from_text(text=alert_msg)]))
                
                # Reset response text for next attempt (optional, but cleaner if we don't return double text)
                # Actually, we should probably keep the text? No, usually we want it to replace its "I will" with the action.
                # But here we appended it to history, so the model knows. 
                # Let's continue, effectively doing a new generation step.
                # Fetch tools for the retry
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
                    ),
                )
                continue

            # Done - no tool call and no retry needed
            if not final_text_content:
                # Fallback if model yields nothing (rare)
                return "I have processed your request."
            return final_text_content

        # 2. Iterate through all function calls in this turn
        function_responses_parts = []
        function_calls_parts = []
        
        # We need to construct the history parts carefully.
        # The 'model' turn must contain the text (if any) and ALL function calls.
        if chunk_text:
            function_calls_parts.append(types.Part.from_text(text=chunk_text))
        
        for fc in function_calls:
            function_calls_parts.append(
                types.Part.from_function_call(name=fc.name, args=fc.args)
            )

            # Execute the tool
            function_name = fc.name
            function_args = dict(fc.args)

            logger.info(f"Executing tool: {function_name} with args: {function_args}")
            await queue.put(
                {
                    "event": "tool_execution",
                    "data": json.dumps(
                        {"tool": function_name, "status": "started", "args": function_args}
                    ),
                }
            )

            result, status, error_msg = await _handle_tool_execution(
                function_name, function_args, network_id, chat_id, db
            )

            if status == "completed":
                # Handle side-effects (visualization, context switch)
                # Note: network_id might change here. We update it for the NEXT loop iteration.
                # For sequential tools in the same turn, we use the updated one if possible,
                # but 'function_args' was already fixed by the LLM. 
                # If a tool relies on the NEW ID, it might fail if the LLM didn't predict it. 
                # But for parallel unconnected tools, it's fine.
                network_id = await _handle_visualization_update(
                    function_name, result, network_id, chat_id, db, queue
                )

            # Notify Tool End
            await queue.put(
                {
                    "event": "tool_execution",
                    "data": json.dumps(
                        {"tool": function_name, "status": status, "error": error_msg}
                    ),
                }
            )

            # Collect response part
            function_responses_parts.append(
                types.Part.from_function_response(
                    name=function_name, response=result
                )
            )

        # 3. Update History
        # Add the full MODEL turn (Text + All Function Calls)
        history.append(types.Content(role="model", parts=function_calls_parts))
        
        # Add the full USER turn (All Function Responses)
        history.append(types.Content(role="user", parts=function_responses_parts))

        # 4. Next Iteration
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
                ),
            )
        except Exception as e:
            logger.error(f"Error generating next content: {e}")
            break  # Exit loop on generation error

    return final_text_content
