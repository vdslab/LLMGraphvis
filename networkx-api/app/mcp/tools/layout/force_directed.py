from typing import Annotated, Optional, Tuple
from pydantic import Field
from app.core.mcp import mcp
from app.core.database import get_db_context
from app.core.decorators import handle_tool_errors
import logging

logger = logging.getLogger(__name__)

# Shared parameter descriptions. Wording is duplicated across tools where the
# meaning is identical so each tool's schema reads standalone for the model.
_FORCE_RECOMPUTE_DESC = (
    "If True, bypasses the cache and always recomputes. The cache key already includes "
    "every parameter below, so changing a parameter recomputes on its own — set this only "
    "when the user explicitly wants the same computation redone."
)
_SEED_DESC = (
    "Random seed for the initial node placement. Force layouts start from random "
    "positions, so successive runs differ unless this is fixed. Defaults to 42, meaning "
    "results are reproducible by default; pass a different value to get a different "
    "arrangement of the same graph."
)
_WEIGHT_DESC = (
    "Edge attribute to use as connection strength. Leave this unset in almost every case: "
    "when the network's edges carry varying weights they are used automatically, so the "
    "default layout is already weighted and stronger connections are already drawn closer "
    "together. Set it only to point at a different numeric edge attribute, or to 'none' to "
    "force an unweighted layout because the user explicitly asked to ignore the weights."
)
_SCALE_CENTER_DESC = (
    "Accepted for completeness but has NO visible effect: the renderer normalizes all "
    "coordinates to a fixed [-1000, 1000] extent before drawing. Do not use this to zoom "
    "or reposition the view."
)
_INIT_FROM_DESC = (
    "Name of a previously computed layout ('forceatlas2', 'spring', ...) whose stored "
    "coordinates become the starting positions, instead of starting from random. Use this "
    "to refine an existing arrangement rather than producing an unrelated new one."
)


@mcp.tool()
@handle_tool_errors
def layout_forceatlas2(
    network_id: Annotated[int, Field(description="The ID of the network.")],
    max_iter: Annotated[Optional[int], Field(description="Maximum iterations. Defaults to auto: max(200, min(2000, node_count)). Higher values converge further at a roughly linear time cost.")] = None,
    gravity: Annotated[Optional[float], Field(description="Strength of the pull toward the center, which keeps disconnected parts from drifting away. Defaults to 1.0. Lower spreads the graph out; higher compacts it.")] = None,
    scaling_ratio: Annotated[Optional[float], Field(description="Node repulsion strength. Defaults to auto from average degree, clamped to [2.0, 10.0]. Raise this to spread overlapping nodes apart.")] = None,
    jitter_tolerance: Annotated[Optional[float], Field(description="Tolerance for the adaptive step size (nx 'jitter tolerance'). Defaults to 1.0. Lower converges more precisely but more slowly; higher allows faster, looser movement.")] = None,
    strong_gravity: Annotated[Optional[bool], Field(description="If True, gravity pulls with a force independent of distance, producing a tighter, more centered cluster. Useful when a graph spreads too thinly.")] = None,
    linlog: Annotated[Optional[bool], Field(description="If True, use a logarithmic attraction model. Separates clusters more sharply than the default linear model — a good choice when the user wants community structure emphasized.")] = None,
    distributed_action: Annotated[Optional[bool], Field(description="If True, distributes the attraction force across a node's degree, which prevents high-degree hubs from collapsing their neighbors onto themselves.")] = None,
    node_mass: Annotated[Optional[dict], Field(description="Optional mapping of node id to mass. Heavier nodes move less. Omit for the default (mass derived from degree).")] = None,
    node_size: Annotated[Optional[dict], Field(description="Optional mapping of node id to radius, enabling size-aware repulsion so large nodes push each other apart instead of overlapping. Pass this when large nodes visibly overlap.")] = None,
    weight: Annotated[Optional[str], Field(description=_WEIGHT_DESC)] = None,
    seed: Annotated[Optional[int], Field(description=_SEED_DESC)] = None,
    init_from_layout: Annotated[Optional[str], Field(description=_INIT_FROM_DESC)] = None,
    force_recompute: Annotated[bool, Field(description=_FORCE_RECOMPUTE_DESC)] = False,
) -> str:
    """
    Calculates a ForceAtlas2 force-directed layout and saves x, y coordinates as node attributes.

    ForceAtlas2 is the **recommended default** for most networks. It produces organic,
    readable layouts by simulating repulsion between nodes and attraction along edges.
    Best for: general-purpose graphs, social networks, medium-to-large networks.

    Note that each iteration computes dense pairwise repulsion (O(N^2), no Barnes-Hut
    approximation), so `max_iter` dominates runtime on large graphs.

    If the network's edges carry varying weights, they are used as attraction strength
    automatically — no parameter needed. The returned message says when that happened.

    After calling this, use `visualization_generate` to render the result.

    Returns:
        str: Status message.
    """
    with get_db_context() as db:
        from app.logic import layout
        overrides = {
            "max_iter": max_iter,
            "gravity": gravity,
            "scaling_ratio": scaling_ratio,
            "jitter_tolerance": jitter_tolerance,
            "strong_gravity": strong_gravity,
            "linlog": linlog,
            "distributed_action": distributed_action,
            "node_mass": node_mass,
            "node_size": node_size,
            "weight": weight,
            "seed": seed,
            "init_from_layout": init_from_layout,
        }
        info = layout.calculate_layout(
            network_id, "forceatlas2", db, overrides=overrides, force=force_recompute
        )
        return layout.format_layout_result(
            info,
            "ForceAtlas2 layout calculated.",
            "Call `visualization_generate` to render.",
        )


