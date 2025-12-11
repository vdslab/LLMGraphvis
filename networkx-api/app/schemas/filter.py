from pydantic import BaseModel
from typing import List, Optional, Union

class Range(BaseModel):
    min: Optional[float] = None
    max: Optional[float] = None

class AttributeCondition(BaseModel):
    attribute_name: str
    ranges: Optional[List[Range]] = None
    categories: Optional[List[Union[str, float, int]]] = None

class SubgraphFilterRequest(BaseModel):
    conditions: List[AttributeCondition]
    suffix: Optional[str] = "Filtered"
