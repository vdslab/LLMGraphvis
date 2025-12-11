from typing import Optional
from .base import BaseSchema

class CentralityRequest(BaseSchema):
    centrality_type: str # degree, betweenness, closeness, eigenvector, pagerank

class TopNodesRequest(BaseSchema):
    metric: str
    k: Optional[int] = 10
