from typing import Annotated, Optional, Dict, List
from pydantic import Field
from app.core.mcp import mcp
from app.core.database import get_db_context
import logging
import traceback

from app.schemas.visualization import (
    EdgeColorConfig,
    EdgeWidthConfig,
    NodeColorConfig,
    NodeLabelConfig,
    NodeSizeConfig,
)

logger = logging.getLogger(__name__)

@mcp.tool()
def generate_visualization(
    network_id: Annotated[int, Field(description="The ID of the network.")],
    node_color: Annotated[Optional[NodeColorConfig], Field(description="Configuration for node coloring.")] = None,
    node_size: Annotated[Optional[NodeSizeConfig], Field(description="Configuration for node sizing.")] = None,
    edge_width_attribute: Annotated[Optional[str], Field(description="Attribute for edge width.")] = None
) -> dict:
    """
    Generates the FULL visualization state for a network.
    
    WARNING:
    This tool completely regenerates the visualization data. 
    Use specialized update tools (`update_node_color`, `update_node_size`, `update_layout`) 
    for partial updates to avoid resetting other visual properties unintentionally.

    Returns:
        dict: The complete visualization object (nodes, links) ready for the frontend.
    """
    with get_db_context() as db:
        try:
            from app.logic import visualization_builder
            
            ew_config = None
            if edge_width_attribute:
                ew_config = {"attribute": edge_width_attribute}
                
            vis_data = visualization_builder.build_visualization(
                db, 
                network_id, 
                node_color_config=node_color, 
                node_size_config=node_size, 
                edge_width_config=ew_config
            )
            vis_data["network_id"] = network_id
            return vis_data
        except Exception as e:
            logger.error(f"generate_visualization failed: {e}")
            logger.error(traceback.format_exc())
            raise RuntimeError(f"Visualization generation failed: {str(e)}") from e


@mcp.tool()
def get_visualization_state(
    network_id: Annotated[int, Field(description="The ID of the network.")]
) -> dict:
    """
    Retrieves the CURRENT stored visualization state without regenerating it.
    Useful for checking what is currently displayed or retrieving the last known state.

    Returns:
        dict: The visualization object.
    """
    with get_db_context() as db:
        try:
            from app.logic import visualization_builder
            vis_data = visualization_builder.get_stored_visualization(db, network_id)
            if vis_data:
                vis_data["network_id"] = network_id
            return vis_data
        except Exception as e:
            logger.error(f"get_visualization_state failed: {e}")
            raise RuntimeError(f"Failed to get visualization state: {str(e)}") from e


@mcp.tool()
def update_layout(
    network_id: Annotated[int, Field(description="The ID of the network.")]
) -> dict:
    """
    Updates the visualization with the latest calculated layout coordinates.
    Call this AFTER `calculate_layout`.
    
    Returns:
        dict: The updated visualization object.
    """
    with get_db_context() as db:
        try:
            from app.logic import visualization_builder
            # Force rebuild to pick up new layout coords from node attributes
            vis_data = visualization_builder.build_visualization(db, network_id)
            vis_data["network_id"] = network_id
            return vis_data
        except Exception as e:
            logger.error(f"update_layout failed: {e}")
            raise RuntimeError(f"Layout update failed: {str(e)}") from e


@mcp.tool()
def update_node_color(
    network_id: Annotated[int, Field(description="The ID of the network.")],
    attribute: Annotated[str, Field(description="Node attribute name to use for coloring.")],
    scale_type: Annotated[str, Field(description="'ordinal' or 'linear'.")],
    mapping: Annotated[Optional[Dict[str, str]], Field(description="Category->Color map for ordinal.")] = None,
    default_color: Annotated[str, Field(description="Fallback color.")] = "#d3d3d3",
    fixed: Annotated[Optional[bool], Field(description="If True, uses fixed mapping.")] = False,
    gradient: Annotated[Optional[Dict[str, str]], Field(description="{'min': '#...', 'max': '#...'} for linear.")] = None
) -> dict:
    """
    Updates ONLY the node colors in the visualization.
    
    Returns:
        dict: The updated visualization object.
    """
    with get_db_context() as db:
        try:
            from app.logic import visualization_builder
            
            # Default to Gray for null/mismatched values if not specified
            if not default_color:
                default_color = "#d3d3d3"

            config = NodeColorConfig(
                attribute=attribute,
                scale_type=scale_type,
                color_map=mapping,
                default_color=default_color,
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
        except Exception as e:
            logger.error(f"update_node_color failed: {e}")
            raise RuntimeError(f"Node color update failed: {str(e)}") from e


@mcp.tool()
def update_node_size(
    network_id: Annotated[int, Field(description="The ID of the network.")],
    attribute: Annotated[str, Field(description="Node attribute name to use for sizing.")],
    min_size: Annotated[Optional[float], Field(description="Min node size. Defaults to adaptive value based on network size (e.g. 5-100).")] = None,
    max_size: Annotated[Optional[float], Field(description="Max node size. Defaults to adaptive value based on network size (e.g. 20-200).")] = None,
    default_size: Annotated[Optional[float], Field(description="Default size used if attribute is missing. Defaults to adaptive value.")] = None
) -> dict:
    """
    Updates ONLY the node sizes in the visualization.
    Typical size values are now in the range of 5 to 200 depending on network density.
    Leave min/max/default as None to use smart adaptive defaults.
    
    Returns:
        dict: The updated visualization object.
    """
    with get_db_context() as db:
        try:
            from app.logic import visualization_builder
            
            config = NodeSizeConfig(
                attribute=attribute,
                min_size=min_size,
                max_size=max_size,
                default_size=default_size
            )
            vis_data = visualization_builder.build_visualization(
                db, 
                network_id, 
                node_size_config=config
            )
            vis_data["network_id"] = network_id
            return vis_data
        except Exception as e:
            logger.error(f"update_node_size failed: {e}")
            raise RuntimeError(f"Node size update failed: {str(e)}") from e


@mcp.tool()
def switch_to_network(
    network_id: Annotated[int, Field(description="The ID of the network to switch to.")]
) -> dict:
    """
    Switches the active view to a different network (e.g., returning to the main graph from a subgraph).
    Retains the last known visualization state of that network.

    Returns:
        dict: The visualization object of the target network.
    """
    with get_db_context() as db:
        try:
            from app.logic import visualization_builder
            vis_data = visualization_builder.get_stored_visualization(db, network_id)
            if vis_data:
                vis_data["network_id"] = network_id
            return vis_data
        except Exception as e:
            logger.error(f"switch_to_network failed: {e}")
            raise RuntimeError(f"Switch network failed: {str(e)}") from e
