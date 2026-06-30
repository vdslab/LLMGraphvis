from typing import Annotated
from pydantic import Field
from app.core.mcp import mcp
from app.core.database import get_db_context
from app.core.decorators import handle_tool_errors
import logging

logger = logging.getLogger(__name__)


@mcp.tool()
@handle_tool_errors
def layout_circular(
    network_id: Annotated[int, Field(description="The ID of the network.")]
) -> str:
    """
    Calculates a circular layout — all nodes equally spaced around a single circle.

    Best for: small graphs where you want to clearly see all connections,
    bipartite graphs, or ring-like structures. Avoids edge crossings at the cost
    of not reflecting graph topology.

    After calling this, use `visualization_apply_layout` to render the result.

    Returns:
        str: Status message.
    """
    with get_db_context() as db:
        from app.logic import layout
        layout.calculate_layout(network_id, "circular", db)
        return "Circular layout calculated. Call `visualization_apply_layout` to render."


@mcp.tool()
@handle_tool_errors
def layout_shell(
    network_id: Annotated[int, Field(description="The ID of the network.")]
) -> str:
    """
    Calculates a shell layout — nodes arranged in concentric circles (shells).

    Best for: hierarchical or layered graphs where group membership matters.
    Nodes are distributed across multiple concentric rings rather than a single circle.

    After calling this, use `visualization_apply_layout` to render the result.

    Returns:
        str: Status message.
    """
    with get_db_context() as db:
        from app.logic import layout
        layout.calculate_layout(network_id, "shell", db)
        return "Shell layout calculated. Call `visualization_apply_layout` to render."


@mcp.tool()
@handle_tool_errors
def layout_spiral(
    network_id: Annotated[int, Field(description="The ID of the network.")]
) -> str:
    """
    Calculates a spiral layout — nodes arranged along an outward spiral.

    Best for: ordered sequences or timelines where you want to see all nodes
    without overlap in a compact, visually distinctive arrangement.

    After calling this, use `visualization_apply_layout` to render the result.

    Returns:
        str: Status message.
    """
    with get_db_context() as db:
        from app.logic import layout
        layout.calculate_layout(network_id, "spiral", db)
        return "Spiral layout calculated. Call `visualization_apply_layout` to render."


@mcp.tool()
@handle_tool_errors
def layout_random(
    network_id: Annotated[int, Field(description="The ID of the network.")]
) -> str:
    """
    Calculates a random layout — nodes placed at random positions (with fixed seed for reproducibility).

    Best for: quick sanity checks, or as a starting point before running a more
    expensive force-directed algorithm. Not useful for analytical purposes.

    After calling this, use `visualization_apply_layout` to render the result.

    Returns:
        str: Status message.
    """
    with get_db_context() as db:
        from app.logic import layout
        layout.calculate_layout(network_id, "random", db)
        return "Random layout calculated. Call `visualization_apply_layout` to render."
