from typing import Annotated, Dict, Optional, Tuple
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
_WEIGHT_DESC = (
    "Edge attribute to use as the numeric edge value (usually 'weight', the weight "
    "imported with the file)."
)
_SCALE_CENTER_DESC = (
    "Accepted for completeness but has NO visible effect: the renderer normalizes all "
    "coordinates to a fixed [-1000, 1000] extent before drawing. Do not use this to zoom "
    "or reposition the view."
)


@mcp.tool()
@handle_tool_errors
def layout_kamada_kawai(
    network_id: Annotated[int, Field(description="The ID of the network.")],
    weight: Annotated[Optional[str], Field(description=_WEIGHT_DESC + " Here a weight is treated as the target DISTANCE along an edge, so heavier edges place their endpoints further apart — the opposite of a connection-strength reading. Because of that this layout is the one layout that is NOT weighted by default: pass this only when the attribute really does mean distance or cost, not strength.")] = None,
    dist: Annotated[Optional[Dict[str, Dict[str, float]]], Field(description="Optional precomputed pairwise target distances as {source: {target: distance}}. Omit to use shortest-path distances, which is almost always what you want.")] = None,
    scale: Annotated[Optional[float], Field(description=_SCALE_CENTER_DESC)] = None,
    center: Annotated[Optional[Tuple[float, float]], Field(description=_SCALE_CENTER_DESC)] = None,
    init_from_layout: Annotated[Optional[str], Field(description="Name of a previously computed layout whose stored coordinates become the starting positions for the optimization. A good starting point (e.g. 'forceatlas2') both speeds up convergence and avoids poor local minima.")] = None,
    force_recompute: Annotated[bool, Field(description=_FORCE_RECOMPUTE_DESC)] = False,
) -> str:
    """
    Calculates a Kamada-Kawai layout — positions nodes to minimize graph-theoretic distance distortion.

    Produces aesthetically clean layouts that reflect global graph structure well.
    The node distances in the drawing approximate the actual shortest-path distances.
    Best for: small-to-medium graphs (< 500 nodes) where structural accuracy matters.

    WARNING: this builds a dense N x N distance matrix, so it is O(N^2) in both time and
    memory. On graphs above a few thousand nodes the call is refused; use
    `layout_forceatlas2` or `layout_spring` there instead.

    After calling this, use `visualization_generate` to render the result.

    Returns:
        str: Status message.
    """
    with get_db_context() as db:
        from app.logic import layout
        overrides = {
            "weight": weight,
            "dist": dist,
            "scale": scale,
            "center": center,
            "init_from_layout": init_from_layout,
        }
        info = layout.calculate_layout(
            network_id, "kamada_kawai", db, overrides=overrides, force=force_recompute
        )
        return layout.format_layout_result(
            info,
            "Kamada-Kawai layout calculated.",
            "Call `visualization_generate` to render.",
        )


@mcp.tool()
@handle_tool_errors
def layout_spectral(
    network_id: Annotated[int, Field(description="The ID of the network.")],
    weight: Annotated[Optional[str], Field(description=_WEIGHT_DESC + " The Laplacian is built from the weighted adjacency matrix. Leave unset: varying edge weights are used automatically. Pass 'none' to force an unweighted Laplacian, or another attribute name to use that one instead.")] = None,
    scale: Annotated[Optional[float], Field(description=_SCALE_CENTER_DESC)] = None,
    center: Annotated[Optional[Tuple[float, float]], Field(description=_SCALE_CENTER_DESC)] = None,
    force_recompute: Annotated[bool, Field(description=_FORCE_RECOMPUTE_DESC)] = False,
) -> str:
    """
    Calculates a spectral layout — uses the eigenvectors of the graph Laplacian matrix.

    Positions are derived from the graph's algebraic structure. Fast and fully
    deterministic (no random seed involved).
    Best for: graphs with clear separation between components or a clean algebraic
    structure. Requires a connected graph for best results.

    CAVEAT: on dense or highly connected graphs a spectral layout frequently collapses
    most nodes onto a line or a tight cluster, because the two leading eigenvectors carry
    little separating information. If the result looks degenerate, use
    `layout_forceatlas2` instead rather than tuning this.

    After calling this, use `visualization_generate` to render the result.

    Returns:
        str: Status message.
    """
    with get_db_context() as db:
        from app.logic import layout
        overrides = {"weight": weight, "scale": scale, "center": center}
        info = layout.calculate_layout(
            network_id, "spectral", db, overrides=overrides, force=force_recompute
        )
        return layout.format_layout_result(
            info,
            "Spectral layout calculated.",
            "Call `visualization_generate` to render.",
        )
