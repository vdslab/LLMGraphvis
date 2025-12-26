from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from .base import BaseSchema

# --- Config Models ---


class NodeColorConfig(BaseModel):
    scale_type: Literal["LINEAR", "CATEGORICAL", "RANKING"] = Field(
        ..., description="Type of color scaling to apply."
    )
    attribute: str = Field(
        ..., description="Name of the node attribute to map to color."
    )
    gradient: Optional[List[str]] = Field(
        None, description="List of [start_color, end_color] for LINEAR scale."
    )
    color_map: Optional[Dict[str, str]] = Field(
        None,
        description="Dictionary mapping attribute values to hex colors for CATEGORICAL scale.",
    )
    ranking_rules: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="List of rules for RANKING scale (e.g. {'top': 10, 'color': '#FF0000'}).",
    )
    default_color: Optional[str] = Field(
        None, description="Fallback color if attribute is missing or no rule matches."
    )
    fixed_mapping: bool = Field(
        False, description="If True, do not auto-generate colors for values not in color_map."
    )


class NodeSizeConfig(BaseModel):
    attribute: str = Field(
        ..., description="Name of the node attribute to map to size."
    )
    min: Optional[float] = Field(None, description="Minimum node radius (default: 5).")
    max: Optional[float] = Field(None, description="Maximum node radius (default: 20).")
    default: Optional[float] = Field(
        None, description="Default radius if attribute is missing."
    )


class EdgeWidthConfig(BaseModel):
    attribute: str = Field(
        ..., description="Name of the edge attribute to map to width."
    )
    min: Optional[float] = Field(None, description="Minimum edge width (default: 1).")
    max: Optional[float] = Field(None, description="Maximum edge width (default: 10).")
    default: Optional[float] = Field(
        None, description="Default width if attribute is missing."
    )


class EdgeColorConfig(BaseModel):
    attribute: str = Field(
        ..., description="Name of the edge attribute to map to color."
    )
    scale_type: Literal["LINEAR", "CATEGORICAL"] = Field(
        ..., description="Type of color scaling."
    )
    gradient: Optional[List[str]] = Field(
        None, description="List of [start_color, end_color] for LINEAR scale."
    )
    color_map: Optional[Dict[str, str]] = Field(
        None, description="Dictionary mapping attribute values to hex colors."
    )
    default_color: Optional[str] = Field(None, description="Fallback color.")


class NodeLabelConfig(BaseModel):
    attribute: str = Field(..., description="Name of the attribute to show as label.")
    show_all: bool = Field(
        False,
        description="If True, shows labels for all nodes. If False, likely only on hover/select.",
    )


# --- Request Model ---


class VisualizationRequest(BaseSchema):
    layout_name: Optional[str] = None
    focus_network_id: Optional[int] = None

    node_size_config: Optional[NodeSizeConfig] = None
    node_color_config: Optional[NodeColorConfig] = None

    edge_width_config: Optional[EdgeWidthConfig] = None
    edge_color_config: Optional[EdgeColorConfig] = None

    node_label_config: Optional[NodeLabelConfig] = None

    # Keeping these generic for now as they might be complex or legacy
    context_config: Optional[Dict[str, Any]] = None
    focus_config: Optional[Dict[str, Any]] = None
    custom_node_colors: Optional[List[Dict[str, Any]]] = None
