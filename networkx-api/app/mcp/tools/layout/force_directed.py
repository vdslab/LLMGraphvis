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
    "arrangement of the same graph. Null uses fresh randomness; a cached result "
    "is still reused unless force_recompute=True."
)
_WEIGHT_DESC = (
    "Edge attribute to use as connection strength (heavier = drawn closer together). "
    "Leave unset by default: the network's own imported edge weights are used "
    "automatically whenever they vary, so the layout is already weighted, and the return "
    "message names any other numeric edge attribute that could be used instead. Set this "
    "to one of those names when the user wants a different quantity to drive the layout "
    "(a graph can carry several), or to 'none' to ignore weights entirely."
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
    max_iter: Annotated[Optional[int], Field(ge=1, description="Maximum iterations. Defaults to auto from graph size. Runtime grows linearly with it. More is not always better: long runs keep contracting dense regions, so lowering it can reduce overlap.")] = None,
    gravity: Annotated[Optional[float], Field(ge=0, description="Pull toward the center. Higher keeps disconnected parts and isolated nodes near the rest, so outliers stop squeezing the drawing into a corner; lower lets the graph spread out. Defaults to 1, raised automatically for graphs in several parts (the reply says so).")] = None,
    scaling_ratio: Annotated[Optional[float], Field(gt=0, description="Repulsion between nodes. Higher spreads nodes apart; lower compacts them. Defaults to auto from the (weighted) average degree.")] = None,
    jitter_tolerance: Annotated[Optional[float], Field(gt=0, description="Tolerance for the adaptive step size (nx 'jitter tolerance'). Defaults to 1.0. Lower converges more precisely but more slowly; higher allows faster, looser movement.")] = None,
    strong_gravity: Annotated[Optional[bool], Field(description="If True, gravity grows with distance from the center, pulling far-flung nodes and components back in, which gives a rounder, more centered drawing. Useful when outliers squeeze the rest, or the graph spreads too thinly.")] = None,
    linlog: Annotated[Optional[bool], Field(description="If True, use a logarithmic attraction model. Separates clusters more sharply than the default linear model — a good choice when the user wants community structure emphasized.")] = None,
    distributed_action: Annotated[Optional[bool], Field(description="If True, distributes the attraction force across a node's degree, which prevents high-degree hubs from collapsing their neighbors onto themselves.")] = None,
    node_mass: Annotated[Optional[dict[str, float]], Field(description="Optional mapping of node id to mass. Heavier nodes move less. Omit for the default (mass derived from degree).")] = None,
    size_aware: Annotated[Optional[bool], Field(description="If True, repulsion accounts for how large each node is drawn (its current node-size style), so large nodes push each other apart instead of overlapping. Use this when large nodes overlap; it roughly doubles the runtime. Recompute after changing node sizes.")] = None,
    node_size: Annotated[Optional[dict[str, float]], Field(description="Explicit node id -> radius in the layout's own coordinate units (not drawn units). Rarely needed; prefer size_aware=True, which derives radii from the drawn sizes. Cannot be combined with size_aware.")] = None,
    weight: Annotated[Optional[str], Field(description=_WEIGHT_DESC)] = None,
    seed: Annotated[Optional[int], Field(description=_SEED_DESC)] = 42,
    pos: Annotated[Optional[dict[str, Tuple[float, float]]], Field(description="Explicit initial x/y coordinates keyed by exact node ID. Partial positions are allowed where NetworkX supports them. Cannot be combined with init_from_layout; fixed nodes must have positions.")] = None,
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

    After calling this, use `visualization_generate` to render the result; its
    `layout_quality` says how readable the drawing is, and `layout_suggest_parameters`
    searches for parameters that fix the issues it lists.

    Returns:
        str: Status message.
    Coordinates are fixed to 2D (NetworkX dim=2). NetworkX store_pos_as is
    replaced by database attributes named after the layout: <layout>_x/y.
    Omitted/null tuning parameters use app defaults unless stated otherwise.

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
            "size_aware": size_aware,
            "weight": weight,
            "seed": seed,
            "init_from_layout": init_from_layout,
            "pos": pos,
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
    iterations: Annotated[Optional[int], Field(ge=1, description="Number of iterations. Defaults to auto from graph size. More is not always better: on trees and sparse graphs long runs can pile leaves onto each other, so fewer iterations may reduce overlap.")] = None,
    k: Annotated[Optional[float], Field(gt=0, description="Optimal distance between nodes, relative to the other forces. Defaults to auto from node count. Higher gives more room between neighbours relative to the whole drawing; because the drawing is rescaled to the canvas, its effect on overlap depends on the graph.")] = None,
    threshold: Annotated[Optional[float], Field(gt=0, description="Convergence threshold on total node movement; iteration stops below it. Defaults to auto from graph size. Lower is more precise and slower.")] = None,
    method: Annotated[Optional[str], Field(description="Force computation method: 'auto' (default), 'energy' (energy minimization with per-component gravity, set automatically for graphs in several parts), or 'force' (Fruchterman-Reingold force simulation).")] = None,
    gravity: Annotated[Optional[float], Field(ge=0, description="Pull of each connected component toward the center. Higher keeps separate parts close to the rest, so they stop squeezing the drawing. Only used by the 'energy' method; setting it without method='energy' has no effect.")] = None,
    fixed: Annotated[Optional[list[str]], Field(description="List of node ids to hold at their current positions while the rest of the graph moves around them. Requires pos or init_from_layout for those nodes. Renderer normalization can still change their screen positions.")] = None,
    weight: Annotated[Optional[str], Field(description=_WEIGHT_DESC)] = None,
    scale: Annotated[Optional[float], Field(description=_SCALE_CENTER_DESC)] = None,
    center: Annotated[Optional[Tuple[float, float]], Field(description=_SCALE_CENTER_DESC)] = None,
    seed: Annotated[Optional[int], Field(description=_SEED_DESC)] = 42,
    pos: Annotated[Optional[dict[str, Tuple[float, float]]], Field(description="Explicit initial x/y coordinates keyed by exact node ID. Partial positions are allowed where NetworkX supports them. Cannot be combined with init_from_layout; fixed nodes must have positions.")] = None,
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

    After calling this, use `visualization_generate` to render the result; its
    `layout_quality` says how readable the drawing is, and `layout_suggest_parameters`
    searches for parameters that fix the issues it lists.

    Returns:
        str: Status message.
    Coordinates are fixed to 2D (NetworkX dim=2). NetworkX store_pos_as is
    replaced by database attributes named after the layout: <layout>_x/y.
    Omitted/null tuning parameters use app defaults unless stated otherwise.

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
            "pos": pos,
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
    scaling: Annotated[Optional[float], Field(gt=0, description="Repulsion scale. Higher spreads nodes further apart, reducing overlap and clumping.")] = None,
    a: Annotated[Optional[float], Field(gt=1, description="Strength of the spring force relative to repulsion. Must be > 1. Higher pulls connected nodes tighter together, which also draws far-flung nodes back in.")] = None,
    etol: Annotated[Optional[float], Field(description="Energy tolerance for stopping. Lower converges further at more cost.")] = None,
    dt: Annotated[Optional[float], Field(description="Integration step size. Smaller is more stable but slower to converge.")] = None,
    max_iter: Annotated[Optional[int], Field(ge=1, description="Maximum iterations. Defaults to auto from graph size.")] = None,
    seed: Annotated[Optional[int], Field(description=_SEED_DESC)] = 42,
    pos: Annotated[Optional[dict[str, Tuple[float, float]]], Field(description="Explicit initial x/y coordinates keyed by exact node ID. Partial positions are allowed where NetworkX supports them. Cannot be combined with init_from_layout; fixed nodes must have positions.")] = None,
    init_from_layout: Annotated[Optional[str], Field(description=_INIT_FROM_DESC)] = None,
    force_recompute: Annotated[bool, Field(description=_FORCE_RECOMPUTE_DESC)] = False,
) -> str:
    """
    Calculates an ARF (attractive-repulsive force) layout and saves x, y coordinates.

    ARF is a spring-based layout with separate control over attraction (`a`) and overall
    spread (`scaling`). Best used as a second attempt when ForceAtlas2 leaves too much
    node overlap, or when the user wants finer control over the attraction/repulsion
    balance than ForceAtlas2 exposes.

    After calling this, use `visualization_generate` to render the result; its
    `layout_quality` says how readable the drawing is, and `layout_suggest_parameters`
    searches for parameters that fix the issues it lists.

    Returns:
        str: Status message.
    Coordinates are fixed to 2D (NetworkX dim=2). NetworkX store_pos_as is
    replaced by database attributes named after the layout: <layout>_x/y.
    Omitted/null tuning parameters use app defaults unless stated otherwise.

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
            "pos": pos,
        }
        info = layout.calculate_layout(
            network_id, "arf", db, overrides=overrides, force=force_recompute
        )
        return layout.format_layout_result(info, "ARF layout calculated. Call `visualization_generate` to render.")
