from typing import Annotated
from pydantic import Field
from app.core.mcp import mcp
from app.core.database import get_db_context
from app.core.decorators import handle_tool_errors
import logging

logger = logging.getLogger(__name__)


@mcp.tool()
@handle_tool_errors
def layout_kamada_kawai(
    network_id: Annotated[int, Field(description="The ID of the network.")]
) -> str:
    """
    Calculates a Kamada-Kawai layout — positions nodes to minimize graph-theoretic distance distortion.

    Produces aesthetically clean layouts that reflect global graph structure well.
    The node distances in the drawing approximate the actual shortest-path distances.
    Best for: small-to-medium graphs (< 500 nodes) where structural accuracy matters.
    WARNING: O(N²) complexity — slow on large graphs. Prefer ForceAtlas2 for > 500 nodes.

    After calling this, use `visualization_apply_layout` to render the result.

    Returns:
        str: Status message.
    """
    with get_db_context() as db:
        from app.logic import layout
        layout.calculate_layout(network_id, "kamada_kawai", db)
        return "Kamada-Kawai layout calculated. Call `visualization_apply_layout` to render."


@mcp.tool()
@handle_tool_errors
def layout_spectral(
    network_id: Annotated[int, Field(description="The ID of the network.")]
) -> str:
    """
    Calculates a spectral layout — uses the eigenvectors of the graph Laplacian matrix.

    Positions are derived from the graph's algebraic structure, often revealing
    community structure and clusters naturally.
    Best for: graphs with clear community structure, expander graphs, or when you want
    a mathematically principled layout. Requires a connected graph for best results.

    After calling this, use `visualization_apply_layout` to render the result.

    Returns:
        str: Status message.
    """
    with get_db_context() as db:
        from app.logic import layout
        layout.calculate_layout(network_id, "spectral", db)
        return "Spectral layout calculated. Call `visualization_apply_layout` to render."
