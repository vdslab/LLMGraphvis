"""Edge backbone extraction (ADR 0040)."""

from typing import Annotated, Literal, Optional

from pydantic import Field

from app.core.database import get_db_context
from app.core.decorators import handle_tool_errors
from app.core.mcp import mcp
from app.logic.backbone import extract_backbone


@mcp.tool()
@handle_tool_errors
def subgraph_edge_backbone(
    network_id: Annotated[int, Field(description="Source network ID.")],
    method: Annotated[
        Literal["top_k", "threshold"],
        Field(
            description="top_k keeps, for every node, its k strongest edges (an edge stays if either end chose it). threshold keeps edges whose imported weight is at least min_weight; it needs varying edge weights."
        ),
    ] = "top_k",
    k: Annotated[
        Optional[int],
        Field(
            ge=1,
            le=20,
            description="top_k only: strongest edges kept per node. Lower separates groups more and leaves more small parts; higher keeps more of the ties between groups.",
        ),
    ] = 3,
    min_weight: Annotated[
        Optional[float],
        Field(description="threshold only: the smallest edge weight kept."),
    ] = None,
    description: Annotated[
        Optional[str], Field(description="Purpose of this backbone network.")
    ] = None,
) -> dict:
    """Thin out a dense network: keep every node but only its strongest edges.

    The cure for a hairball, where every node links to many others and no
    layout setting separates the groups: with only each node's closest ties
    left, groups of mutually similar nodes come apart. Strength is the imported
    edge weight; a network without varying weights uses the number of shared
    neighbours instead (reported as `strength`).

    Creates a child network and returns created_network_id with the edges,
    connected parts and largest part it has. Does not select, lay out or
    render: call network_select, a layout tool, then visualization_generate.
    Metrics computed on it describe the thinned network.
    `subgraph_suggest_reduction` measures several k before you choose.
    """
    with get_db_context() as db:
        return extract_backbone(network_id, db, method, k, min_weight, description)
