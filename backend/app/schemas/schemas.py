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
        from_attributes = True

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
        from_attributes = True

class Network(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    network_id: Optional[int] = None # For compatibility if needed, though usually just id
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class ChatWithNetwork(Chat):
    """Chat with network information"""
    network: Optional[Any] = None # Allow both Dict and Network model
    
    class Config:
        from_attributes = True

class ChatMessageBase(BaseModel):
    role: str
    content: str
    content: str

class ChatMessageCreate(ChatMessageBase):
    pass

class ChatMessage(ChatMessageBase):
    id: int
    chat_id: int
    created_at: datetime

    class Config:
        from_attributes = True

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

class CreateComponentContainingNodeRequest(BaseModel):
    node_id: str

class Subgraph(BaseModel):
    id: int
    name: str
    created_at: datetime

