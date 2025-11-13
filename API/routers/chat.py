"""
API endpoints for chat-based network analysis.

This module provides routes for managing conversations, messages, and
interacting with the network analysis tools through a chat interface.
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
import json
import logging

import models
import schemas
import auth
from database import get_db
from utils import create_empty_graphml
from services import conversation_service, chat_processor, layout_recommender

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/chat",
    tags=["chat"],
    responses={401: {"description": "Unauthorized"}},
)

@router.post("/conversations", response_model=schemas.Conversation)
async def create_conversation(
    conversation: schemas.ConversationCreate,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Creates a new conversation.

    Args:
        conversation: The conversation to create.
        current_user: The current authenticated user.
        db: The database session.

    Returns:
        The newly created conversation.
    """
    return conversation_service.create_conversation(db, current_user.id, conversation.title)

@router.get("/conversations", response_model=List[schemas.Conversation])
async def get_conversations(
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Retrieves all conversations for the current user.

    Args:
        current_user: The current authenticated user.
        db: The database session.

    Returns:
        A list of conversations.
    """
    return conversation_service.get_user_conversations(db, current_user.id)

@router.get("/conversations/{conversation_id}", response_model=schemas.Conversation)
async def get_conversation(
    conversation_id: int,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Retrieves a specific conversation by ID.

    Args:
        conversation_id: The ID of the conversation to retrieve.
        current_user: The current authenticated user.
        db: The database session.

    Returns:
        The conversation with the specified ID.
    """
    conversations = conversation_service.get_user_conversations(db, current_user.id)
    for conv in conversations:
        if conv.id == conversation_id:
            return conv
    
    raise HTTPException(status_code=404, detail="Conversation not found")

@router.get("/conversations/{conversation_id}/messages", response_model=List[schemas.ChatMessage])
async def get_messages(
    conversation_id: int,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Retrieves all messages for a given conversation.

    Args:
        conversation_id: The ID of the conversation.
        current_user: The current authenticated user.
        db: The database session.

    Returns:
        A list of messages in the conversation.
    """
    try:
        return conversation_service.get_conversation_messages(db, conversation_id, current_user.id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Conversation not found")

@router.post("/conversations/{conversation_id}/messages", response_model=schemas.ChatMessage)
async def create_message(
    conversation_id: int,
    message: schemas.ChatMessageCreate,
    background_tasks: BackgroundTasks,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Creates a new message in a conversation.

    Args:
        conversation_id: The ID of the conversation.
        message: The message to create.
        background_tasks: FastAPI background tasks.
        current_user: The current authenticated user.
        db: The database session.

    Returns:
        The newly created message.
    """
    try:
        # ユーザーメッセージを保存
        user_message = conversation_service.save_message(
            db, conversation_id, "user", message.content, current_user.id
        )
        
        # バックグラウンドでLLM処理
        background_tasks.add_task(
            chat_processor.process_user_message,
            conversation_id=conversation_id,
            user_message=message.content,
            user_id=current_user.id,
            db=db,
            model=message.model
        )
        
        return user_message
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error in create_message: {type(e).__name__}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")

@router.post("/recommend-layout")
async def recommend_layout_endpoint(
    request: Request,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db)
):
    """
    Recommends a network layout algorithm based on a description and purpose.

    Args:
        request: The incoming request.
        current_user: The current authenticated user.
        db: The database session.

    Returns:
        A dictionary with the recommended layout and an explanation.
    """
    try:
        body = await request.json()
        description = body.get("description", "")
        purpose = body.get("purpose", "")
        
        if not description or not purpose:
            raise HTTPException(status_code=400, detail="Both description and purpose are required")
            
        result = await layout_recommender.recommend_layout(description, purpose)
        
        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("error", "Layout recommendation failed"))
            
        return result
        
    except Exception as e:
        logger.error(f"Error in recommend_layout_endpoint: {type(e).__name__}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An error occurred: {str(e)}")

@router.post("/process")
async def process_chat(
    request: Request,
    current_user: models.User = Depends(auth.get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    Processes a chat message and returns the response.

    This endpoint handles the main chat functionality, including conversation
    creation, message history, and interaction with the LLM and network tools.

    Args:
        request: The incoming request.
        current_user: The current authenticated user.
        db: The database session.

    Returns:
        A dictionary with the response and any network updates.
    """
    try:
        body = await request.json()
        message_content = body.get("message", "")
        conversation_id = body.get("conversation_id")
        model = body.get("model")

        if not message_content:
            raise HTTPException(status_code=400, detail="Message is required")

        # 会話が存在しない場合は新規作成
        if not conversation_id:
            db_conversation = conversation_service.create_conversation(
                db, current_user.id, "New Conversation"
            )
            conversation_id = db_conversation.id

        # メッセージを処理
        result = await chat_processor.process_user_message(
            conversation_id=conversation_id,
            user_message=message_content,
            user_id=current_user.id,
            db=db,
            model=model
        )

        return result

    except ValueError as e:
        # 会話が見つからない場合など
        logger.error(f"Value error in process_chat: {str(e)}")
        return {
            "success": False,
            "content": str(e),
            "error_code": "VALUE_ERROR"
        }
    except Exception as e:
        logger.error(f"Error in process_chat: {type(e).__name__}: {e}", exc_info=True)
        return {
            "success": False,
            "content": f"An unexpected error occurred: {str(e)}",
            "error_code": "PROCESS_ERROR",
            "context": {"error_type": type(e).__name__}
        }