from typing import Annotated, List
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
    Renders the network and returns the visualization, using its saved style configuration.

    This is the tool to call whenever the display needs to be (re)drawn: after computing a
    layout with any `layout_*` tool, after editing graph data, or to recover the current
    view. It does NOT reset anything — the last saved layout, colors, sizes, and labels are
    all reloaded and reapplied, so calling it is always safe.

    To change one visual channel, use the specific `visualization_set_*` tool instead; each
    of those renders as part of its own work, so a separate call here is unnecessary after
    one of them.

    The result also carries `layout_quality`, readability metrics of the drawing as
    the user sees it, so you can judge a layout without seeing it:
    - `node_overlap`: share of nodes touching another node (0 is ideal).
    - `crossings` / `crossings_per_edge`: edge crossings (`crossings_sampled` = estimated).
    - `edge_length_cv`: unevenness of edge lengths (0 = all equal).
    - `core_extent`: share of the canvas used by the central 90% of nodes; small means a
      few outlying nodes are squeezing everything else together.
    - `aspect`: how much the drawing is stretched to fill the square canvas (1 = not).
    - `occupancy`: how evenly nodes fill the canvas.
    - `score`: combined penalty for comparing layouts of this network (lower is better).
    - `issues`: the problems above that exceed their thresholds.
    `layout_suggest_parameters` searches for parameters that reduce these issues.

    Returns:
        dict: The complete visualization object (nodes, links, legend, layout_quality).
    """
    with get_db_context() as db:
        from app.logic import visualization_builder
        vis_data = visualization_builder.build_visualization(
            db, network_id, with_quality=True
        )
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
    DEPRECATED — use `visualization_generate` instead, which does exactly the same thing.

    This name is retained only so existing conversations do not break. It is byte-for-byte
    identical to `visualization_generate`: both re-render the network from its saved
    configuration, which includes the most recently computed layout.

    Returns:
        dict: The updated visualization object (nodes, links, legend, layout_quality).
    """
    with get_db_context() as db:
        from app.logic import visualization_builder
        vis_data = visualization_builder.build_visualization(
            db, network_id, with_quality=True
        )
        vis_data["network_id"] = network_id
        return vis_data


@mcp.tool()
@handle_tool_errors
def visualization_reset_style(
    network_id: Annotated[int, Field(description="The ID of the network.")],
    targets: Annotated[List[str], Field(description="Which visual channels to return to their default. Any of: 'node_color', 'node_size', 'node_label', 'edge_color', 'edge_width', 'highlight'. Pass several to reset several at once; pass only the ones you mean, since the rest are preserved.")]
) -> dict:
    """
    Returns one or more visual channels to their default (uniform) appearance.

    This is the ONLY way to un-set a style. The `visualization_set_*` tools deliberately
    preserve any channel you do not pass, which means there is no value you can pass them
    to clear one — an omitted or empty argument reads as "keep what is there".

    The main use is after filtering a subgraph down to a single value of the attribute that
    color encodes: every remaining node then has the same color and the legend is
    meaningless, so node_color should be reset while other channels (e.g. size mapped to a
    centrality metric) are kept.

    Returns:
        dict: The re-rendered visualization object (including layout_quality), plus `reset` listing the channels that
        actually had a configuration to clear.
    """
    with get_db_context() as db:
        from app.logic import visualization_builder
        cleared = visualization_builder.reset_style(db, network_id, targets)
        vis_data = visualization_builder.build_visualization(
            db, network_id, with_quality=True
        )
        vis_data["network_id"] = network_id
        vis_data["reset"] = cleared
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
        dict: The visualization object of the target network (nodes, links, legend, layout_quality).
    """
    with get_db_context() as db:
        from app.logic import visualization_builder
        vis_data = visualization_builder.build_visualization(
            db, network_id, with_quality=True
        )
        vis_data["network_id"] = network_id
        return vis_data
