"""Path tools compute results without changing attributes or the active view."""

import json
from typing import Annotated, Literal

from app.core.database import get_db_context
from app.core.decorators import handle_tool_errors
from app.core.mcp import mcp
from app.logic import paths
from pydantic import Field

NetworkId = Annotated[int, Field(description="ID of the network to query.")]
NodeId = Annotated[str, Field(description="Exact string node ID; use node_search for labels.")]
Cost = Annotated[str | None, Field(description="Numeric edge attribute interpreted as distance/cost, NOT connection strength. 'weight' uses the imported weight; another name uses that numeric attribute. Missing edge values default to 1. Omit or pass null/'none' for hop count.")]
Method = Annotated[Literal["dijkstra", "bellman-ford"], Field(description="Weighted-path algorithm. Dijkstra requires nonnegative costs. Bellman-Ford supports negative costs but rejects reachable negative cycles. With no weight, unweighted traversal is used.")]


@mcp.tool()
@handle_tool_errors
def analysis_shortest_path(
    network_id: NetworkId,
    source_node_id: NodeId,
    target_node_id: NodeId,
    weight: Cost = None,
    method: Method = "dijkstra",
) -> str:
    """Return one shortest path, total cost (length), and hops; respect edge direction.

    Read-only: does not extract a subgraph, change styles, or render. Multiple
    equally short paths may exist; this returns one. No path is a normal result.
    Negative cycles make weighted shortest paths undefined and return an error.
    """
    with get_db_context() as db:
        return json.dumps(paths.shortest_path(
            network_id, source_node_id, target_node_id, db, weight, method
        ))


@mcp.tool()
@handle_tool_errors
def analysis_single_source_distances(
    network_id: NetworkId,
    source_node_id: NodeId,
    weight: Cost = None,
    method: Method = "dijkstra",
    cutoff: Annotated[float | None, Field(ge=0, allow_inf_nan=False, description="Maximum returned distance/cost, inclusive. Omit for all reachable nodes. With negative costs filtering occurs after Bellman-Ford finishes.")] = None,
) -> dict:
    """Return distances from one node to reachable nodes, optionally within a cutoff.

    The source has distance zero. Omitted nodes are unreachable or outside the
    cutoff; never interpret omission as distance zero. Read-only; follows outgoing
    edges of directed graphs. No node attributes or visualization are changed.
    """
    with get_db_context() as db:
        return paths.single_source_distances(
            network_id, source_node_id, db, weight, method, cutoff
        )


@mcp.tool()
@handle_tool_errors
def analysis_has_path(
    network_id: NetworkId,
    source_node_id: NodeId,
    target_node_id: NodeId,
) -> dict:
    """Check reachability without computing costs or changing the graph/view.

    Respects edge direction. Weights are irrelevant; a node can reach itself.
    Unknown node IDs are errors rather than an unreachable result.
    """
    with get_db_context() as db:
        return paths.has_path(network_id, source_node_id, target_node_id, db)
