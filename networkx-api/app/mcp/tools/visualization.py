from typing import List, Optional, Dict, Any, Annotated
from pydantic import Field
from app.core.mcp import mcp
from app.core import database
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
    layout_name: Annotated[Optional[str], Field(description="Layout algorithm to use (e.g., 'forceatlas2', 'circular'). If None, preserves current.")] = None,
    node_color_config: Annotated[Optional[NodeColorConfig], Field(description="Complex object for node coloring configuration.")] = None,
    node_size_config: Annotated[Optional[NodeSizeConfig], Field(description="Complex object for node sizing configuration.")] = None,
    edge_width_config: Annotated[Optional[EdgeWidthConfig], Field(description="Complex object for edge width configuration.")] = None,
    edge_color_config: Annotated[Optional[EdgeColorConfig], Field(description="Complex object for edge color configuration.")] = None,
    context_config: Annotated[Optional[dict], Field(description="Configuration for context view (visual style of non-focused elements).")] = None,
    focus_config: Annotated[Optional[dict], Field(description="Configuration for focus view (visual style of focused elements).")] = None,
    node_label_config: Annotated[Optional[NodeLabelConfig], Field(description="Configuration for node labels.")] = None,
    custom_node_colors: Annotated[Optional[list], Field(description="List of specific {'node_id': 'id', 'color': 'hex'} overrides.")] = None,
) -> dict:
    """
    [INITIALIZER / RESET TOOL]
    Generates the network visualization. Use this tool primarily for:
    1.  **Initialization**: The first time you visualize a network.
    2.  **Full Reset**: If you want to change EVERYTHING at once (layout, color, size).
    
    **Best Practice**:
    -   For simple updates (e.g., "Change color to red"), use the specialized tools:
        -   `update_node_color`
        -   `update_node_size`
        -   `update_layout`
    -   This tool allows complex nested configurations but is harder to get right.
    
    **Persisted State**:
    -   Any config provided here (not None) is saved to the database.
    -   Any config set to None will PRESERVE the existing state from the database.
        
    Returns:
        dict: The complete visualization data {"nodes": [...], "links": [...], "legend": ...}
    """
    db = database.SessionLocal()
    try:
        from app.logic import visualization_builder
        # 2. Build Visualization
        vis_data = visualization_builder.build_visualization(
            db,
            network_id,
            node_color_config,
            node_size_config,
            edge_width_config,
            edge_color_config,
            context_config,
            focus_config,  
            node_label_config, 
            custom_node_colors
        )
        return vis_data
    except Exception as e:
        logger.error(f"generate_visualization failed: {e}")
        logger.error(traceback.format_exc())
        return {"error": f"{type(e).__name__}: {str(e)}"}
    finally:
        db.close()


@mcp.tool()
def get_visualization_state(
    network_id: Annotated[int, Field(description="The ID of the network.")]
) -> dict:
    """
    Returns the current visualization configuration (color mapping, sizing, layout, etc.).
    By reading this, you can understand how the network is currently visualized.
        
    Returns:
        dict: A dictionary containing 'layout_name', 'node_size', 'node_color', etc.
    """
    db = database.SessionLocal()
    try:
        from app.logic import visualization_builder
        return visualization_builder.get_current_visualization(db, network_id)
    except Exception as e:
        logger.error(f"get_visualization_state failed: {e}")
        return {"error": f"{type(e).__name__}: {str(e)}"}
    finally:
        db.close()


@mcp.tool()
def update_layout(
    network_id: Annotated[int, Field(description="The ID of the network.")],
    layout_name: Annotated[str, Field(description="The layout algorithm. Supported: 'forceatlas2', 'spring', etc.")]
) -> dict:
    """
    Updates the network layout.
        
    Returns:
        dict: Updated visualization data.
    """

    db = database.SessionLocal()
    try:
        from app.logic import layout, visualization_builder
        # Calculate new layout
        layout.calculate_layout(network_id, layout_name, db)
        
        # Build new visualization (updating state)
        # Note: We don't change color/size configs, just layout
        return visualization_builder.build_visualization(
            db, 
            network_id,
            layout_name=layout_name # Update the layout preference
        )
    except Exception as e:
        logger.error(f"update_layout failed: {e}")
        return {"error": str(e)}
    finally:
        db.close()


