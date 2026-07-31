from typing import Annotated, Any, Dict, List, Optional
from pydantic import Field
from app.core.mcp import mcp
from app.core.database import get_db_context
from app.core.decorators import handle_tool_errors
import logging

logger = logging.getLogger(__name__)


@mcp.tool()
@handle_tool_errors
def visualization_set_node_color(
    network_id: Annotated[int, Field(description="The ID of the network.")],
    attribute: Annotated[str, Field(description="Node attribute name to use for coloring (e.g., 'community', 'degree_centrality', 'country').")],
    scale_type: Annotated[str, Field(description="Color scale type: 'CATEGORICAL' (for text/discrete values), 'LINEAR' (for numeric ranges), or 'RANKING' (top-N rules).")],
    mapping: Annotated[Optional[Dict[str, str]], Field(description="For CATEGORICAL: dict mapping attribute values to hex colors, e.g. {\"A\": \"#FF0000\"}. Auto-generated from a 20-color palette if omitted.")] = None,
    gradient: Annotated[Optional[List[str]], Field(description="For LINEAR: list of hex strings ordered from low value to high, e.g. [\"#C6DBEF\", \"#6BAED6\", \"#08306B\"].")] = None,
    ranking_rules: Annotated[Optional[List[Dict[str, Any]]], Field(description="For RANKING: list of rules applied in order, each {\"top\": N, \"color\": \"#RRGGBB\"} — e.g. [{\"top\": 10, \"color\": \"#e15759\"}, {\"top\": 50, \"color\": \"#f28e2b\"}] colors the 10 highest-valued nodes red and the next 40 orange. Everything unmatched gets default_color. Use this for 'highlight the top N' requests, where position in the ordering matters more than the value itself.")] = None,
    default_color: Annotated[str, Field(description="Fallback color for nodes with missing attribute values, or unmatched by any RANKING rule.")] = "#d3d3d3",
    fixed: Annotated[bool, Field(description="If True, only colors nodes whose value is in the mapping; others get default_color.")] = False
) -> dict:
    """
    Updates ONLY the node colors in the visualization based on a node attribute.

    All other visual settings (layout, node sizes, edge styles) are preserved.
    Call `analysis_detect_communities` or `analysis_degree_centrality` first if needed.

    Examples:
    - Color by community: attribute='louvain_community', scale_type='CATEGORICAL'
    - Color by centrality: attribute='betweenness_centrality', scale_type='LINEAR', gradient=['#C6DBEF', '#08306B']
    - Highlight the top 10: attribute='pagerank', scale_type='RANKING', ranking_rules=[{'top': 10, 'color': '#e15759'}]

    Report the returned `legend` mapping to the user using its exact hex codes.
    To return colors to uniform, use `visualization_reset_style(target='node_color')` —
    passing an empty mapping here does not clear anything.

    Returns:
        dict: The updated visualization object (nodes, links, legend).
    """
    with get_db_context() as db:
        from app.logic import visualization_builder
        from app.schemas.visualization import NodeColorConfig

        config = NodeColorConfig(
            attribute=attribute,
            scale_type=scale_type.upper(),
            color_map=mapping,
            ranking_rules=ranking_rules,
            default_color=default_color or "#d3d3d3",
            fixed_mapping=fixed,
            gradient=gradient
        )
        vis_data = visualization_builder.build_visualization(
            db,
            network_id,
            node_color_config=config
        )
        vis_data["network_id"] = network_id
        return vis_data


@mcp.tool()
@handle_tool_errors
def visualization_set_node_size(
    network_id: Annotated[int, Field(description="The ID of the network.")],
    attribute: Annotated[str, Field(description="Node attribute name to use for sizing (e.g., 'degree_centrality', 'pagerank'). Calculate first if needed.")],
    min_size: Annotated[Optional[float], Field(description="Minimum node size (area-proportional; rendered radius = sqrt(size * 10 / π)). Leave as None for adaptive auto-sizing (recommended).")] = None,
    max_size: Annotated[Optional[float], Field(description="Maximum node size (area-proportional; rendered radius = sqrt(size * 10 / π)). Leave as None for adaptive auto-sizing (recommended).")] = None,
    default_size: Annotated[Optional[float], Field(description="Default node size (area-proportional; rendered radius = sqrt(size * 10 / π)) for nodes with missing attribute values.")] = None,
    scaling_factor: Annotated[float, Field(description="Global size multiplier. Use > 1.0 to enlarge all nodes, < 1.0 to shrink.")] = 1.0
) -> dict:
    """
    Updates ONLY the node sizes in the visualization based on a node attribute.

    All other visual settings (layout, colors, edge styles) are preserved.
    Leaving min/max/default as None uses smart adaptive sizing based on network density.

    Note: `size` is not a literal pixel radius — it scales with node area, so doubling
    `size` does not double the visible radius. The frontend renders the visible radius
    as sqrt(size * 10 / π).

    Returns:
        dict: The updated visualization object (nodes, links, legend).
    """
    with get_db_context() as db:
        from app.logic import visualization_builder
        from app.schemas.visualization import NodeSizeConfig

        config = NodeSizeConfig(
            attribute=attribute,
            min=min_size,
            max=max_size,
            default=default_size,
            scaling_factor=scaling_factor,
        )
        vis_data = visualization_builder.build_visualization(
            db,
            network_id,
            node_size_config=config
        )
        vis_data["network_id"] = network_id
        return vis_data


