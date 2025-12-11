from typing import Optional, Dict, List, Any
from .base import BaseSchema

class VisualizationRequest(BaseSchema):
    layout_name: Optional[str] = "forceatlas2"
    focus_network_id: Optional[int] = None
    node_size_config: Optional[Dict[str, Any]] = None
    node_color_config: Optional[Dict[str, Any]] = None
    edge_width_config: Optional[Dict[str, Any]] = None
    edge_color_config: Optional[Dict[str, Any]] = None
    context_config: Optional[Dict[str, Any]] = None
    focus_config: Optional[Dict[str, Any]] = None
    node_label_config: Optional[Dict[str, Any]] = None
    custom_node_colors: Optional[List[Dict[str, Any]]] = None
