from typing import Optional
from pydantic import BaseModel
from datetime import datetime

class UpdateNetworkMetadataRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None

class NetworkMetadataResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    is_subgraph: bool
    parent_network_id: Optional[int] = None
