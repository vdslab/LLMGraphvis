"""
モジュール名: conversation_service.py
責務: 会話とメッセージのCRUD操作
依存: models, sqlalchemy.orm.Session, utils.create_empty_graphml
依存先: routers/chat.py, services/chat_processor.py

主要な関数:
- create_conversation: 新規会話作成（初期Networkも同時作成）
- get_user_conversations: ユーザーの会話一覧取得
- get_conversation_messages: 会話のメッセージ一覧取得
- save_message: メッセージ保存

変更時の注意:
- メッセージ保存時はmeta_dataはJSON文字列で保持
- 会話取得時は必ずuser_idでフィルタすること
"""

from typing import List, Any
import json
import logging

from sqlalchemy.orm import Session

import models
import schemas  # noqa: F401  # 型参照用途
from utils import create_empty_graphml

logger = logging.getLogger(__name__)


def _ensure_conversation_owned(db: Session, conversation_id: int, user_id: int) -> models.Conversation:
    """
    会話がユーザーに帰属していることを検証し、会話を返す

    Args:
        db: DBセッション
        conversation_id: 会話ID
        user_id: ユーザーID

    Returns:
        models.Conversation

    Raises:
        ValueError: 会話が存在しない/権限がない
    """
    conv = (
        db.query(models.Conversation)
          .filter(models.Conversation.id == conversation_id,
                  models.Conversation.user_id == user_id)
          .first()
    )
    if conv is None:
        logger.error(f"Conversation not found or not owned. conv_id={conversation_id}, user_id={user_id}")
        raise ValueError("Conversation not found")
    return conv


def create_conversation(db: Session, user_id: int, title: str) -> models.Conversation:
    """
    会話を作成し、空GraphMLのNetworkを関連付けて返す

    Args:
        db: DBセッション
        user_id: ユーザーID
        title: 会話タイトル

    Returns:
        作成された会話(models.Conversation)
    """
    try:
        db_conversation = models.Conversation(title=title or "New Conversation", user_id=user_id)
        db.add(db_conversation)
        db.commit()
        db.refresh(db_conversation)

        db_network = models.Network(
            name="Initial Network",
            conversation_id=db_conversation.id,
            graphml_content=create_empty_graphml(),
        )
        db.add(db_network)
        db.commit()
        db.refresh(db_conversation)
        return db_conversation
    except Exception as e:
        logger.error(f"Error creating conversation: {type(e).__name__}: {e}", exc_info=True)
        db.rollback()
        raise


def get_user_conversations(db: Session, user_id: int) -> List[models.Conversation]:
    """
    ユーザーの会話一覧を取得

    Args:
        db: DBセッション
        user_id: ユーザーID

    Returns:
        会話リスト
    """
    return (
        db.query(models.Conversation)
          .filter(models.Conversation.user_id == user_id)
          .order_by(models.Conversation.created_at)
          .all()
    )


def get_conversation_messages(db: Session, conversation_id: int, user_id: int) -> List[models.ChatMessage]:
    """
    会話のメッセージ一覧を取得（作成日時順）

    Args:
        db: DBセッション
        conversation_id: 会話ID
        user_id: ユーザーID

    Returns:
        メッセージリスト
    """
    _ensure_conversation_owned(db, conversation_id, user_id)
    return (
        db.query(models.ChatMessage)
          .filter(models.ChatMessage.conversation_id == conversation_id)
          .order_by(models.ChatMessage.created_at)
          .all()
    )


def save_message(db: Session, conversation_id: int, role: str, content: Any, user_id: int) -> models.ChatMessage:
    """
    メッセージを保存

    Args:
        db: DBセッション
        conversation_id: 会話ID
        role: "user" | "assistant"
        content: 文字列または辞書
        user_id: ユーザーID

    Returns:
        保存したメッセージ(models.ChatMessage)
    """
    _ensure_conversation_owned(db, conversation_id, user_id)

    # contentを文字列へ正規化
    if isinstance(content, dict):
        normalized = json.dumps(content)
    else:
        normalized = str(content)

    try:
        db_message = models.ChatMessage(
            content=normalized,
            role=role,
            user_id=user_id,
            conversation_id=conversation_id,
        )
        db.add(db_message)
        db.commit()
        db.refresh(db_message)
        return db_message
    except Exception as e:
        logger.error(f"Error saving message: {type(e).__name__}: {e}", exc_info=True)
        db.rollback()
        raise


__all__ = [
    "create_conversation",
    "get_user_conversations",
    "get_conversation_messages",
    "save_message",
]