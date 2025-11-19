from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request, UploadFile, File
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse
import models, schemas, database
from services import llm_service, network_service

router = APIRouter(
    prefix="/chat",
    tags=["chat"]
)

@router.post("", response_model=schemas.Chat)
def create_chat(chat: schemas.ChatCreate, db: Session = Depends(database.get_db)):
    # Placeholder: get current user
    user_id = 1 # TODO: Get from auth
    
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

@router.post("/{chat_id}/upload", status_code=202)
async def upload_network(chat_id: int, background_tasks: BackgroundTasks, file: UploadFile = File(...), db: Session = Depends(database.get_db)):
    # Verify chat exists
    chat = db.query(models.Chat).filter(models.Chat.id == chat_id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat not found")

    content = await file.read()
    # Decode assuming utf-8 for GraphML
    try:
        graphml_data = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Invalid file encoding. Please upload a valid UTF-8 encoded GraphML file.")
    
    # Start background task
    # We pass the network_id associated with the chat
    background_tasks.add_task(network_service.initialize_network, chat.network_id, graphml_data)
    
    return {"status": "accepted"}

@router.post("/{chat_id}/process", status_code=202)
def process_message(chat_id: int, request: schemas.ChatProcessRequest, background_tasks: BackgroundTasks, db: Session = Depends(database.get_db)):
    # Save user message
    db_message = models.ChatMessage(
        chat_id=chat_id,
        role=request.message.role,
        content=request.message.content
    )
    db.add(db_message)
    db.commit()
    
    # Start background task
    background_tasks.add_task(llm_service.process_chat, chat_id, request.message.content, db)
    
    return {"status": "accepted"}

@router.get("/{chat_id}/stream")
async def stream(chat_id: int, request: Request):
    # This is a simplified SSE implementation. 
    # In a real app, we'd need a pub/sub mechanism (like Redis) to broadcast messages from the background task to this endpoint.
    # For this MVP/local setup, we might need a simple in-memory queue or similar.
    # Given the constraints, I'll implement a generator that yields events.
    # But wait, the background task runs in a separate thread/process.
    # I need a way to communicate.
    
    # I will use a simple global dictionary of queues for this MVP.
    return EventSourceResponse(llm_service.event_generator(chat_id, request))
