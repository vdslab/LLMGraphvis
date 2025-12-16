import json
from sqlalchemy.orm import Session
from google.genai import types
from app import models
from app.core.logging import get_logger
from . import engine, history, events, mcp_client, local_tools
from .engine import client
from .prompts import SYSTEM_INSTRUCTION

logger = get_logger(__name__)

async def process_chat(chat_id: int, user_message: str, db: Session) -> str:
    """Process a chat message using Gemini API with function calling"""
    logger.info(f"Processing chat_id={chat_id}, message='{user_message[:50]}...'")
    queue = await events.get_event_queue(chat_id)
    
    try:
        # 1. Setup Context
        chat = db.query(models.Chat).filter(models.Chat.id == chat_id).first()
        if not chat: raise ValueError("Chat not found")
        network_id = chat.network_id
        
        # Build base history
        chat_history = history.build_history(chat_id, user_message, db)

        # --- Context Injection Start ---
        try:
            context_summary = await _build_context_summary(network_id)
            if context_summary and chat_history and chat_history[-1].role == "user":
                # Prepend to the last user message (Checking parts to fail safely)
                if chat_history[-1].parts and chat_history[-1].parts[0].text:
                     original_text = chat_history[-1].parts[0].text
                     new_text = f"{context_summary}\n\n{original_text}"
                     chat_history[-1].parts[0].text = new_text
                     logger.info("Injected Context Summary into User Prompt")
        except Exception as e:
            logger.warning(f"Failed to inject context summary: {e}")
        # --- Context Injection End ---
        
        # Notify thinking start
        await queue.put({
            "event": "thinking_stream",
            "data": json.dumps({"content": "Analyzing your request..."})
        })
        
        # 2. Initial LLM Call
        # tool_definitions = tools.get_definitions()
        mcp_tools = await mcp_client.get_tools_as_gemini_functions()
        local_tool_defs = local_tools.get_local_tools()
        all_tools = mcp_tools + local_tool_defs
        
        tool_config = types.ToolConfig(function_calling_config=types.FunctionCallingConfig(mode="AUTO"))
        
        logger.info("Calling Gemini API...")
        
        # Log Request Details
        logger.info(f"--- Gemini API Request ---")
        logger.info(f"Model: gemini-2.5-flash")
        
        # Truncate system instruction for logging
        sys_instruction_log = SYSTEM_INSTRUCTION[:100] + "..." if len(SYSTEM_INSTRUCTION) > 100 else SYSTEM_INSTRUCTION
        logger.info(f"System Instruction: {sys_instruction_log}")
        
        tool_names = [fn.name for t in all_tools for fn in (t.function_declarations or [])]
        logger.info(f"Tools: {tool_names}")
        
        # Log limited history
        history_log = chat_history[-2:] if len(chat_history) > 1 else chat_history
        # logger.info(f"History (Last 2): {history_log}") # Can be verbose, maybe omit or summarize
        
        # Use generate_content_stream for streaming response
        response = await client.aio.models.generate_content_stream(
            model="gemini-2.5-flash",
            contents=chat_history,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                tools=all_tools,
                tool_config=tool_config,
                temperature=0.1,
            )
        )

        
        # Log Response Details (Streaming start)
        logger.info(f"--- Gemini API Response (Streaming Started) ---")
        
        # 3. Tool Execution Loop
        # Now passing the streaming response directly to the engine
        final_response_text = await engine.execute_tool_loop(response, network_id, chat_history, queue, tool_config, chat_id, db)
        return final_response_text
        
    except Exception as e:
        logger.error(f"Error in process_chat: {e}")
        import traceback
        traceback.print_exc()
        await queue.put({"event": "error", "data": str(e)})
        return f"I encountered an error: {str(e)}"

async def _build_context_summary(network_id: int) -> str:
    """Fetches network stats and attributes to build a context summary string."""
    try:
        # Fetch resources concurrently could be better, but sequential is safer for now
        structure = await mcp_client.get_resource(f"network://{network_id}/structure")
        node_attrs = await mcp_client.get_resource(f"network://{network_id}/attributes/nodes")
        
        summary_lines = ["[Current Network Context]"]
        summary_lines.append(f"Network ID: {network_id}")
        
        if structure:
            n_count = structure.get("node_count", "?")
            e_count = structure.get("edge_count", "?")
            summary_lines.append(f"Stats: {n_count} Nodes, {e_count} Edges")
            
        if node_attrs and "attributes" in node_attrs:
            attrs = node_attrs["attributes"]
            if attrs:
                summary_lines.append("Available Node Attributes:")
                for attr in attrs:
                    name = attr.get("name")
                    dtype = attr.get("data_type")
                    summary_lines.append(f"- {name} ({dtype})")
            else:
                summary_lines.append("Node Attributes: None")
        
        return "\n".join(summary_lines)
    except Exception as e:
        logger.error(f"Error building context summary: {e}")
        return ""
