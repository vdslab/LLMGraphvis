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
        
        chat_history = history.build_history(chat_id, user_message, db)
        
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
        
        response = await client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=chat_history,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                tools=all_tools,
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
                        text_log = part.text[:200] + "..." if len(part.text) > 200 else part.text
                        logger.info(f"  Text: {text_log}")
                    if part.function_call:
                        logger.info(f"  Function Call: {part.function_call.name}({part.function_call.args})")
        else:
            logger.info("No candidates in response.")
        
        # 3. Tool Execution Loop
        final_response_text = await engine.execute_tool_loop(response, network_id, chat_history, queue, tool_config, chat_id, db)
        return final_response_text
        
    except Exception as e:
        logger.error(f"Error in process_chat: {e}")
        import traceback
        traceback.print_exc()
        await queue.put({"event": "error", "data": str(e)})
        return f"I encountered an error: {str(e)}"
