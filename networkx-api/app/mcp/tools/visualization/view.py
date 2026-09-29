"""View tools: what stands out and where the camera points (ADR 0023).

Neither changes the graph, the active network, or any attribute encoding.
"""

from typing import Annotated, List, Literal, Optional

from pydantic import Field

from app.core.database import get_db_context
from app.core.decorators import handle_tool_errors
from app.core.mcp import mcp
from app.logic import view_state


@mcp.tool()
@handle_tool_errors
def visualization_highlight(
    network_id: Annotated[int, Field(description="The ID of the network.")],
    node_ids: Annotated[List[str], Field(description="Exact node IDs to bring forward (resolve names with node_search). With edges='path', list them in route order, e.g. the `path` from analysis_shortest_path.")],
    edges: Annotated[Literal["induced", "path", "incident", "none"], Field(description="Which edges stay prominent. 'induced': edges between highlighted nodes. 'path': only edges between consecutive node_ids (a route). 'incident': every edge touching a highlighted node (shows its connections). 'none': nodes only.")] = "induced",
    neighbor_hops: Annotated[int, Field(ge=0, le=3, description="Also highlight nodes within this many hops of node_ids, ignoring edge direction. 1 highlights each node's immediate neighbours.")] = 0,
    dim_opacity: Annotated[float, Field(ge=0, le=1, description="Opacity of everything not highlighted: 0 hides it, 1 does not dim at all.")] = view_state.DEFAULT_DIM_OPACITY,
    color: Annotated[Optional[str], Field(description="Hex color for highlighted nodes and edges, e.g. '#e15759'. None keeps their current color encoding, which is usually better when a color channel is already set.")] = None,
    zoom_to: Annotated[bool, Field(description="Also move the view to frame the highlighted nodes, as visualization_set_viewport would.")] = False,
) -> dict:
    """
    Emphasizes a set of nodes (a focus, a neighbourhood, or a route) and dims everything else.

    Use this to focus on nodes or show a path WITHOUT extracting a subgraph: the
    whole network stays on screen and every analysis still runs on it. Extract
    (`subgraph_*`) only when the user wants later analysis restricted to the
    subset.

    The highlight is a saved channel like color or size: it persists through
    later `visualization_set_*` calls and re-renders, and a new call replaces it.
    Remove it with `visualization_reset_style(targets=['highlight'])`.

    Returns:
        dict: The re-rendered visualization; `legend.highlight` reports how many
        nodes and edges are highlighted.
    """
    with get_db_context() as db:
        from app.logic import visualization_builder

        config = view_state.resolve_highlight(
            network_id, db, node_ids, edges, neighbor_hops, dim_opacity, color
        )
        vis_data = visualization_builder.build_visualization(
            db, network_id, highlight_config=config, with_quality=True
        )
        vis_data["network_id"] = network_id
        if zoom_to:
            vis_data["viewport"] = view_state.viewport_directive(
                "nodes", config["node_ids"]
            )
        return vis_data


@mcp.tool()
@handle_tool_errors
def visualization_set_viewport(
    network_id: Annotated[int, Field(description="The ID of the network.")],
    target: Annotated[Literal["all", "nodes", "highlighted"], Field(description="'all' fits the whole network (reset zoom). 'nodes' frames node_ids. 'highlighted' frames the current highlight.")] = "all",
    node_ids: Annotated[Optional[List[str]], Field(description="For target='nodes': exact node IDs to frame. One node zooms in on it and its surroundings.")] = None,
    padding: Annotated[float, Field(ge=0, le=2, description="Margin around the framed nodes as a fraction of their extent; larger shows more context.")] = view_state.DEFAULT_VIEWPORT_PADDING,
) -> dict:
    """
    Moves the user's view (zoom and pan) to frame some nodes, or back to the whole network.

    This is the tool for "zoom in on X", "show me that area", or "zoom out". It
    changes nothing else: no data, style, or layout. The move applies once;
    the user can pan and zoom freely afterwards, and later renders keep their
    view. Layout `scale`/`center` parameters are not a zoom and have no visible
    effect.

    Returns:
        dict: The visualization with a `viewport` instruction for the canvas.
    """
    with get_db_context() as db:
        from app.logic import visualization_builder
        from common import models

        if target == "nodes":
            if not node_ids:
                raise ValueError("target='nodes' needs node_ids")
            known = {
                row[0]
                for row in db.query(models.Node.node_id)
                .filter(models.Node.network_id == network_id)
                .all()
            }
            missing = [n for n in node_ids if n not in known]
            if missing:
                raise ValueError(
                    f"Unknown node ID(s): {', '.join(missing[:10])}. "
                    "Use node_search to resolve labels to exact IDs."
                )
            directive = view_state.viewport_directive("nodes", node_ids, padding)
        elif target == "highlighted":
            network = db.query(models.Network).get(network_id)
            highlighted = ((network and network.last_highlight_config) or {}).get(
                "node_ids"
            )
            if not highlighted:
                raise ValueError(
                    "Nothing is highlighted; call visualization_highlight first "
                    "or use target='nodes'."
                )
            directive = view_state.viewport_directive("nodes", highlighted, padding)
        else:
            directive = view_state.viewport_directive("fit", [], padding)

        vis_data = visualization_builder.build_visualization(
            db, network_id, with_quality=True
        )
        vis_data["network_id"] = network_id
        vis_data["viewport"] = directive
        return vis_data