@mcp.tool()
@handle_tool_errors
def visualization_set_node_labels(
    network_id: Annotated[int, Field(description="The ID of the network.")],
    attribute: Annotated[Optional[str], Field(description="Node attribute to display as label (e.g., 'country', 'score'). Pass None to revert to default node labels.")] = None,
    show_all: Annotated[bool, Field(description="If True, shows labels for all nodes simultaneously. If False, labels appear on hover/select only.")] = False
) -> dict:
    """
    Updates which attribute is displayed as the node label.

    Use this to switch from default node IDs/names to showing a specific attribute value
    (e.g., display each node's 'country' or 'score' as its label).
    Pass attribute=None to revert to the default label column.

    Returns:
        dict: The updated visualization object (nodes, links, legend).
    """
    with get_db_context() as db:
        from app.logic import visualization_builder
        from app.schemas.visualization import NodeLabelConfig

        config = NodeLabelConfig(attribute=attribute, show_all=show_all) if attribute else {}
        vis_data = visualization_builder.build_visualization(
            db,
            network_id,
            node_label_config=config
        )
        vis_data["network_id"] = network_id
        return vis_data


@mcp.tool()
@handle_tool_errors
def visualization_set_edge_color(
    network_id: Annotated[int, Field(description="The ID of the network.")],
    attribute: Annotated[str, Field(description="Edge attribute name to use for coloring (e.g., 'weight', 'type').")],
    scale_type: Annotated[str, Field(description="Color scale type: 'CATEGORICAL' (for text/discrete values) or 'LINEAR' (for numeric ranges).")],
    mapping: Annotated[Optional[Dict[str, str]], Field(description="For CATEGORICAL: dict mapping attribute values to hex colors.")] = None,
    gradient: Annotated[Optional[List[str]], Field(description="For LINEAR: list of [start_color, end_color] hex strings.")] = None,
    default_color: Annotated[Optional[str], Field(description="Fallback color for edges with missing attribute values.")] = None
) -> dict:
    """
    Updates ONLY the edge colors in the visualization based on an edge attribute.

    All other visual settings (layout, node colors/sizes, edge widths) are preserved.
    Use `network_list_edge_attributes` first to see what edge attributes are available.

    Returns:
        dict: The updated visualization object (nodes, links, legend).
    """
    with get_db_context() as db:
        from app.logic import visualization_builder
        from app.schemas.visualization import EdgeColorConfig

        config = EdgeColorConfig(
            attribute=attribute,
            scale_type=scale_type.upper(),
            color_map=mapping,
            gradient=gradient,
            default_color=default_color
        )
        vis_data = visualization_builder.build_visualization(
            db,
            network_id,
            edge_color_config=config
        )
        vis_data["network_id"] = network_id
        return vis_data


@mcp.tool()
@handle_tool_errors
def visualization_set_edge_width(
    network_id: Annotated[int, Field(description="The ID of the network.")],
    attribute: Annotated[str, Field(description="Edge attribute name to use for width (e.g., 'weight').")],
    min_width: Annotated[Optional[float], Field(description="Minimum edge width in pixels. Defaults to adaptive.")] = None,
    max_width: Annotated[Optional[float], Field(description="Maximum edge width in pixels. Defaults to adaptive.")] = None,
    default_width: Annotated[Optional[float], Field(description="Default width for edges with missing attribute values.")] = None
) -> dict:
    """
    Updates ONLY the edge widths in the visualization based on an edge attribute.

    All other visual settings (layout, node styles, edge colors) are preserved.
    Commonly used with the 'weight' attribute to show edge strength.

    Returns:
        dict: The updated visualization object (nodes, links, legend).
    """
    with get_db_context() as db:
        from app.logic import visualization_builder
        from app.schemas.visualization import EdgeWidthConfig

        config = EdgeWidthConfig(
            attribute=attribute,
            min=min_width,
            max=max_width,
            default=default_width
        )
        vis_data = visualization_builder.build_visualization(
            db,
            network_id,
            edge_width_config=config
        )
        vis_data["network_id"] = network_id
        return vis_data
