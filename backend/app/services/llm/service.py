import json
from typing import List, Any, Tuple

from google.genai import types
from sqlalchemy.orm import Session

from common import models
from app.core.logging import get_logger

from . import engine, events, history, local_tools, mcp_client
from .prompts import SYSTEM_INSTRUCTION

logger = get_logger(__name__)


def _format_exception_message(e: BaseException) -> str:
    """
    Format exception message, handling ExceptionGroup/TaskGroup recursively.
    """
    try:
        # Python 3.11+ BaseExceptionGroup
        if isinstance(e, BaseExceptionGroup):
            msgs = []
            for exc in e.exceptions:
                msgs.append(_format_exception_message(exc))
            return "; ".join(msgs)
    except NameError:
        pass  # Pre-3.11

    return f"{type(e).__name__}: {str(e)}"

async def process_chat(chat_id: int, user_message: str, db: Session) -> Tuple[str, List[Any]]:
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

        final_response_text, execution_log = await agent.process_turn(
            history=chat_history,
            queue=queue,
            chat_id=chat_id,
            network_id=network_id,
            tool_config=tool_config
        )
        
        return final_response_text, execution_log

    except Exception as e:
        logger.error(f"Error in process_chat: {e}")
        import traceback

        traceback.print_exc()
        traceback.print_exc()
        await queue.put({"event": "error", "data": str(e)})
        
        error_msg = _format_exception_message(e)
        # Return empty log on error
        return f"I encountered an error: {error_msg}", []


async def _build_context_summary(network_id: int) -> str:
    """Fetches network stats and attributes to build a context summary string."""
    try:
        # Fetch resources using a single session to reduce overhead
        async with mcp_client.session_scope() as session:
            structure = await mcp_client.get_resource(
                f"network://{network_id}/structure", session=session
            )
            node_attrs = await mcp_client.get_resource(
                f"network://{network_id}/attributes/nodes", session=session
            )
            edge_attrs = await mcp_client.get_resource(
                f"network://{network_id}/attributes/edges", session=session
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
                    # Limit to top 15 to avoid context saturation
                    limit = 15
                    for i, attr in enumerate(attrs):
                        if i >= limit:
                            remaining = len(attrs) - limit
                            summary_lines.append(f"- ... and {remaining} more")
                            break
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
                    limit = 15
                    for i, attr in enumerate(ats):
                        if i >= limit:
                            remaining = len(ats) - limit
                            summary_lines.append(f"- ... and {remaining} more")
                            break
                        name = attr.get("name")
                        dtype = attr.get("data_type")
                        summary_lines.append(f"- {name} ({dtype})")
            
        format_attrs(node_attrs, "Node Attributes")
        format_attrs(edge_attrs, "Edge Attributes")

        return "\n".join(summary_lines)
    except Exception as e:
        logger.error(f"Error building context summary: {e}")
        return ""
