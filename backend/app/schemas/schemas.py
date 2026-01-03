from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel


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


class ChatUpdate(ChatBase):
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
    network_id: Optional[int] = (
        None  # For compatibility if needed, though usually just id
    )
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ChatWithNetwork(Chat):
    """Chat with network information"""

    network: Optional[Any] = None  # Allow both Dict and Network model

    class Config:
        from_attributes = True


class ChatMessageBase(BaseModel):
    role: str
    content: str


class ChatMessageCreate(ChatMessageBase):
    pass


class ToolExecutionBase(BaseModel):
    tool_name: str
    arguments: Optional[Any] = None
    result: Optional[Any] = None
    thought: Optional[str] = None
    status: str
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class ToolExecution(ToolExecutionBase):
    id: int
    message_id: int
    created_at: datetime

    class Config:
        from_attributes = True


class ChatMessage(ChatMessageBase):
    id: int
    chat_id: int
    meta_data: Optional[Any] = None
    tool_executions: List[ToolExecution] = []
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
