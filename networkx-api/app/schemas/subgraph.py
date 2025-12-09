from typing import List, Optional
from .base import BaseSchema

class EgoNetworkRequest(BaseSchema):
    center_node_id: str
    radius: int

class PathSubgraphRequest(BaseSchema):
    source_node_id: str
    target_node_id: str

class NodesSubgraphRequest(BaseSchema):
    node_ids: List[str]

class KCoreRequest(BaseSchema):
    k: int
