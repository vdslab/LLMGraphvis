from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime

class UserBase(BaseModel):
    username: str

class UserCreate(UserBase):
    password: str

class User(UserBase):
    id: int
    
    class Config:
        orm_mode = True

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: Optional[str] = None

class ChatBase(BaseModel):
    name: str

class ChatCreate(ChatBase):
    pass

class Chat(ChatBase):
    id: int
    user_id: int
    network_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True

class ChatMessageBase(BaseModel):
    role: str
    content: str
    meta_data: Optional[Dict[str, Any]] = None

class ChatMessageCreate(ChatMessageBase):
    pass

class ChatMessage(ChatMessageBase):
    id: int
    chat_id: int
    created_at: datetime

    class Config:
        orm_mode = True

class ChatProcessRequest(BaseModel):
    message: ChatMessageBase
