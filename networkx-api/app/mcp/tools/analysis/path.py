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
    limit: Annotated[int, Field(ge=1, le=500, description="How many of the nearest reachable nodes to list in `distances`. `reachable_count` and `summary` (whose `distribution` maps hop count -> node count for unweighted queries) always cover every reachable node.")] = 30,
    target_node_ids: Annotated[list[str] | None, Field(description="Exact node IDs whose distance you need. When given, `distances` lists exactly these (null = unreachable or beyond cutoff) and `limit` is ignored.")] = None,
) -> dict:
    """Return distances from one node to reachable nodes, optionally within a cutoff.

    The source has distance zero. `distances` lists the nearest `limit` nodes,
    or exactly `target_node_ids`; nodes not listed are not thereby unreachable,
    so read `reachable_count` for how many are. Never interpret an unlisted
    node as distance zero. Read-only; follows outgoing edges of directed
    graphs. No node attributes or visualization are changed.
    """
    with get_db_context() as db:
        return paths.single_source_distances(
            network_id, source_node_id, db, weight, method, cutoff,
            limit=limit, targets=target_node_ids,
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


@mcp.tool()
@handle_tool_errors
def analysis_k_shortest_paths(
    network_id: NetworkId,
    source_node_id: NodeId,
    target_node_id: NodeId,
    k: Annotated[int, Field(ge=1, le=10, description="How many alternative routes to return, shortest first.")] = 3,
    weight: Cost = None,
) -> dict:
    """Return up to k loopless routes between two nodes, shortest first.

    Use when the user asks for several routes, alternatives, or "other ways"
    from A to B; for the single best route use analysis_shortest_path. Each
    route has its node sequence, hops and total cost (length). Respects edge
    direction; costs must be nonnegative. Read-only: to show a route, pass its
    `path` to visualization_highlight(edges='path').
    """
    from app.logic import exploration

    with get_db_context() as db:
        return exploration.k_shortest_paths(
            network_id, db, source_node_id, target_node_id, k, weight
        )
