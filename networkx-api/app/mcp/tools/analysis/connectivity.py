"""Connectivity queries are independent from extraction and view switching."""

from typing import Annotated

from app.core.database import get_db_context
from app.core.decorators import handle_tool_errors
from app.core.mcp import mcp
from app.logic import connectivity
from pydantic import Field

NetworkId = Annotated[int, Field(description="ID of the network to analyze.")]
ComponentLimit = Annotated[int, Field(ge=1, le=100, description="How many components to list, largest first. `count` and `size_distribution` (component size -> how many components have it) always cover all of them.")]
NodeLimit = Annotated[int, Field(ge=1, le=500, description="How many node IDs to list per component; `omitted_nodes` says how many more it has. Raise only when the members themselves are needed.")]
ListLimit = Annotated[int, Field(ge=1, le=500, description="How many to list. `count` is always the total and `omitted` the number not listed.")]



@mcp.tool()
@handle_tool_errors
def analysis_connected_components(
    network_id: NetworkId, limit: ComponentLimit = 10, node_limit: NodeLimit = 50
) -> dict:
    """List the connected components of an undirected graph, largest first.

    Each listed component has its `size` and member `node_ids`. Isolates are
    one-node components; an empty graph has no components.
    Read-only: no subgraphs, attributes, or visualization changes are made.
    Use weakly/strongly connected components for a directed network.
    """
    with get_db_context() as db:
        return connectivity.components(network_id, db, "connected_components", limit, node_limit)


@mcp.tool()
@handle_tool_errors
def analysis_weakly_connected_components(
    network_id: NetworkId, limit: ComponentLimit = 10, node_limit: NodeLimit = 50
) -> dict:
    """List directed graph components connected when edge direction is ignored.

    Use for groups joined by any chain of edges. This does NOT imply mutual
    directed reachability. Returns largest groups first without extracting or
    changing the active network. Requires a directed graph.
    """
    with get_db_context() as db:
        return connectivity.components(network_id, db, "weakly_connected_components", limit, node_limit)


@mcp.tool()
@handle_tool_errors
def analysis_strongly_connected_components(
    network_id: NetworkId, limit: ComponentLimit = 10, node_limit: NodeLimit = 50
) -> dict:
    """List groups in which every node can reach every other along directed edges.

    Requires a directed graph. Isolates are one-node groups. Lists the
    largest groups first. Read-only: does not extract subgraphs or change the view.
    """
    with get_db_context() as db:
        return connectivity.components(network_id, db, "strongly_connected_components", limit, node_limit)



@mcp.tool()
@handle_tool_errors
def analysis_bridges(network_id: NetworkId, limit: ListLimit = 50) -> dict:
    """Find undirected edges whose removal increases the number of components.

    Each bridge is returned as a pair of node IDs. Works on disconnected graphs;
    self-loops are never bridges. No edge is removed or styled. For actual edge
    removal or visual highlighting, a separate explicit operation is required.
    """
    with get_db_context() as db:
        return connectivity.bridges(network_id, db, limit)


@mcp.tool()
@handle_tool_errors
def analysis_articulation_points(network_id: NetworkId, limit: ListLimit = 50) -> dict:
    """Find undirected nodes whose removal increases the number of components.

    Useful for structural bottlenecks. Lists the points whose removal splits off
    the most pieces first (`pieces_added`). Returns node IDs without removing nodes,
    extracting a subgraph, or changing visualization. Supports disconnected graphs.
    This measures a different property from betweenness centrality.
    """
    with get_db_context() as db:
        return connectivity.articulation_points(network_id, db, limit)


@mcp.tool()
@handle_tool_errors
def analysis_transitivity(network_id: NetworkId) -> dict:
    """Return global unweighted triangle closure for an undirected graph.

    Three times the triangle count divided by the number of connected triples.
    This differs from the average local clustering coefficient. Returns zero if
    no connected triples exist. Self-loops are ignored. Read-only; saves nothing.
    """
    with get_db_context() as db:
        return connectivity.transitivity(network_id, db)
