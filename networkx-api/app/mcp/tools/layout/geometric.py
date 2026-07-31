from typing import Annotated, List, Optional, Tuple
from pydantic import Field
from app.core.mcp import mcp
from app.core.database import get_db_context
from app.core.decorators import handle_tool_errors
import logging

logger = logging.getLogger(__name__)

_FORCE_RECOMPUTE_DESC = (
    "If True, bypasses the cache and always recomputes. The cache key already includes "
    "every parameter below, so changing a parameter recomputes on its own — set this only "
    "when the user explicitly wants the same computation redone."
)

# All four geometric layouts share this: the renderer normalizes coordinates, so
# scale/center are inert. Saying so in the schema stops the model from offering
# them as a way to zoom, and from claiming they worked.
_SCALE_DESC = (
    "Radius scale factor. NOTE: has no visible effect — the renderer normalizes all "
    "coordinates to a fixed [-1000, 1000] extent before drawing, so this is only "
    "observable in the raw stored layout attribute values. Do not use it to zoom."
)
_CENTER_DESC = (
    "(x, y) coordinate to center the layout on. NOTE: has no visible effect — the "
    "renderer normalizes all coordinates before drawing. Do not use it to reposition "
    "the view."
)


@mcp.tool()
@handle_tool_errors
def layout_circular(
    network_id: Annotated[int, Field(description="The ID of the network.")],
    scale: Annotated[Optional[float], Field(description=_SCALE_DESC)] = None,
    center: Annotated[Optional[Tuple[float, float]], Field(description=_CENTER_DESC)] = None,
    force_recompute: Annotated[bool, Field(description=_FORCE_RECOMPUTE_DESC)] = False,
) -> str:
    """
    Calculates a circular layout — all nodes equally spaced around a single circle.

    Best for: small graphs where you want to clearly see all connections,
    bipartite graphs, or ring-like structures. Guarantees no node overlap, at the cost
    of not reflecting graph topology at all.

    After calling this, use `visualization_generate` to render the result.

    Returns:
        str: Status message.
    """
    with get_db_context() as db:
        from app.logic import layout
        overrides = {"scale": scale, "center": center}
        layout.calculate_layout(
            network_id, "circular", db, overrides=overrides, force=force_recompute
        )
        return "Circular layout calculated. Call `visualization_generate` to render."


@mcp.tool()
@handle_tool_errors
def layout_shell(
    network_id: Annotated[int, Field(description="The ID of the network.")],
    nlist: Annotated[Optional[List[List[str]]], Field(description="List of lists of node IDs, one inner list per concentric shell (innermost first). Node IDs must match the graph's node IDs. This is the parameter that makes the layout meaningful: use it to place a grouping (e.g. one shell per community, or core nodes inside and periphery outside). Defaults to a single shell containing all nodes, which is identical to a circular layout.")] = None,
    rotate: Annotated[Optional[float], Field(description="Angle in radians by which each successive shell is rotated relative to the previous one. Reduces radial alignment of nodes across shells, which can make edges easier to follow.")] = None,
    scale: Annotated[Optional[float], Field(description=_SCALE_DESC)] = None,
    center: Annotated[Optional[Tuple[float, float]], Field(description=_CENTER_DESC)] = None,
    force_recompute: Annotated[bool, Field(description=_FORCE_RECOMPUTE_DESC)] = False,
) -> str:
    """
    Calculates a shell layout — nodes arranged in concentric circles (shells).

    Best for: hierarchical or layered graphs where group membership matters.
    Without `nlist` this produces exactly a circular layout, so supply `nlist` when the
    grouping is the point.

    After calling this, use `visualization_generate` to render the result.

    Returns:
        str: Status message.
    """
    with get_db_context() as db:
        from app.logic import layout
        overrides = {
            "nlist": nlist,
            "rotate": rotate,
            "scale": scale,
            "center": center,
        }
        layout.calculate_layout(
            network_id, "shell", db, overrides=overrides, force=force_recompute
        )
        return "Shell layout calculated. Call `visualization_generate` to render."


@mcp.tool()
@handle_tool_errors
def layout_spiral(
    network_id: Annotated[int, Field(description="The ID of the network.")],
    resolution: Annotated[Optional[float], Field(description="Compactness of the spiral: the angle between successive nodes. Lower values wind the spiral more tightly (more turns); higher values make it looser.")] = None,
    equidistant: Annotated[Optional[bool], Field(description="If True, nodes are spaced at equal arc distance along the spiral instead of at equal angles, which keeps outer nodes from spreading further apart than inner ones.")] = None,
    scale: Annotated[Optional[float], Field(description=_SCALE_DESC)] = None,
    center: Annotated[Optional[Tuple[float, float]], Field(description=_CENTER_DESC)] = None,
    force_recompute: Annotated[bool, Field(description=_FORCE_RECOMPUTE_DESC)] = False,
) -> str:
    """
    Calculates a spiral layout — nodes arranged along an outward spiral.

    Best for: ordered sequences or timelines where you want to see all nodes
    without overlap in a compact, visually distinctive arrangement. Node order follows
    the graph's node insertion order.

    After calling this, use `visualization_generate` to render the result.

    Returns:
        str: Status message.
    """
    with get_db_context() as db:
        from app.logic import layout
        overrides = {
            "resolution": resolution,
            "equidistant": equidistant,
            "scale": scale,
            "center": center,
        }
        layout.calculate_layout(
            network_id, "spiral", db, overrides=overrides, force=force_recompute
        )
        return "Spiral layout calculated. Call `visualization_generate` to render."


@mcp.tool()
@handle_tool_errors
def layout_random(
    network_id: Annotated[int, Field(description="The ID of the network.")],
    seed: Annotated[Optional[int], Field(description="Random seed. Defaults to 42, so the result is reproducible; pass a different value for a different arrangement.")] = None,
    center: Annotated[Optional[Tuple[float, float]], Field(description=_CENTER_DESC + " NOTE: unlike the other geometric layouts, networkx's random_layout has no `scale` parameter, so none is offered here.")] = None,
    force_recompute: Annotated[bool, Field(description=_FORCE_RECOMPUTE_DESC)] = False,
) -> str:
    """
    Calculates a random layout — nodes placed at uniformly random positions.

    Best for: a baseline to compare against, or as an explicit starting point for a
    force-directed layout via its `init_from_layout` parameter. Not useful for
    analysis on its own.

    After calling this, use `visualization_generate` to render the result.

    Returns:
        str: Status message.
    """
    with get_db_context() as db:
        from app.logic import layout
        overrides = {"seed": seed, "center": center}
        layout.calculate_layout(
            network_id, "random", db, overrides=overrides, force=force_recompute
        )
        return "Random layout calculated. Call `visualization_generate` to render."
