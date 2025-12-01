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

class ChatWithNetwork(Chat):
    """Chat with network information"""
    network: Optional[Dict[str, Any]] = None
    
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

class ChatProcessMessage(BaseModel):
    content: str

class ChatProcessRequest(BaseModel):
    message: ChatProcessMessage

class CreateEgoNetworkRequest(BaseModel):
    center_node_id: str
    radius: int

class CreateSubgraphFromNodesRequest(BaseModel):
    node_ids: List[str]

class CreatePathSubgraphRequest(BaseModel):
    source_node_id: str
    target_node_id: str

class CreateKCoreSubgraphRequest(BaseModel):
    k: int

class Subgraph(BaseModel):
    id: int
    name: str
    created_at: datetime