@mcp.tool()
def update_node_color(
    network_id: Annotated[int, Field(description="The ID of the network.")],
    attribute: Annotated[str, Field(description="The attribute name (e.g., 'country', 'modularity_class') to use for coloring.")],
    scale_type: Annotated[str, Field(description="How to map values to colors. 'CATEGORICAL' (distinct), 'LINEAR' (gradient), 'RANKING' (top-k).")] = "CATEGORICAL",
    mapping: Annotated[Optional[Dict[str, str]], Field(description="Optional dictionary for explicit value->color pairs. e.g. {'Japan': 'red'}.")] = None,
    default_color: Annotated[Optional[str], Field(description="Fallback color for nodes that don't match mapping or are null. Default: '#d3d3d3'.")] = None,
    fixed: Annotated[bool, Field(description="If True, strictly uses mapping+default. If False (default), auto-generates types.")] = False,
    gradient: Annotated[Optional[List[str]], Field(description="List of colors for LINEAR scale (e.g. ['#ffffff', '#ff0000']).")] = None
) -> dict:
    """
    Updates the node coloring based on an attribute.
    
    Returns:
        dict: Updated visualization data.
        
    Example:
    To color "Austria" nodes red and all others gray:
    >>> update_node_color(
            network_id=1,
            attribute="country",
            scale_type="CATEGORICAL",
            mapping={"Austria": "red"},
            default_color="#d3d3d3",
            fixed=True
        )
    """
    db = database.SessionLocal()
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
        return visualization_builder.build_visualization(
            db, network_id, node_color_config=config
        )
    except Exception as e:
        logger.error(f"update_node_color failed: {e}")
        return {"error": f"{type(e).__name__}: {str(e)}"}
    finally:
        db.close()


@mcp.tool()
def update_node_size(
    network_id: Annotated[int, Field(description="The ID of the network.")],
    attribute: Annotated[str, Field(description="The attribute name (number) to use for sizing.")],
    min_size: Annotated[float, Field(description="Node radius for the minimum attribute value.")] = 5.0,
    max_size: Annotated[float, Field(description="Node radius for the maximum attribute value.")] = 20.0
) -> dict:
    """
    Updates the node sizing based on an attribute.
    
    Returns:
        dict: Updated visualization data.
    """
    db = database.SessionLocal()
    try:
        from app.logic import visualization_builder
        config = NodeSizeConfig(
            attribute=attribute,
            min=min_size,
            max=max_size
        )
        return visualization_builder.build_visualization(
            db, network_id, node_size_config=config
        )
    except Exception as e:
        logger.error(f"update_node_size failed: {e}")
        return {"error": f"{type(e).__name__}: {str(e)}"}

    finally:
        db.close()


@mcp.tool()
def switch_to_network(
    network_id: Annotated[int, Field(description="The ID of the network to switch context to (e.g. returning to main graph).")]
) -> dict:
    """
    Switches the active view to a specific network (e.g., returning to the main graph from a subgraph).
    Retains the existing visualization state of that network.
    
    Returns:
        dict: The visualization data for the target network.
    """
    db = database.SessionLocal()
    try:
        from app.logic import visualization_builder
        # Build visualization with stored configs (pass nothing to preserve state)
        vis_data = visualization_builder.build_visualization(
            db,
            network_id
        )
        return vis_data
    except Exception as e:
        logger.error(f"switch_to_network failed: {e}")
        return {"error": f"{type(e).__name__}: {str(e)}"}
    finally:
        db.close()
