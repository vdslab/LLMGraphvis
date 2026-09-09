from typing import Annotated, Optional
from pydantic import Field
from app.core.mcp import mcp
from app.core.database import get_db_context
from app.core.decorators import handle_tool_errors
import logging

logger = logging.getLogger(__name__)


@mcp.tool()
@handle_tool_errors
def analysis_detect_communities(
    network_id: Annotated[int, Field(description="The ID of the network.")],
    algorithm: Annotated[str, Field(
        description=(
            "Community detection algorithm to use:\n"
            "- 'louvain' (default): High-quality, fast, works well on most graphs.\n"
            "- 'greedy_modularity': Good modularity optimization, deterministic.\n"
            "- 'label_propagation': Semi-synchronous propagation for undirected graphs."
        )
    )] = "louvain",
    resolution: Annotated[Optional[float], Field(description="Louvain or greedy modularity. Higher values favor smaller/more numerous communities, lower values favor larger/fewer communities. Rejected for other algorithms. Defaults to networkx's own default (1.0) if not specified.")] = None,
    seed: Annotated[Optional[int], Field(description="Louvain-only. Random seed for reproducible results. Rejected for 'greedy_modularity' and 'label_propagation' (neither supports a seed in networkx). Defaults to non-deterministic if not specified.")] = None,
    best_n: Annotated[Optional[int], Field(description="'greedy_modularity'-only. Forces merging until at most this many communities remain. Rejected for other algorithms. Defaults to networkx's own automatic choice if not specified.")] = None,
    force_recompute: Annotated[bool, Field(description="If True, bypasses the cache and always recomputes, even if a valid cached result exists for this exact graph state and parameters. Default False preserves current auto-caching behavior.")] = False
) -> str:
    """
    Legacy algorithm-selecting community tool. Prefer analysis_louvain_communities,
    analysis_greedy_modularity_communities, or analysis_label_propagation_communities
    for algorithm-specific parameters. Saves a node attribute without rendering.

    Community detection finds groups of nodes that are more densely connected to each other
    than to the rest of the network. Results can be used to color nodes by community
    using `visualization_set_node_color`.

    IMPORTANT: The saved attribute name is NOT a fixed value called 'community'. It is
    dynamically named as f"{algorithm}_community" (e.g. 'louvain_community',
    'greedy_modularity_community', 'label_propagation_community'). Always read the
    returned status message from this tool to get the exact attribute name that was
    saved, then use that exact name with `visualization_set_node_color` or
    `subgraph_community` — do not assume/hardcode a name.

    Returns:
        str: Status message with the exact saved attribute name.
    """
    with get_db_context() as db:
        from app.logic import community
        attr_name = community.calculate_community(
            network_id,
            algorithm,
            db,
            resolution=resolution,
            seed=seed,
            best_n=best_n,
            force=force_recompute,
        )
        return f"Communities detected using '{algorithm}' and saved as '{attr_name}' attribute."


@mcp.tool()
@handle_tool_errors
def analysis_louvain_communities(
    network_id: Annotated[int, Field(description="Network to partition.")],
    weight: Annotated[Optional[str], Field(description="Edge strength attribute, 'weight' for imported strength; omit/null/'none' for unweighted.")] = None,
    resolution: Annotated[float, Field(gt=0, allow_inf_nan=False, description="Below 1 favors larger communities; above 1 favors smaller communities.")] = 1.0,
    threshold: Annotated[float, Field(ge=0, allow_inf_nan=False, description="Stop when modularity gain between levels is below this value.")] = 1e-7,
    max_level: Annotated[Optional[int], Field(gt=0, description="Maximum hierarchy levels; omit for no explicit cap.")] = None,
    seed: Annotated[Optional[int], Field(description="Random seed; 42 is reproducible, null uses fresh randomness.")] = 42,
    force_recompute: Annotated[bool, Field(description="Bypass a valid cache for the same graph and parameters.")] = False,
) -> str:
    """Run Louvain and save 'louvain_community'; supports directed/undirected graphs.

    Edge weights mean connection strength. Self-loops affect community retention.
    No coloring, subgraph extraction, view switch, or rendering is performed.
    """
    with get_db_context() as db:
        from app.logic.community import calculate_community
        name = calculate_community(network_id, "louvain", db, weight=weight,
                                   resolution=resolution, threshold=threshold,
                                   max_level=max_level, seed=seed, force=force_recompute)
        return f"Saved '{name}'."


@mcp.tool()
@handle_tool_errors
def analysis_greedy_modularity_communities(
    network_id: Annotated[int, Field(description="Network to partition.")],
    weight: Annotated[Optional[str], Field(description="Edge strength attribute; omit/null/'none' for unweighted.")] = None,
    resolution: Annotated[float, Field(gt=0, allow_inf_nan=False, description="Modularity resolution; below 1 favors larger communities, above 1 smaller.")] = 1.0,
    cutoff: Annotated[int, Field(ge=1, description="Stop merging at this lower bound on the number of groups, even if modularity could improve.")] = 1,
    best_n: Annotated[Optional[int], Field(ge=1, description="Force merging until at most this many groups remain. For exactly k groups, set cutoff=best_n=k. Must be at least cutoff and at most node count.")] = None,
    force_recompute: Annotated[bool, Field(description="Bypass a valid cache for the same graph and parameters.")] = False,
) -> str:
    """Run greedy modularity maximization and save 'greedy_modularity_community'.

    No random seed is used. No coloring, extraction, switching, or rendering.
    """
    with get_db_context() as db:
        from app.logic.community import calculate_community
        name = calculate_community(network_id, "greedy_modularity", db, weight=weight,
                                   resolution=resolution, cutoff=cutoff, best_n=best_n,
                                   force=force_recompute)
        return f"Saved '{name}'."


@mcp.tool()
@handle_tool_errors
def analysis_label_propagation_communities(
    network_id: Annotated[int, Field(description="Undirected network to partition.")],
    force_recompute: Annotated[bool, Field(description="Bypass a valid cache for the same graph.")] = False,
) -> str:
    """Run semi-synchronous label propagation; save 'label_propagation_community'.

    Requires an undirected graph. This NetworkX algorithm accepts neither weights
    nor seed. No coloring, extraction, switching, or rendering is performed.
    """
    with get_db_context() as db:
        from app.logic.community import calculate_community
        name = calculate_community(network_id, "label_propagation", db, force=force_recompute)
        return f"Saved '{name}'."
