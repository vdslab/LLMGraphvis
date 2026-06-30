from typing import Annotated, Optional
from pydantic import Field
from app.core.mcp import mcp
from app.core.database import get_db_context
from app.core.decorators import handle_tool_errors
import logging

logger = logging.getLogger(__name__)


@mcp.tool()
@handle_tool_errors
def layout_forceatlas2(
    network_id: Annotated[int, Field(description="The ID of the network.")],
    max_iter: Annotated[Optional[int], Field(description="Maximum iterations. Defaults to auto (1000–5000 based on graph size).")] = None,
    gravity: Annotated[float, Field(description="Gravity constant pulling nodes toward center. Default 1.0.")] = 1.0,
    scaling_ratio: Annotated[Optional[float], Field(description="Scaling ratio for node repulsion. Defaults to auto based on avg degree.")] = None
) -> str:
    """
    Calculates a ForceAtlas2 force-directed layout and saves x, y coordinates as node attributes.

    ForceAtlas2 is the **recommended default** for most networks. It produces organic,
    readable layouts by simulating repulsion between nodes and attraction along edges.
    Best for: general-purpose graphs, social networks, medium-to-large networks.

    After calling this, use `visualization_apply_layout` to render the result.

    Returns:
        str: Status message.
    """
    with get_db_context() as db:
        from app.logic import layout
        layout.calculate_layout(network_id, "forceatlas2", db)
        return "ForceAtlas2 layout calculated. Call `visualization_apply_layout` to render."


@mcp.tool()
@handle_tool_errors
def layout_spring(
    network_id: Annotated[int, Field(description="The ID of the network.")],
    iterations: Annotated[Optional[int], Field(description="Number of iterations. Defaults to auto (200–1000 based on graph size).")] = None,
    k: Annotated[Optional[float], Field(description="Optimal distance between nodes. Defaults to auto.")] = None
) -> str:
    """
    Calculates a Spring (Fruchterman-Reingold) force-directed layout and saves x, y coordinates.

    Similar to ForceAtlas2 but uses the classic Fruchterman-Reingold algorithm.
    Best for: small-to-medium graphs (< 500 nodes) where high-quality convergence is needed.
    Slower than ForceAtlas2 on large graphs.

    After calling this, use `visualization_apply_layout` to render the result.

    Returns:
        str: Status message.
    """
    with get_db_context() as db:
        from app.logic import layout
        layout.calculate_layout(network_id, "spring", db)
        return "Spring layout calculated. Call `visualization_apply_layout` to render."
