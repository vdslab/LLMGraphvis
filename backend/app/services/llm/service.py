import json

from google.genai import types
from sqlalchemy.orm import Session

from common import models
from app.core.logging import get_logger

from . import engine, events, history, local_tools, mcp_client
from .prompts import SYSTEM_INSTRUCTION

logger = get_logger(__name__)


async def process_chat(chat_id: int, user_message: str, db: Session) -> str:
    """Process a chat message using Gemini API with function calling"""
    logger.info(f"Processing chat_id={chat_id}, message='{user_message[:50]}...'")
    queue = await events.get_event_queue(chat_id)

    try:
        # 1. Setup Context
        chat = db.query(models.Chat).filter(models.Chat.id == chat_id).first()
        if not chat:
            raise ValueError("Chat not found")
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
        await queue.put(
            {
                "event": "thinking_stream",
                "data": json.dumps({"content": "Analyzing your request..."}),
            }
        )

        # 2. Delegate to GraphVisAgent
        # The agent handles tool retrieval, initial generation, and the tool loop.
        agent = engine.GraphVisAgent(db)
        
        # We can still pass a custom tool_config if needed, but default is usually fine.
        tool_config = types.ToolConfig(
            function_calling_config=types.FunctionCallingConfig(mode="AUTO")
        )

        final_response_text = await agent.process_turn(
            history=chat_history,
            queue=queue,
            chat_id=chat_id,
            network_id=network_id,
            tool_config=tool_config
        )
        
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
        node_attrs = await mcp_client.get_resource(
            f"network://{network_id}/attributes/nodes"
        )
        edge_attrs = await mcp_client.get_resource(
            f"network://{network_id}/attributes/edges"
        )

        summary_lines = ["[Current Network Context]"]
        summary_lines.append(f"Network ID: {network_id}")

        if structure:
            n_count = structure.get("node_count", "?")
            e_count = structure.get("edge_count", "?")
            summary_lines.append(f"Stats: {n_count} Nodes, {e_count} Edges")

        if node_attrs and isinstance(node_attrs, list):
             # It seems node_attrs returns a list based on get_attribute_stats
             # But let's check mcp_server.py implementation. 
             # It returns json.dumps(stats), and stats is a list of dicts.
             # mcp_client.get_resource likely returns the parsed JSON.
             pass

        # Helper to format attributes
        def format_attrs(attrs, label):
            if attrs and isinstance(attrs, list):
                if attrs:
                    summary_lines.append(f"Available {label}:")
                    for attr in attrs:
                        name = attr.get("name")
                        dtype = attr.get("data_type")
                        summary_lines.append(f"- {name} ({dtype})")
                else:
                    summary_lines.append(f"{label}: None")
            elif attrs and isinstance(attrs, dict) and "attributes" in attrs:
                # Fallback if structure changes
                ats = attrs["attributes"]
                if ats:
                    summary_lines.append(f"Available {label}:")
                    for attr in ats:
                        name = attr.get("name")
                        dtype = attr.get("data_type")
                        summary_lines.append(f"- {name} ({dtype})")
            
        format_attrs(node_attrs, "Node Attributes")
        format_attrs(edge_attrs, "Edge Attributes")

        return "\n".join(summary_lines)
    except Exception as e:
        logger.error(f"Error building context summary: {e}")
        return ""
