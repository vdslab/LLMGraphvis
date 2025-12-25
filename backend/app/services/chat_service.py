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


async def handle_upload_background(chat_id: int, network_id: int, graphml_data: str) -> None:
    """
    Background task to handle network upload and initialization.
    Executes the 'initialize_network' tool on the MCP server and notifies the frontend.
    """
    logger.info(
        f"Background upload started for chat_id={chat_id}, network_id={network_id}"
    )
    try:
        # Initialize network and get response containing visualization and final_network_id
        result = await mcp_client.execute_tool(
            "initialize_network",
            {"network_id": network_id, "graphml_data": graphml_data},
        )

        vis_data = result.get("network")
        final_network_id = result.get("network_id")

        if final_network_id is None:
            error_msg = result.get(
                "content", "Unknown error during network initialization"
            )
            logger.error(f"Network initialization failed: {error_msg}")
            raise ValueError(f"Network initialization failed: {error_msg}")

        # If network_id changed (collision handling), update the Chat record
        if final_network_id != network_id:
            logger.info(
                f"Network ID updated from {network_id} to {final_network_id} due to collision/re-upload."
            )
            # Use a fresh session for this background operation
            db_session = database.SessionLocal()
            try:
                chat = (
                    db_session.query(models.Chat)
                    .filter(models.Chat.id == chat_id)
                    .first()
                )
                if chat:
                    chat.network_id = final_network_id
                    db_session.commit()
            finally:
                db_session.close()

        # Broadcast render_update
        logger.info(f"Broadcasting render_update for chat_id={chat_id}")
        queue = await llm_service.get_event_queue(chat_id)
        await queue.put({"event": "render_update", "data": json.dumps(vis_data)})

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
        logger.error(f"Error in upload background task: {e}")
        traceback.print_exc()
        queue = await llm_service.get_event_queue(chat_id)
        await queue.put({"event": "error", "data": str(e)})


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
        final_response = await llm_service.process_chat(chat_id, user_message, db)

        # Save Assistant Message
        if final_response:
            db_msg = models.ChatMessage(
                chat_id=chat_id, role="model", content=final_response
            )
            db.add(db_msg)
            db.commit()
            logger.info(f"Saved assistant message for chat_id={chat_id}")

            # Emit message_complete event
            queue = await llm_service.get_event_queue(chat_id)
            await queue.put(
                {"event": "message_complete", "data": json.dumps({"id": db_msg.id})}
            )

    except Exception as e:
        logger.error(f"Error in process background task: {e}")
        traceback.print_exc()

        # Persist error message to DB so user sees it in history/on reload
        try:
            # Re-open session if needed (it might be closed or rollback needed)
            # The 'db' session from local scope might be in invalid state due to exception
            db_error = database.SessionLocal()
            error_content = f"I encountered an internal error while processing your request: {str(e)}"
            db_err_msg = models.ChatMessage(
                chat_id=chat_id, role="model", content=error_content
            )
            db_error.add(db_err_msg)
            db_error.commit()
            
            # Notify frontend of completion (even though it's an error state) so it stops thinking
            queue = await llm_service.get_event_queue(chat_id)
            await queue.put(
                {"event": "message_complete", "data": json.dumps({"id": db_err_msg.id})}
            )
            # Also emit the error event for immediate toast/notification
            await queue.put({"event": "error", "data": str(e)})
            
            db_error.close()
        except Exception as inner_e:
            logger.error(f"Failed to save error message to DB: {inner_e}")
            queue = await llm_service.get_event_queue(chat_id)
            await queue.put({"event": "error", "data": str(e)})

    finally:
        db.close()
