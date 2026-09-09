"""Independent structure measurements without extraction or visual side effects."""

from typing import Annotated, Optional

from app.core.database import get_db_context
from app.core.decorators import handle_tool_errors
from app.core.mcp import mcp
from app.logic import structure_metrics
from pydantic import Field

NetworkId = Annotated[int, Field(description="Network to measure.")]


@mcp.tool()
@handle_tool_errors
def analysis_core_number(network_id: NetworkId) -> dict:
    """Return each node's highest k-core membership, without extracting a core.

    Directed graphs use in-degree plus out-degree. Self-loops are rejected.
    Isolated nodes have core number zero. Read-only: no saved attributes or view
    changes. This measures cohesive structure, not shortest-path importance.
    """
    with get_db_context() as db:
        return structure_metrics.core_numbers(network_id, db)


@mcp.tool()
@handle_tool_errors
def analysis_triangles(
    network_id: NetworkId,
    nodes: Annotated[Optional[list[str]], Field(description="Exact node IDs to measure; omit/null for all nodes. A subset measures triangles in the full graph, not its induced subgraph.")] = None,
) -> dict:
    """Count triangles incident to nodes in an undirected graph; ignore self-loops.

    Unweighted. When measuring all nodes, also returns the unique graph-wide
    triangle count. Partial-node sums are not a graph-wide count. Read-only.
    """
    with get_db_context() as db:
        return structure_metrics.triangle_counts(network_id, db, nodes)


@mcp.tool()
@handle_tool_errors
def analysis_edge_betweenness(
    network_id: NetworkId,
    k: Annotated[Optional[int], Field(ge=1, description="Sample this many source nodes for approximation; omit/null for exact calculation. Must not exceed node count.")] = None,
    normalized: Annotated[bool, Field(description="Normalize by the number of possible node pairs, accounting for direction.")] = True,
    weight: Annotated[Optional[str], Field(description="Edge distance/cost attribute. All costs must be positive and finite. Omit/null/'none' for unweighted; strength is not automatically treated as cost.")] = None,
    seed: Annotated[Optional[int], Field(description="Seed for sampling when k is set. Default 42; null uses fresh randomness.")] = 42,
) -> dict:
    """Measure shortest-path traffic through each edge, without changing the graph.

    Supports directed graphs. Exact computation can be expensive; use k for
    approximation and report that choice. Returns source/target/value records;
    does not remove edges, save attributes, style, switch, or render.
    """
    with get_db_context() as db:
        return structure_metrics.edge_betweenness(network_id, db, k, normalized, weight, seed)


@mcp.tool()
@handle_tool_errors
def analysis_modularity(
    network_id: NetworkId,
    attribute: Annotated[str, Field(description="Existing node attribute defining one community per node. Use the exact attribute returned by community detection. Every node needs a value.")],
    weight: Annotated[Optional[str], Field(description="Nonnegative finite edge strength attribute. Omit/null/'none' for unweighted.")] = None,
    resolution: Annotated[float, Field(gt=0, allow_inf_nan=False, description="Null-model resolution. Compare partitions using the same graph, weight and resolution.")] = 1.0,
) -> dict:
    """Evaluate an existing partition's modularity without detecting new communities.

    Supports directed graphs. Zero total edge strength is undefined and rejected.
    A larger score does not prove a scientifically correct grouping; comparison
    requires consistent graph and settings. Read-only: saves and renders nothing.
    """
    with get_db_context() as db:
        return structure_metrics.partition_modularity(network_id, db, attribute, weight, resolution)