@mcp.tool()
@handle_tool_errors
def layout_spring(
    network_id: Annotated[int, Field(description="The ID of the network.")],
    iterations: Annotated[Optional[int], Field(description="Number of iterations. Defaults to auto (200–1000 based on graph size).")] = None,
    k: Annotated[Optional[float], Field(description="Optimal distance between nodes. Defaults to auto (2.0/sqrt(node_count)). Larger values increase spacing between nodes.")] = None,
    threshold: Annotated[Optional[float], Field(description="Convergence threshold on total node movement; iteration stops below it. Defaults to auto (1e-6 to 1e-4 based on graph size). Lower is more precise and slower.")] = None,
    method: Annotated[Optional[str], Field(description="Force computation method: 'auto' (default), 'energy' (exact, better quality, slower), or 'force' (approximate, faster on large graphs).")] = None,
    gravity: Annotated[Optional[float], Field(description="Strength of the pull toward the center, which keeps disconnected components from drifting apart. Only used by the 'energy' method.")] = None,
    fixed: Annotated[Optional[list], Field(description="List of node ids to hold at their current positions while the rest of the graph moves around them. Requires init_from_layout so those nodes have positions to be held at.")] = None,
    weight: Annotated[Optional[str], Field(description=_WEIGHT_DESC)] = None,
    scale: Annotated[Optional[float], Field(description=_SCALE_CENTER_DESC)] = None,
    center: Annotated[Optional[Tuple[float, float]], Field(description=_SCALE_CENTER_DESC)] = None,
    seed: Annotated[Optional[int], Field(description=_SEED_DESC)] = None,
    init_from_layout: Annotated[Optional[str], Field(description=_INIT_FROM_DESC)] = None,
    force_recompute: Annotated[bool, Field(description=_FORCE_RECOMPUTE_DESC)] = False,
) -> str:
    """
    Calculates a Spring (Fruchterman-Reingold) force-directed layout and saves x, y coordinates.

    Similar to ForceAtlas2 but uses the classic Fruchterman-Reingold algorithm. It tends
    to produce more even node spacing and less pronounced clustering than ForceAtlas2.
    Best for: small-to-medium graphs (< 500 nodes) where high-quality convergence is needed.
    Slower than ForceAtlas2 on large graphs.

    If the network's edges carry varying weights, they are used as attraction strength
    automatically — no parameter needed.

    After calling this, use `visualization_generate` to render the result.

    Returns:
        str: Status message.
    """
    with get_db_context() as db:
        from app.logic import layout
        overrides = {
            "iterations": iterations,
            "k": k,
            "threshold": threshold,
            "method": method,
            "gravity": gravity,
            "fixed": fixed,
            "weight": weight,
            "scale": scale,
            "center": center,
            "seed": seed,
            "init_from_layout": init_from_layout,
        }
        info = layout.calculate_layout(
            network_id, "spring", db, overrides=overrides, force=force_recompute
        )
        return layout.format_layout_result(
            info,
            "Spring layout calculated.",
            "Call `visualization_generate` to render.",
        )


@mcp.tool()
@handle_tool_errors
def layout_arf(
    network_id: Annotated[int, Field(description="The ID of the network.")],
    scaling: Annotated[Optional[float], Field(description="Overall scaling of the layout. Larger values spread nodes further apart.")] = None,
    a: Annotated[Optional[float], Field(description="Strength of the spring force relative to repulsion. Must be > 1. Larger values pull connected nodes tighter together.")] = None,
    etol: Annotated[Optional[float], Field(description="Energy tolerance for stopping. Lower converges further at more cost.")] = None,
    dt: Annotated[Optional[float], Field(description="Integration step size. Smaller is more stable but slower to converge.")] = None,
    max_iter: Annotated[Optional[int], Field(description="Maximum iterations. Defaults to auto (200–1000 based on graph size).")] = None,
    seed: Annotated[Optional[int], Field(description=_SEED_DESC)] = None,
    init_from_layout: Annotated[Optional[str], Field(description=_INIT_FROM_DESC)] = None,
    force_recompute: Annotated[bool, Field(description=_FORCE_RECOMPUTE_DESC)] = False,
) -> str:
    """
    Calculates an ARF (attractive-repulsive force) layout and saves x, y coordinates.

    ARF is a spring-based layout with separate control over attraction (`a`) and overall
    spread (`scaling`). Best used as a second attempt when ForceAtlas2 leaves too much
    node overlap, or when the user wants finer control over the attraction/repulsion
    balance than ForceAtlas2 exposes.

    After calling this, use `visualization_generate` to render the result.

    Returns:
        str: Status message.
    """
    with get_db_context() as db:
        from app.logic import layout
        overrides = {
            "scaling": scaling,
            "a": a,
            "etol": etol,
            "dt": dt,
            "max_iter": max_iter,
            "seed": seed,
            "init_from_layout": init_from_layout,
        }
        layout.calculate_layout(
            network_id, "arf", db, overrides=overrides, force=force_recompute
        )
        return "ARF layout calculated. Call `visualization_generate` to render."
