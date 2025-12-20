from .base import BaseSchema


class LayoutRequest(BaseSchema):
    layout_name: str  # forceatlas2, spring, etc.
