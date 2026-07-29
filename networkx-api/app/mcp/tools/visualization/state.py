from typing import Annotated
from pydantic import Field
from app.core.mcp import mcp
from app.core.database import get_db_context
from app.core.decorators import handle_tool_errors
import logging

logger = logging.getLogger(__name__)


@mcp.tool()
@handle_tool_errors
def visualization_generate(
    network_id: Annotated[int, Field(description="The ID of the network.")]
) -> dict:
    """
    Regenerates the FULL visualization for a network using its last saved style configuration.

    Use this to get a fresh visualization after changes to the graph structure,
    or after importing/editing data. Preserves the last layout, colors, and sizes.

    WARNING: This regenerates everything from scratch. Use specialized `visualization_set_*`
    tools for partial visual updates to avoid accidentally resetting other styles.

    Returns:
        dict: The complete visualization object (nodes, links, legend).
    """
    with get_db_context() as db:
        from app.logic import visualization_builder
        vis_data = visualization_builder.build_visualization(db, network_id)
        vis_data["network_id"] = network_id
        return vis_data


@mcp.tool()
@handle_tool_errors
def visualization_get_state(
    network_id: Annotated[int, Field(description="The ID of the network.")]
) -> dict:
    """
    Returns the current visualization configuration (layout, color/size settings) without re-rendering.

    Use this to inspect what visual settings are currently active without the overhead
    of a full re-render. Returns config dicts, not node/edge data.

    Returns:
        dict: Current visual configuration (layout_name, node_size, node_color, edge_width, etc.).
    """
    with get_db_context() as db:
        from app.logic import visualization_builder
        return visualization_builder.get_current_visualization(db, network_id)


@mcp.tool()
@handle_tool_errors
def visualization_apply_layout(
    network_id: Annotated[int, Field(description="The ID of the network.")]
) -> dict:
    """
    Re-renders the visualization using the most recently calculated layout coordinates.

    Call this AFTER any layout tool (`layout_forceatlas2`, `layout_spring`, etc.)
    to update the display. All current style settings (colors, sizes) are preserved.

    Returns:
        dict: The updated visualization object (nodes, links, legend).
    """
    with get_db_context() as db:
        from app.logic import visualization_builder
        vis_data = visualization_builder.build_visualization(db, network_id)
        vis_data["network_id"] = network_id
        return vis_data


@mcp.tool()
@handle_tool_errors
def visualization_switch_network(
    network_id: Annotated[int, Field(description="The ID of the network to switch to.")]
) -> dict:
    """
    Switches the active view to a different network and renders its last saved visualization.

    Use this to navigate between the main graph and a subgraph, or between multiple
    loaded networks. The last known layout and styles for the target network are preserved.

    Returns:
        dict: The visualization object of the target network (nodes, links, legend).
    """
    with get_db_context() as db:
        from app.logic import visualization_builder
        vis_data = visualization_builder.build_visualization(db, network_id)
        vis_data["network_id"] = network_id
        return vis_data
