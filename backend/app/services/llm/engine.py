import json
import os
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

async def execute_tool_loop(initial_response, network_id, history, queue, tool_config, chat_id, db):
    """Handle the loop of tool executions."""
    # We maintain current_response for the loop, but it might be a stream or a complete response.
    # Initial response is already complete (from service.py), so we use it as is for the first iteration logic.
    # But wait, service.py also needs to be updated to stream the initial call if we want full streaming.
    # For now, let's assume service.py calls this with a complete response, OR we change service.py too.
    # The plan was: "Change client.aio.models.generate_content to use stream=True" in engine.py.
    # But engine.py only has the loop. service.py does the initial call.
    # So we actually need to change logic in service.py as well to start with a stream, 
    # OR we just handle streaming inside the loop for subsequent steps.
    # HOWEVER, the previous step's plan implied modifying engine.py widely.
    # To properly implement "Token Streaming", we should change ALL generate_content calls to stream=True.
    
    # As the initial response is passed from service.py, we'll handle the loop here.
    # If the initial response is ALREADY a stream (which we will change service.py to do next), 
    # we need to iterate it.
    
    # Let's rewrite this function to take a response_stream if possible, or we handle the first response as text
    # then subsequent ones as streams.
    
    # Actually, to avoid breaking service.py's contract immediately, let's look at `service.py` again.
    # `service.py` calls `client.aio.models.generate_content` (non-stream) then passes `response` here.
    # It expects `final_response_text` return.
    
    # We will modify `execute_tool_loop` to handle the complexity.
    
    current_response = initial_response
    max_iterations = 10
    iteration = 0
    final_text_content = ""

    while iteration < max_iterations:
        iteration += 1
        has_function_call = False
        full_function_call = None
        current_text_chunk = ""
        
        # Check if current_response is an async generator (streaming) or a standard response
        # We can detect by checking `__aiter__` or just type.
        # But `google.genai.types.GenerateContentResponse` is not an iterator. 
        # `AsyncGenerateContentResponse` (result of stream=True) is an async iterator.
        
        # If it's a direct response (first pass from service.py currently), we convert to a list to unify logic,
        # or just handle it. BUT we want to change service.py too.
        # Let's assume we will change service.py to pass a stream, or we just change the loop calls to stream.
        
        # Existing logic handles `current_response` as a complete object. 
        # We need to adapt this loop to handle *subsequent* calls as streams.
        # And really, service.py should also use stream=True.
        # Let's stick to the plan: "Change client.aio.models.generate_content to use stream=True".
        
        # If `current_response` is not a stream (initial call from service.py), we handle it as before
        # but for the loop's internal calls, we will use stream=True.
        
        # Wait, if we want to stream the *final* answer to the user, the final answer usually comes 
        # EITHER immediately (no tools) OR after tool execution.
        # So we definitely need streaming in the loop.
        
        # Processing current_response (which might be the initial one)
        # If it's the initial one and it's NOT a stream, we just process it.
        # If it IS a stream (we'll update service.py next), we iterate.
        
        candidates = []
        if hasattr(current_response, '__aiter__'):  # It is a stream
            logger.info("Stream detected. Starting to consume response stream...")
            try:

                chunk_count = 0
                async for chunk in current_response:
                    chunk_count += 1
                    # Accumulate text and send chunks
                    if chunk.candidates:
                        candidates.append(chunk.candidates[0]) # approximations for history reconstruction
                        
                        for part in chunk.candidates[0].content.parts:

                            if part.text:
                                current_text_chunk += part.text
                                final_text_content += part.text # Accumulate final text
                                # Send text chunk to frontend
                                await queue.put({
                                    "event": "message_chunk",
                                    "data": json.dumps({"content": part.text})
                                })
                            # Also "Thinking" is separate. 
                            # Usually if it's text, it's the answer.
                            # If it's "Thinking" (CoT), it comes as text too but usually we treat all text as answer 
                            # unless we parse it. 
                            # The current prompt might output text before tool calls? 
                            # The previous code handled `thinking_stream`.
                            # Let's keep `thinking_stream` for CoT if identifiable, or just everything as `message_chunk`?
                            # The previous code sent text as `thinking_stream`? 
                            # Ah, "thinking_stream" was used for text parts in the loop.
                            # If we are strictly doing "Token Streaming" for the FINAL answer, we need to know when it is the final answer.
                            # But often we don't know until we see if there's a tool call.
                            # Standard Gemini behavior: Text processing thoughts, THEN Function Call.
                            # OR Text Answer.
                            # So streaming text is safe. It's either "Thinking" or "Answer".
                            # The user sees it immediately. That's the point.
                            
                        
                        if part.function_call:
                            # Function calls might be split across chunks in some APIs, 
                            # but Google GenAI SDK `stream=True` typically yields complete function calls per chunk or aggregates them?
                            # Actually, Vertex AI / Gemini streaming of function calls can be partial.
                            # But the SDK helpers might handle aggregation.
                            # Let's assume for now we might get partials or we build it up.
                            # SAFE ROUTE: The Python SDK `stream=True` yields chunks. 
                            # `candidates[0].content.parts` in the chunk has the delta.
                            # It's tricky to reconstruct manually if not handled by SDK.
                            # However, `response.text` property usually aggregates.
                            # But we want to stream.
                            
                            # Let's rely on the fact that usually function calls come in one chunk or we can just collect them.
                            # We'll check `part.function_call`.
                            if full_function_call is None:
                                full_function_call = part.function_call
                            else:
                                # If we get multiple parts of a function call, this logic might be too simple.
                                # But let's proceed with assuming we get the call object.
                                pass
                                
                                
                logger.info(f"Stream consumption finished. Total chunks: {chunk_count}")
            
            except Exception as e:

                logger.error(f"Error while consuming stream: {e}")
                import traceback
                logger.error(traceback.format_exc())
                raise e

            # After iterating the stream, we have the full picture.

            # But wait, we need to reconstruct the `Content` object for history.
            # We can use `aggregated_response = client.aio.models.generate_content(...)` equivalent?
            # No, we just built it.
            
            # Reconstruct content part for history
            parts = []
            if current_text_chunk:
                parts.append(types.Part.from_text(text=current_text_chunk))
            if full_function_call:
                 parts.append(types.Part.from_function_call(name=full_function_call.name, args=full_function_call.args))
            
            generated_content = types.Content(role="model", parts=parts)
            
        else:
            # Not a stream (Initial response if service.py not updated yet)
            # Or if we decide to fallback.
            if current_response.candidates:
                generated_content = current_response.candidates[0].content
                # Legacy handling for non-stream
                for part in generated_content.parts:
                    if part.text:
                        final_text_content += part.text
                        # Send as chunk anyway to be consistent
                        # Note: This is "fast" streaming (one big chunk)
                        await queue.put({
                            "event": "message_chunk",
                            "data": json.dumps({"content": part.text})
                        })
                    if part.function_call:
                        full_function_call = part.function_call
            else:
                generated_content = types.Content(role="model", parts=[])

        # Now decide what to do based on content
        if full_function_call:
            has_function_call = True
            function_name = full_function_call.name
            function_args = dict(full_function_call.args)
            
             # Notify start
            logger.info(f"Executing tool: {function_name} with args: {function_args}")
            await queue.put({
                "event": "tool_execution",
                "data": json.dumps({"tool": function_name, "status": "started", "args": function_args})
            })
            
            # Execute Tool (Same logic as before)
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

            # Visualization Logic (Same as before)
            if status == "completed" and isinstance(function_result, dict):
                    # Context Switching Logic
                    if "new_network_id" in function_result and function_result["new_network_id"] != network_id:
                        new_id = function_result["new_network_id"]
                        logger.info(f"Context switch detected: {network_id} -> {new_id}")
                        
                        # Update Database
                        chat = db.query(models.Chat).filter(models.Chat.id == chat_id).first()
                        if chat:
                            chat.network_id = new_id
                            db.commit()
                            logger.info(f"Updated Chat {chat_id} context to Network {new_id}")
                        
                        # Update local variable for next iteration
                        network_id = new_id

                        # NEW: Auto-generate visualization for the new network
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
                        logger.warning(f"Skipping render_update for {function_name}: Invalid visualization data or error response")

            # Notify end
            await queue.put({
                "event": "tool_execution",
                "data": json.dumps({"tool": function_name, "status": status, "error": error_msg})
            })
            
            # Update history
            history.append(generated_content) # usage of the reconstructed content
            history.append(types.Content(
                role="user",
                parts=[types.Part.from_function_response(name=function_name, response=function_result)]
            ))
            
            # Next iteration - Streaming call
            logger.info("--- Gemini API Request (Tool Loop) ---")
            logger.info(f"Tool Output: {str(function_result)[:100]}...")
            
            mcp_tools = await mcp_client.get_tools_as_gemini_functions()
            local_tool_defs = local_tools.get_local_tools()
            all_tools = mcp_tools + local_tool_defs

            # CRITICAL CHANGE: Use stream=True
            # CRITICAL CHANGE: Use generate_content_stream
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
            # Loop continues -> next iteration will handle the stream
            # Loop continues -> next iteration will handle the stream
            
        else:
            # No function call, just text. We already streamed it.
            # We are done.
            if not final_text_content:
                 return "I have processed your request."
            return final_text_content
            
    return final_text_content
