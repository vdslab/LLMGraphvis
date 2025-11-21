from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request, UploadFile, File, Response
import json
from typing import List
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse
from app import models, schemas
from app.core import database
from app.services import llm_service, network_service
from app.api.v1.endpoints.auth import get_current_user

router = APIRouter(
    prefix="/chat",
    tags=["chat"]
)

def verify_chat_ownership(
    chat_id: int,
    user_id: int,
    db: Session
) -> models.Chat:
    """Verify user owns the chat and return it"""
    chat = db.query(models.Chat).filter(
        models.Chat.id == chat_id,
        models.Chat.user_id == user_id
    ).first()
    
    if not chat:
        raise HTTPException(
            status_code=404,
            detail="Chat not found or access denied"
        )
    
    return chat

@router.get("", response_model=List[schemas.Chat])
def list_chats(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(database.get_db)
):
    """Get all chats for the current user"""
    chats = db.query(models.Chat).filter(
        models.Chat.user_id == current_user.id
    ).order_by(models.Chat.updated_at.desc()).all()
    return chats

@router.get("/{chat_id}", response_model=schemas.ChatWithNetwork)
def get_chat(
    chat_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(database.get_db)
):
    """Get specific chat with network information"""
    chat = verify_chat_ownership(chat_id, current_user.id, db)
    
    # Here we would add network information to the response
    # For now, just return the chat
    return chat

@router.get("/{chat_id}/messages", response_model=List[schemas.ChatMessage])
def get_messages(
    chat_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(database.get_db)
):
    """Get all messages for a specific chat"""
    # Verify ownership
    verify_chat_ownership(chat_id, current_user.id, db)
    
    messages = db.query(models.ChatMessage).filter(
        models.ChatMessage.chat_id == chat_id
    ).order_by(models.ChatMessage.created_at.asc()).all()
    
    return messages

@router.get("/{chat_id}/export")
async def export_network(
    chat_id: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(database.get_db)
):
    """Export network as GraphML file"""
    # Verify ownership
    chat = verify_chat_ownership(chat_id, current_user.id, db)
    
    # Call NetworkXAPI to get GraphML
    graphml_data = await network_service.export_network(chat.network_id)
    
    return Response(
        content=graphml_data,
        media_type="application/xml",
        headers={
            "Content-Disposition": f"attachment; filename=network_{chat.network_id}.graphml"
        }
    )

@router.post("", response_model=schemas.Chat)
def create_chat(
    chat: schemas.ChatCreate,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(database.get_db)
):
    user_id = current_user.id
    
    # Create Network
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
    try:
        # Initialize network and get visualization data
        vis_data = await network_service.initialize_network(network_id, graphml_data)
        
        # Broadcast render_update
        queue = await llm_service.get_event_queue(chat_id)
        await queue.put({"event": "render_update", "data": json.dumps(vis_data)})
        
        # Also notify system message
        await queue.put({"event": "system_message", "data": json.dumps({"content": "Graph uploaded and initialized successfully."})})
        
    except Exception as e:
        print(f"Error in upload background task: {e}")
        queue = await llm_service.get_event_queue(chat_id)
        await queue.put({"event": "error", "data": str(e)})

@router.post("/{chat_id}/upload", status_code=202)
async def upload_network(
    chat_id: int,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(database.get_db)
):
    # Verify chat exists and user owns it
    chat = verify_chat_ownership(chat_id, current_user.id, db)

    content = await file.read()
    # Decode assuming utf-8 for GraphML
    try:
        graphml_data = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Invalid file encoding. Please upload a valid UTF-8 encoded GraphML file.")
    
    # Start background task
    background_tasks.add_task(handle_upload_background, chat_id, chat.network_id, graphml_data)
    
    return {"status": "accepted"}

async def handle_process_background(chat_id: int, user_message: str, db: Session):
    """Background task to process chat message with LLM"""
    try:
        # Process chat and get response
        response_content = await llm_service.process_chat(chat_id, user_message, db)
        
        # Save assistant message
        db_response = models.ChatMessage(
            chat_id=chat_id,
            role="assistant",
            content=response_content
        )
        db.add(db_response)
        db.commit()
        
        # Send final message via SSE
        queue = await llm_service.get_event_queue(chat_id)
        await queue.put({
            "event": "message",
            "data": json.dumps({
                "role": "assistant",
                "content": response_content,
                "id": db_response.id,
                "created_at": db_response.created_at.isoformat()
            })
        })
        
    except Exception as e:
        print(f"Error in process background task: {e}")
        import traceback
        traceback.print_exc()
        queue = await llm_service.get_event_queue(chat_id)
        await queue.put({"event": "error", "data": str(e)})

@router.post("/{chat_id}/process", status_code=202)
async def process_message(
    chat_id: int,
    request: schemas.ChatProcessRequest,
    background_tasks: BackgroundTasks,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(database.get_db)
):
    # Verify chat exists and user owns it
    verify_chat_ownership(chat_id, current_user.id, db)
    
    # Save user message
    db_message = models.ChatMessage(
        chat_id=chat_id,
        role="user",
        content=request.message.content
    )
    db.add(db_message)
    db.commit()
    
    # Start background task for LLM processing
    background_tasks.add_task(handle_process_background, chat_id, request.message.content, db)
    
    return {"status": "accepted"}

@router.get("/{chat_id}/stream")
async def stream(
    chat_id: int,
    request: Request,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(database.get_db)
):
    # Verify chat exists and user owns it
    verify_chat_ownership(chat_id, current_user.id, db)
    
    # Return SSE response with event generator
    return EventSourceResponse(llm_service.event_generator(chat_id, request), ping=15)
