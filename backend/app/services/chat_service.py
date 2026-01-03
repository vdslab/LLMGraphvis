import json
import traceback
from typing import Optional

from sqlalchemy.orm import Session

from common import models
from app.core import database
from app.core.logging import get_logger
from app.services import llm as llm_service
from app.services.llm import mcp_client

logger = get_logger(__name__)


async def _handle_background_error(chat_id: int, e: Exception, message: str) -> None:
    logger.error(f"{message}: {e}")
    traceback.print_exc()
    queue = await llm_service.get_event_queue(chat_id)
    await queue.put({"event": "training_error" if "training" in message else "error", "data": str(e)})

    # If it's a process error, persist to DB
    if "process" in message:
        try:
             # Use a fresh session for error logging
            db_error = database.SessionLocal()
            error_content = f"I encountered an internal error while processing your request: {str(e)}"
            db_err_msg = models.ChatMessage(
                chat_id=chat_id, role="model", content=error_content
            )
            db_error.add(db_err_msg)
            db_error.commit()
            
            await queue.put(
                {"event": "message_complete", "data": json.dumps({"id": db_err_msg.id})}
            )
            db_error.close()
        except Exception as inner_e:
            logger.error(f"Failed to save error message to DB: {inner_e}")

async def handle_upload_background(chat_id: int, network_id: int, graphml_data: str) -> None:
    """
    Background task to handle network upload and initialization.
    Executes the initialization steps granularly to provide progress updates.
    """
    logger.info(
        f"Background upload started for chat_id={chat_id}, network_id={network_id}"
    )
    
    queue = await llm_service.get_event_queue(chat_id)
    
    try:
        # Step 1: Import
        await queue.put({"event": "thinking_stream", "data": {"content": "Importing GraphML data..."}})
        import_result = await mcp_client.execute_tool(
            "import_graphml",
            {"network_id": network_id, "graphml_data": graphml_data},
        )
        
        if "error" in import_result:
            raise ValueError(f"Import failed: {import_result['error']}")
            
        final_network_id = import_result.get("network_id")
        if final_network_id is None:
             raise ValueError("Import tool did not return a valid network_id")

        # Step 2: Layout
        await queue.put({"event": "thinking_stream", "data": {"content": "Calculating ForceAtlas2 layout..."}})
        layout_result = await mcp_client.execute_tool(
            "calculate_layout",
            {"network_id": final_network_id, "layout_name": "forceatlas2"}
        )
        
        # layout tool returns string message or "Error: ..."
        if isinstance(layout_result, str) and layout_result.startswith("Error"):
             raise ValueError(layout_result)

        # Step 3: Visualization
        await queue.put({"event": "thinking_stream", "data": {"content": "Generating initial visualization..."}})
        vis_data = await mcp_client.execute_tool(
            "generate_visualization",
            {"network_id": final_network_id}
        )
        
        # Check if vis_data is an error dict (though tool raises/returns dict usually)
        if isinstance(vis_data, dict) and "error" in vis_data:
             raise ValueError(f"Visualization failed: {vis_data['error']}")

        # Update Chat record with new network_id (if changed) and visualization_state
        # Use a fresh session for this background operation
        db_session = database.SessionLocal()
        try:
            chat = (
                db_session.query(models.Chat)
                .filter(models.Chat.id == chat_id)
                .first()
            )
            if chat:
                # Update network_id if collision occurred
                if final_network_id != network_id:
                     logger.info(
                        f"Network ID updated from {network_id} to {final_network_id} due to collision/re-upload."
                    )
                     chat.network_id = final_network_id
                
                # ALWAYS save the initial visualization state
                if vis_data:
                    chat.visualization_state = vis_data
                    logger.info(f"Saved initial visualization state for chat_id={chat_id}")

                db_session.commit()
        finally:
            db_session.close()

        # Broadcast render_update
        logger.info(f"Broadcasting render_update for chat_id={chat_id}")
        await queue.put({"event": "render_update", "data": json.dumps(vis_data)})
        
        # Clear the thinking message
        await queue.put({"event": "thinking_stream", "data": {"content": None}})

        # Also notify system message
        await queue.put(
            {
                "event": "system_message",
                "data": json.dumps(
                    {"content": "Graph uploaded and initialized successfully."}
                ),
            }
        )

    except Exception as e:
        await _handle_background_error(chat_id, e, "Error in upload background task")


async def handle_process_background(chat_id: int, user_message: str) -> None:
    """
    Background task to process chat message with LLM.
    Orchestrates the Agent interaction and persists messages.
    """
    logger.info(
        f"Background process started for chat_id={chat_id}, message='{user_message[:50]}...'"
    )
    db = database.SessionLocal()
    try:
        # Process chat and get response
        # process_turn now returns (final_text, execution_log)
        final_response_text, execution_log = await llm_service.process_chat(chat_id, user_message, db)

        # Save Assistant Message
        if final_response_text:
            db_msg = models.ChatMessage(
                chat_id=chat_id, 
                role="model", 
                content=final_response_text,
            )
            db.add(db_msg)
            db.commit()
            db.refresh(db_msg)

            # Persist separate Tool Executions
            if execution_log:
                for step in execution_log:
                    if step.get("step_type") == "tool_execution":
                        for tool_call in step.get("tool_calls", []):
                            execution = models.ToolExecution(
                                message_id=db_msg.id,
                                tool_name=tool_call.get("name"),
                                arguments=tool_call.get("args"),
                                result=tool_call.get("result"),
                                thought=step.get("thought"),
                                status=tool_call.get("status", "unknown"),
                                error=tool_call.get("error"),
                                started_at=tool_call.get("started_at"),
                                completed_at=tool_call.get("completed_at")
                            )
                            db.add(execution)
                db.commit()
            
            logger.info(f"Saved assistant message for chat_id={chat_id}")

            # Emit message_complete event
            queue = await llm_service.get_event_queue(chat_id)
            await queue.put(
                {"event": "message_complete", "data": json.dumps({"id": db_msg.id})}
            )

    except Exception as e:
        await _handle_background_error(chat_id, e, "Error in process background task")

    finally:
        db.close()
