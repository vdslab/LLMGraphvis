from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel, Field


class UserBase(BaseModel):
    username: str


class UserCreate(UserBase):
    username: str = Field(min_length=3, max_length=50, pattern=r"^[A-Za-z0-9._-]+$")
    password: str = Field(min_length=8, max_length=128)


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
    provider: Optional[str] = None
    model: Optional[str] = None


class ChatUpdate(BaseModel):
    name: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None


class Chat(ChatBase):
    id: int
    user_id: int
    network_id: int
    provider: Optional[str] = None
    model: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class LlmModelOption(BaseModel):
    id: str
    label: str


class LlmProviderOption(BaseModel):
    id: str
    label: str
    models: List[LlmModelOption]


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


class LlmUsageBase(BaseModel):
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    cached_input_tokens: int
    iteration_count: int
    estimated_cost_usd: Optional[float] = None


class LlmUsage(LlmUsageBase):
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
    usage: Optional[LlmUsage] = None
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
