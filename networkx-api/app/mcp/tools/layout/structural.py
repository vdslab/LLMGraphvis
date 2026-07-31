"""Layouts whose arrangement is driven by graph structure or an attribute
partition, rather than by force simulation or pure geometry.
"""

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
_SCALE_CENTER_DESC = (
    "Accepted for completeness but has NO visible effect: the renderer normalizes all "
    "coordinates to a fixed [-1000, 1000] extent before drawing."
)
_ALIGN_DESC = (
    "Orientation of the layers: 'vertical' (default) stacks them left-to-right as vertical "
    "columns; 'horizontal' stacks them top-to-bottom as horizontal rows."
)


@mcp.tool()
@handle_tool_errors
def layout_bipartite(
    network_id: Annotated[int, Field(description="The ID of the network.")],
    partition_attribute: Annotated[Optional[str], Field(description="Node attribute that splits the graph into two sides (e.g. 'type', 'role', 'is_author'). Required unless `nodes` is given. If the attribute has exactly two distinct values, either may be treated as the first side; otherwise also pass `partition_value`.")] = None,
    partition_value: Annotated[Optional[str], Field(description="Which value of `partition_attribute` forms the first (left/top) side. Nodes with any other value form the second side. Required when the attribute has more than two distinct values.")] = None,
    nodes: Annotated[Optional[List[str]], Field(description="Explicit list of node IDs forming one side, as an alternative to `partition_attribute`. Use this only when the split is not recorded as an attribute.")] = None,
    align: Annotated[Optional[str], Field(description=_ALIGN_DESC)] = None,
    aspect_ratio: Annotated[Optional[float], Field(description="Ratio of the layout's width to its height. Defaults to 4/3. Raise it to spread the two sides further apart.")] = None,
    scale: Annotated[Optional[float], Field(description=_SCALE_CENTER_DESC)] = None,
    center: Annotated[Optional[Tuple[float, float]], Field(description=_SCALE_CENTER_DESC)] = None,
    force_recompute: Annotated[bool, Field(description=_FORCE_RECOMPUTE_DESC)] = False,
) -> str:
    """
    Calculates a bipartite layout — two facing columns (or rows) of nodes.

    Use this when the graph divides into two kinds of node and the division is the
    point: authors and papers, users and items, people and organizations. Edges run
    between the two sides, so cross-side structure becomes easy to read.

    This does NOT verify that the graph is actually bipartite; it arranges the two
    groups you name. Edges inside a group are still drawn, they just run along a side.

    After calling this, use `visualization_generate` to render the result.

    Returns:
        str: Status message.
    """
    with get_db_context() as db:
        from app.logic import layout
        overrides = {
            "partition_attribute": partition_attribute,
            "partition_value": partition_value,
            "nodes": nodes,
            "align": align,
            "aspect_ratio": aspect_ratio,
            "scale": scale,
            "center": center,
        }
        layout.calculate_layout(
            network_id, "bipartite", db, overrides=overrides, force=force_recompute
        )
        return "Bipartite layout calculated. Call `visualization_generate` to render."


@mcp.tool()
@handle_tool_errors
def layout_multipartite(
    network_id: Annotated[int, Field(description="The ID of the network.")],
    subset_attribute: Annotated[str, Field(description="Node attribute whose distinct values define the layers, one column (or row) per value — e.g. 'level', 'generation', 'year', or a community attribute such as 'louvain_community'. EVERY node must have a value for this attribute; nodes without one cannot be placed in a layer.")],
    align: Annotated[Optional[str], Field(description=_ALIGN_DESC)] = None,
    scale: Annotated[Optional[float], Field(description=_SCALE_CENTER_DESC)] = None,
    center: Annotated[Optional[Tuple[float, float]], Field(description=_SCALE_CENTER_DESC)] = None,
    force_recompute: Annotated[bool, Field(description=_FORCE_RECOMPUTE_DESC)] = False,
) -> str:
    """
    Calculates a multipartite layout — one column (or row) of nodes per attribute value.

    Use this when nodes fall into ordered or categorical layers and you want to see how
    edges flow between them: a citation graph by year, an org chart by level, or detected
    communities placed side by side.

    Pairs well with `analysis_detect_communities`: run it first, then pass the community
    attribute it saved (e.g. 'louvain_community') as `subset_attribute` to see each
    community as its own column and the edges that bridge them.

    After calling this, use `visualization_generate` to render the result.

    Returns:
        str: Status message.
    """
    with get_db_context() as db:
        from app.logic import layout
        overrides = {
            "subset_attribute": subset_attribute,
            "align": align,
            "scale": scale,
            "center": center,
        }
        layout.calculate_layout(
            network_id, "multipartite", db, overrides=overrides, force=force_recompute
        )
        return "Multipartite layout calculated. Call `visualization_generate` to render."


@mcp.tool()
@handle_tool_errors
def layout_planar(
    network_id: Annotated[int, Field(description="The ID of the network.")],
    scale: Annotated[Optional[float], Field(description=_SCALE_CENTER_DESC)] = None,
    center: Annotated[Optional[Tuple[float, float]], Field(description=_SCALE_CENTER_DESC)] = None,
    force_recompute: Annotated[bool, Field(description=_FORCE_RECOMPUTE_DESC)] = False,
) -> str:
    """
    Calculates a planar layout — a drawing with no edge crossings at all.

    Only works on planar graphs. Most real-world networks are NOT planar, and this call
    fails with a clear message when the graph is not; in that case use
    `layout_forceatlas2` or `layout_spring` instead. Worth trying for trees, grids,
    road-like networks, and other sparse structures where a crossing-free drawing is
    dramatically more readable.

    After calling this, use `visualization_generate` to render the result.

    Returns:
        str: Status message.
    """
    with get_db_context() as db:
        from app.logic import layout
        overrides = {"scale": scale, "center": center}
        layout.calculate_layout(
            network_id, "planar", db, overrides=overrides, force=force_recompute
        )
        return "Planar layout calculated. Call `visualization_generate` to render."


@mcp.tool()
@handle_tool_errors
def layout_bfs(
    network_id: Annotated[int, Field(description="The ID of the network.")],
    start: Annotated[str, Field(description="Node ID to use as the root. Nodes are placed in layers by their BFS distance from it. Use `node_search` first if you have a label rather than an ID.")],
    align: Annotated[Optional[str], Field(description=_ALIGN_DESC + " Layers here are BFS distances from the root.")] = None,
    scale: Annotated[Optional[float], Field(description=_SCALE_CENTER_DESC)] = None,
    center: Annotated[Optional[Tuple[float, float]], Field(description=_SCALE_CENTER_DESC)] = None,
    force_recompute: Annotated[bool, Field(description=_FORCE_RECOMPUTE_DESC)] = False,
) -> str:
    """
    Calculates a BFS layout — nodes arranged in layers by hop distance from one root node.

    Use this to answer "how far is everything from X?": each layer is one more hop away
    from `start`. Ideal for trees, hierarchies, and dependency or spread analysis.

    Only nodes reachable from `start` are laid out, so on a disconnected graph the other
    components will not be positioned meaningfully. Extract the relevant component first
    (`subgraph_largest_component`) or use an ego network if that matters.

    After calling this, use `visualization_generate` to render the result.

    Returns:
        str: Status message.
    """
    with get_db_context() as db:
        from app.logic import layout
        overrides = {
            "start": start,
            "align": align,
            "scale": scale,
            "center": center,
        }
        layout.calculate_layout(
            network_id, "bfs", db, overrides=overrides, force=force_recompute
        )
        return "BFS layout calculated. Call `visualization_generate` to render."
