from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
import json

# --- User Schemas ---


class UserBase(BaseModel):
    username: str


class UserCreate(UserBase):
    password: str


class User(UserBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {
        "from_attributes": True
    }

# --- Token Schemas ---


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: Optional[str] = None

# --- Network Schemas ---


class NetworkBase(BaseModel):
    name: str = "Untitled Network"
    graphml_content: str


class NetworkCreate(NetworkBase):
    pass


class NetworkUpdate(BaseModel):
    name: Optional[str] = None
    graphml_content: Optional[str] = None


class Network(NetworkBase):
    id: int
    conversation_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = {
        "from_attributes": True
    }

# --- Conversation Schemas ---


class ConversationBase(BaseModel):
    title: str = "New Conversation"


class ConversationCreate(ConversationBase):
    pass


class Conversation(ConversationBase):
    id: int
    user_id: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    network: Optional[Network] = None

    model_config = {
        "from_attributes": True
    }

# --- Chat Message Schemas ---


class ChatMessageBase(BaseModel):
    content: str
    role: str = "user"


class ChatMessageCreate(ChatMessageBase):
    pass


class ChatMessage(ChatMessageBase):
    id: int
    user_id: int
    conversation_id: int
    meta_data: Optional[str] = "{}"
    created_at: datetime

    model_config = {
        "from_attributes": True
    }

    def get_metadata(self) -> Dict[str, Any]:
        """Get metadata as a dictionary."""
        try:
            return json.loads(self.meta_data)
        except (json.JSONDecodeError, TypeError):
            return {}

# --- LLM Provider Schemas ---


class LLMProviderSettings(BaseModel):
    provider: str = Field(...,
                          description="LLM provider: 'google' or 'openai'")
    google_api_key: Optional[str] = Field(None, description="Google API key")
    openai_api_key: Optional[str] = Field(None, description="OpenAI API key")
    openai_model: Optional[str] = Field(
        "gpt-4o", description="OpenAI model name")


class LLMProviderUpdate(BaseModel):
    provider: Optional[str] = Field(
        None, description="LLM provider: 'google' or 'openai'")
    google_api_key: Optional[str] = Field(None, description="Google API key")
    openai_api_key: Optional[str] = Field(None, description="OpenAI API key")
    openai_model: Optional[str] = Field(None, description="OpenAI model name")


class LLMProviderResponse(BaseModel):
    provider: str
    has_google_api_key: bool
    has_openai_api_key: bool
    openai_model: Optional[str]
    available_providers: List[str] = ["google", "openai"]
