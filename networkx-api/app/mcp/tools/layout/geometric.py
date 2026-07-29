from typing import Annotated, List, Optional, Tuple
from pydantic import Field
from app.core.mcp import mcp
from app.core.database import get_db_context
from app.core.decorators import handle_tool_errors
import logging

logger = logging.getLogger(__name__)


@mcp.tool()
@handle_tool_errors
def layout_circular(
    network_id: Annotated[int, Field(description="The ID of the network.")],
    scale: Annotated[Optional[float], Field(description="Scale factor for the layout radius. Defaults to networkx's own default (1.0) if not specified.")] = None,
    center: Annotated[Optional[Tuple[float, float]], Field(description="(x, y) coordinate to center the layout on. Defaults to the origin if not specified.")] = None,
    force_recompute: Annotated[bool, Field(description="If True, bypasses the cache and always recomputes, even if a valid cached result exists for this exact graph state and parameters. Default False preserves current auto-caching behavior.")] = False
) -> str:
    """
    Calculates a circular layout — all nodes equally spaced around a single circle.

    Best for: small graphs where you want to clearly see all connections,
    bipartite graphs, or ring-like structures. Avoids edge crossings at the cost
    of not reflecting graph topology.

    After calling this, use `visualization_apply_layout` to render the result.

    Note: the final rendered visualization normalizes all layout coordinates to a
    fixed [-1000, 1000] range, so `scale`/`center` overrides are only observable
    in the raw stored layout attribute values (via `network_list_node_attributes`
    or direct inspection), not in the final on-screen pixel positions.

    Returns:
        str: Status message.
    """
    with get_db_context() as db:
        from app.logic import layout
        overrides = {"scale": scale, "center": center}
        layout.calculate_layout(
            network_id, "circular", db, overrides=overrides, force=force_recompute
        )
        return "Circular layout calculated. Call `visualization_apply_layout` to render."


@mcp.tool()
@handle_tool_errors
def layout_shell(
    network_id: Annotated[int, Field(description="The ID of the network.")],
    scale: Annotated[Optional[float], Field(description="Scale factor for the layout radius. Defaults to networkx's own default (1.0) if not specified.")] = None,
    center: Annotated[Optional[Tuple[float, float]], Field(description="(x, y) coordinate to center the layout on. Defaults to the origin if not specified.")] = None,
    nlist: Annotated[Optional[List[List[str]]], Field(description="List of lists of node IDs, one inner list per concentric shell (innermost first). Node IDs must match the graph's node IDs. Defaults to a single automatic shell containing all nodes if not specified.")] = None,
    force_recompute: Annotated[bool, Field(description="If True, bypasses the cache and always recomputes, even if a valid cached result exists for this exact graph state and parameters. Default False preserves current auto-caching behavior.")] = False
) -> str:
    """
    Calculates a shell layout — nodes arranged in concentric circles (shells).

    Best for: hierarchical or layered graphs where group membership matters.
    Nodes are distributed across multiple concentric rings rather than a single circle.

    After calling this, use `visualization_apply_layout` to render the result.

    Note: the final rendered visualization normalizes all layout coordinates to a
    fixed [-1000, 1000] range, so `scale`/`center` overrides are only observable
    in the raw stored layout attribute values (via `network_list_node_attributes`
    or direct inspection), not in the final on-screen pixel positions.

    Returns:
        str: Status message.
    """
    with get_db_context() as db:
        from app.logic import layout
        overrides = {"scale": scale, "center": center, "nlist": nlist}
        layout.calculate_layout(
            network_id, "shell", db, overrides=overrides, force=force_recompute
        )
        return "Shell layout calculated. Call `visualization_apply_layout` to render."


@mcp.tool()
@handle_tool_errors
def layout_spiral(
    network_id: Annotated[int, Field(description="The ID of the network.")],
    scale: Annotated[Optional[float], Field(description="Scale factor for the layout radius. Defaults to networkx's own default (1.0) if not specified.")] = None,
    center: Annotated[Optional[Tuple[float, float]], Field(description="(x, y) coordinate to center the layout on. Defaults to the origin if not specified.")] = None,
    force_recompute: Annotated[bool, Field(description="If True, bypasses the cache and always recomputes, even if a valid cached result exists for this exact graph state and parameters. Default False preserves current auto-caching behavior.")] = False
) -> str:
    """
    Calculates a spiral layout — nodes arranged along an outward spiral.

    Best for: ordered sequences or timelines where you want to see all nodes
    without overlap in a compact, visually distinctive arrangement.

    After calling this, use `visualization_apply_layout` to render the result.

    Note: the final rendered visualization normalizes all layout coordinates to a
    fixed [-1000, 1000] range, so `scale`/`center` overrides are only observable
    in the raw stored layout attribute values (via `network_list_node_attributes`
    or direct inspection), not in the final on-screen pixel positions.

    Returns:
        str: Status message.
    """
    with get_db_context() as db:
        from app.logic import layout
        overrides = {"scale": scale, "center": center}
        layout.calculate_layout(
            network_id, "spiral", db, overrides=overrides, force=force_recompute
        )
        return "Spiral layout calculated. Call `visualization_apply_layout` to render."


@mcp.tool()
@handle_tool_errors
def layout_random(
    network_id: Annotated[int, Field(description="The ID of the network.")],
    center: Annotated[Optional[Tuple[float, float]], Field(description="(x, y) coordinate to center the layout on. Defaults to the origin if not specified. NOTE: unlike the other geometric layouts, networkx's random_layout has no `scale` parameter, so no `scale` override is offered here.")] = None,
    force_recompute: Annotated[bool, Field(description="If True, bypasses the cache and always recomputes, even if a valid cached result exists for this exact graph state and parameters. Default False preserves current auto-caching behavior.")] = False
) -> str:
    """
    Calculates a random layout — nodes placed at random positions (with fixed seed for reproducibility).

    Best for: quick sanity checks, or as a starting point before running a more
    expensive force-directed algorithm. Not useful for analytical purposes.

    After calling this, use `visualization_apply_layout` to render the result.

    Note: the final rendered visualization normalizes all layout coordinates to a
    fixed [-1000, 1000] range, so a `center` override is only observable in the
    raw stored layout attribute values (via `network_list_node_attributes` or
    direct inspection), not in the final on-screen pixel positions.

    Returns:
        str: Status message.
    """
    with get_db_context() as db:
        from app.logic import layout
        overrides = {"center": center}
        layout.calculate_layout(
            network_id, "random", db, overrides=overrides, force=force_recompute
        )
        return "Random layout calculated. Call `visualization_apply_layout` to render."
