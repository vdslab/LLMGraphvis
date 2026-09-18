"""Tools that decide layouts rather than compute one: which algorithm fits this
graph, and which parameters would make the current drawing more readable.

Neither saves nor draws anything (ADR 0017). The quality of the drawing itself
arrives with every `visualization_generate` as `layout_quality`.
"""

from typing import Annotated, Optional

from pydantic import Field

from app.core.database import get_db_context
from app.core.decorators import handle_tool_errors
from app.core.mcp import mcp


@mcp.tool()
@handle_tool_errors
def layout_profile(
    network_id: Annotated[int, Field(description="The ID of the network.")],
) -> dict:
    """
    Describes the network's structure as it matters to a layout, and which layout
    algorithms suit it.

    Returns the profile (node/edge counts, density, degree spread, connected
    components, isolated nodes, weight range, and whether the graph is a forest,
    planar or bipartite), `recommended` layouts in order with the reason each fits,
    and `unsuitable` layouts with the reason each would fail or mislead.

    Use it before choosing a layout algorithm when the user has not named one, or to
    explain why a layout looks the way it does. It computes no coordinates.
    """
    with get_db_context() as db:
        from app.logic.layouts.profile import (
            profile_graph,
            recommend_layouts,
            unsuitable_layouts,
        )
        from app.logic.utils.graph_builder import (
            WEIGHT_COLUMN,
            build_graph_from_db,
            summarize_edge_weights,
        )

        weighted = summarize_edge_weights(network_id, db)["is_informative"]
        weight = WEIGHT_COLUMN if weighted else None
        G = build_graph_from_db(network_id, db, weight_attribute=weight)
        profile = profile_graph(G, weight)
        return {
            "network_id": network_id,
            "profile": profile.as_dict(),
            "recommended": recommend_layouts(profile),
            "unsuitable": unsuitable_layouts(profile),
        }


@mcp.tool()
@handle_tool_errors
def layout_suggest_parameters(
    network_id: Annotated[int, Field(description="The ID of the network.")],
    layout: Annotated[Optional[str], Field(description="Layout to tune, e.g. 'forceatlas2' or 'spring'. Omit to tune the layout currently drawn.")] = None,
    max_candidates: Annotated[int, Field(ge=1, le=5, description="How many candidates to return, best first.")] = 3,
) -> dict:
    """
    Searches for layout parameters that make the drawing more readable, by running the
    layout with several parameter sets and scoring each one as it would be drawn.

    It starts from the parameters the current layout used, finds its readability
    issues (node overlap, outliers squeezing the rest, clumping, uneven edges,
    stretch), and moves the parameters known to fix them. Nothing is saved or drawn.

    Returns `current` (the present layout's metrics and issues), `candidates` ranked by
    `score` (lower is better), each with the exact `arguments` to pass to the layout
    tool, the parameter `changes`, a plain-words `tradeoff`, and `metric_deltas`
    against the current layout; plus `knobs`, the tunable parameters with their
    recommended ranges and which issue each one fixes.

    To apply a candidate, call `layout_<layout>` with its `arguments`, then
    `visualization_generate`, and report what changed.

    Each candidate is a full layout run, so this takes several times as long as one
    layout (capped at about a minute; `stopped_early` says the budget ran out).
    Layouts without tunable parameters (circular, bfs, ...) return their metrics only.
    """
    with get_db_context() as db:
        from app.logic.layout_optimizer import suggest_parameters

        return suggest_parameters(
            network_id, db, layout_name=layout, max_candidates=max_candidates
        )
