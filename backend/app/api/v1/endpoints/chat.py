import json
from typing import List

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    Request,
    Response,
    UploadFile,
)
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from app import models, schemas
from app.api.v1.endpoints.auth import get_current_user
from app.core import database
from app.core.logging import get_logger
from app.services import llm as llm_service
from app.services.llm import mcp_client

logger = get_logger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


def verify_chat_ownership(chat_id: int, user_id: int, db: Session) -> models.Chat:
    """Verify user owns the chat and return it"""
    chat = (
        db.query(models.Chat)
        .filter(models.Chat.id == chat_id, models.Chat.user_id == user_id)
        .first()
    )

    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found or access denied")

    return chat


@router.get("", response_model=List[schemas.Chat])
def list_chats(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(database.get_db),
):
    """Get all chats for the current user"""
    chats = (
        db.query(models.Chat)
        .filter(models.Chat.user_id == current_user.id)
        .order_by(models.Chat.updated_at.desc())
        .all()
    )
    return chats


@router.get("/{chat_id}", response_model=schemas.ChatWithNetwork)
async def get_chat(
    chat_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(database.get_db),
):
    """Get specific chat with network information"""
    chat = verify_chat_ownership(chat_id, current_user.id, db)

    try:
        # Try to get saved visualization state first
        if chat.visualization_state:
            logger.info(f"Returning saved visualization state for chat {chat_id}")
            vis_data = chat.visualization_state
        else:
            logger.info(
                f"No saved visualization for chat {chat_id}, generating default."
            )
            # Generate default visualization data
            vis_data = await mcp_client.execute_tool(
                "generate_visualization",
                {"network_id": chat.network_id, "layout_name": "forceatlas2"},
            )

        return {
            "id": chat.id,
            "name": chat.name,
            "user_id": chat.user_id,
            "network_id": chat.network_id,
            "created_at": chat.created_at,
            "updated_at": chat.updated_at,
            "network": vis_data,
        }

    except Exception as e:
        print(f"Failed to fetch visualization for chat {chat_id}: {e}")
        # Fallback to returning chat with empty network data if fails
        return {
            "id": chat.id,
            "name": chat.name,
            "user_id": chat.user_id,
            "network_id": chat.network_id,
            "created_at": chat.created_at,
            "updated_at": chat.updated_at,
            "network": None,
        }


@router.get("/{chat_id}/messages", response_model=List[schemas.ChatMessage])
def get_messages(
    chat_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(database.get_db),
):
    """Get all messages for a specific chat"""
    # Verify ownership
    verify_chat_ownership(chat_id, current_user.id, db)

    messages = (
        db.query(models.ChatMessage)
        .filter(models.ChatMessage.chat_id == chat_id)
        .order_by(models.ChatMessage.created_at.asc())
        .all()
    )

    return messages


@router.get("/{chat_id}/export")
async def export_network(
    chat_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(database.get_db),
):
    """Export network as GraphML file"""
    # Verify ownership
    chat = verify_chat_ownership(chat_id, current_user.id, db)

    # Call NetworkXAPI to get GraphML
    graphml_data = await mcp_client.execute_tool(
        "export_network", {"network_id": chat.network_id}
    )

    return Response(
        content=graphml_data,
        media_type="application/xml",
        headers={
            "Content-Disposition": f"attachment; filename=network_{chat.network_id}.graphml"
        },
    )


@router.post("", response_model=schemas.Chat)
def create_chat(
    chat: schemas.ChatCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(database.get_db),
):
    logger.info(f"Creating new chat: {chat.name} for user {current_user.id}")
    user_id = current_user.id

    db_network = models.Network(name=f"{chat.name} Network")
    db.add(db_network)
    db.commit()
    db.refresh(db_network)

    # Create Chat
    db_chat = models.Chat(name=chat.name, user_id=user_id, network_id=db_network.id)
    db.add(db_chat)
    db.commit()
    db.refresh(db_chat)

    return db_chat


async def handle_upload_background(chat_id: int, network_id: int, graphml_data: str):
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
        print(f"Error in upload background task: {e}")
        import traceback

        traceback.print_exc()
        queue = await llm_service.get_event_queue(chat_id)
        await queue.put({"event": "error", "data": str(e)})


@router.post("/{chat_id}/upload", status_code=202)
async def upload_network(
    chat_id: int,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(database.get_db),
):
    # Verify chat exists and user owns it
    chat = verify_chat_ownership(chat_id, current_user.id, db)

    content = await file.read()
    # Decode assuming utf-8 for GraphML
    try:
        graphml_data = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=400,
            detail="Invalid file encoding. Please upload a valid UTF-8 encoded GraphML file.",
        )

    # Start background task
    background_tasks.add_task(
        handle_upload_background, chat_id, chat.network_id, graphml_data
    )

    return {"status": "accepted"}


async def handle_process_background(chat_id: int, user_message: str):
    """Background task to process chat message with LLM"""
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
        print(f"Error in process background task: {e}")
        import traceback

        traceback.print_exc()
        queue = await llm_service.get_event_queue(chat_id)
        await queue.put({"event": "error", "data": str(e)})
    finally:
        db.close()


@router.post("/{chat_id}/process", status_code=202)
async def process_message(
    chat_id: int,
    request: schemas.ChatProcessRequest,
    background_tasks: BackgroundTasks,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(database.get_db),
):
    logger.info(f"Process message request received for chat_id={chat_id}")
    # Verify chat exists and user owns it
    verify_chat_ownership(chat_id, current_user.id, db)

    # Save user message
    db_message = models.ChatMessage(
        chat_id=chat_id, role="user", content=request.message.content
    )
    db.add(db_message)
    db.commit()

    # Start background task for LLM processing
    background_tasks.add_task(
        handle_process_background, chat_id, request.message.content
    )

    return {"status": "accepted"}


@router.get("/{chat_id}/stream")
async def stream(
    chat_id: int,
    request: Request,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(database.get_db),
):
    # Verify chat exists and user owns it
    verify_chat_ownership(chat_id, current_user.id, db)

    # Return SSE response with event generator
    return EventSourceResponse(llm_service.event_generator(chat_id, request), ping=15)
