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

from common import models
from app import schemas
from app.api.v1.endpoints.auth import get_current_user
from app.core import database
from app.core.logging import get_logger
from app.services import llm as llm_service
from app.services.llm import mcp_client
from app.services.llm.catalog import get_available_provider_catalog
from app.services import chat_service, sample_networks

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


@router.get("/providers", response_model=List[schemas.LlmProviderOption])
def list_llm_providers(
    current_user: models.User = Depends(get_current_user),
):
    """List the LLM providers/models a chat can be pinned to."""
    return get_available_provider_catalog()


@router.get("/samples", response_model=List[schemas.SampleNetworkOption])
def list_sample_networks(
    current_user: models.User = Depends(get_current_user),
):
    """List the bundled networks available for starting an analysis."""
    return sample_networks.list_samples()


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
                "visualization_generate",
                {"network_id": chat.network_id},
            )

        return {
            "id": chat.id,
            "name": chat.name,
            "user_id": chat.user_id,
            "network_id": chat.network_id,
            "provider": chat.provider,
            "model": chat.model,
            "name_is_custom": chat.name_is_custom,
            "created_at": chat.created_at,
            "updated_at": chat.updated_at,
            "network": vis_data,
        }

    except Exception as e:
        logger.exception(f"Failed to fetch visualization for chat {chat_id}: {e}")
        # Fallback to returning chat with empty network data if fails
        return {
            "id": chat.id,
            "name": chat.name,
            "user_id": chat.user_id,
            "network_id": chat.network_id,
            "provider": chat.provider,
            "model": chat.model,
            "name_is_custom": chat.name_is_custom,
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
    from sqlalchemy.orm import joinedload
    
    # Verify ownership
    verify_chat_ownership(chat_id, current_user.id, db)

    messages = (
        db.query(models.ChatMessage)
        .options(joinedload(models.ChatMessage.usage))
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
    db_chat = models.Chat(
        name=chat.name,
        user_id=user_id,
        network_id=db_network.id,
        provider=chat.provider,
        model=chat.model,
    )
    db.add(db_chat)
    db.commit()
    db.refresh(db_chat)

    return db_chat


MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50MB


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

    # Read in chunks with a hard cap so an oversized upload can't
    # exhaust server memory before we reject it.
    chunks = []
    total_size = 0
    while chunk := await file.read(1024 * 1024):
        total_size += len(chunk)
        if total_size > MAX_UPLOAD_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Maximum size is {MAX_UPLOAD_SIZE // (1024 * 1024)}MB.",
            )
        chunks.append(chunk)
    content = b"".join(chunks)

    # Decode assuming utf-8 for GraphML
    try:
        graphml_data = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=400,
            detail="Invalid file encoding. Please upload a valid UTF-8 encoded GraphML file.",
        )

    if "<graphml" not in graphml_data[:4096]:
        raise HTTPException(
            status_code=400,
            detail="File does not look like a GraphML document.",
        )

    # Start background task utilizing the Service Layer
    background_tasks.add_task(
        chat_service.handle_upload_background,
        chat_id,
        chat.network_id,
        graphml_data,
        file.filename,
    )

    return {"status": "accepted"}


@router.post("/{chat_id}/samples/{sample_id}", status_code=202)
async def load_sample_network(
    chat_id: int,
    sample_id: str,
    background_tasks: BackgroundTasks,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(database.get_db),
):
    """Initialize a chat from one allowlisted bundled sample network."""
    chat = verify_chat_ownership(chat_id, current_user.id, db)
    sample = sample_networks.get_sample(sample_id)
    if sample is None:
        raise HTTPException(status_code=404, detail="Sample network not found")

    background_tasks.add_task(
        chat_service.handle_upload_background,
        chat_id,
        chat.network_id,
        sample_networks.load_graphml(sample),
        sample.upload_filename,
    )

    return {"status": "accepted"}


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

    # Start background task utilizing the Service Layer
    background_tasks.add_task(
        chat_service.handle_process_background, chat_id, request.message.content
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


@router.patch("/{chat_id}", response_model=schemas.Chat)
def update_chat(
    chat_id: int,
    chat_update: schemas.ChatUpdate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(database.get_db),
):
    """Update a chat (e.g. rename, or pin its LLM provider/model)"""
    logger.info(f"Updating chat {chat_id} with data: {chat_update}")
    chat = verify_chat_ownership(chat_id, current_user.id, db)

    update_data = chat_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(chat, field, value)

    # A name the user typed is final: pin it so neither the upload-filename nor
    # the LLM-generated title can overwrite it later.
    if update_data.get("name"):
        chat.name_is_custom = True

    db.commit()
    db.refresh(chat)

    return chat
