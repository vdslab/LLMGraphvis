from typing import List

from google.genai import types
from sqlalchemy.orm import Session

from app import models


def build_history(chat_id: int, user_message: str, db: Session) -> List[types.Content]:
    """Build conversation history with few-shot examples."""
    messages = (
        db.query(models.ChatMessage)
        .filter(models.ChatMessage.chat_id == chat_id)
        .order_by(models.ChatMessage.created_at.asc())
        .all()
    )

    history = []
    for msg in messages:
        role = "user" if msg.role == "user" else "model"
        history.append(types.Content(role=role, parts=[types.Part(text=msg.content)]))

    # Check if the last message in history is the same as the user_message
    # This prevents duplication if the message was already saved to DB and fetched
    if not history or history[-1].parts[0].text != user_message:
        history.append(
            types.Content(role="user", parts=[types.Part(text=user_message)])
        )

    return history
