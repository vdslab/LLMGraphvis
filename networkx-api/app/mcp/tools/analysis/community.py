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
            "- 'label_propagation': Very fast, good for large graphs, non-deterministic."
        )
    )] = "louvain",
    resolution: Annotated[Optional[float], Field(description="Louvain-only. Higher values favor smaller/more numerous communities, lower values favor larger/fewer communities. Ignored for other algorithms. Defaults to networkx's own default (1.0) if not specified.")] = None,
    seed: Annotated[Optional[int], Field(description="Louvain-only. Random seed for reproducible results. Ignored for 'greedy_modularity' and 'label_propagation' (neither supports a seed in networkx). Defaults to non-deterministic if not specified.")] = None,
    best_n: Annotated[Optional[int], Field(description="'greedy_modularity'-only. Forces the algorithm to return exactly this many communities. Ignored for other algorithms. Defaults to networkx's own automatic choice if not specified.")] = None,
    force_recompute: Annotated[bool, Field(description="If True, bypasses the cache and always recomputes, even if a valid cached result exists for this exact graph state and parameters. Default False preserves current auto-caching behavior.")] = False
) -> str:
    """
    Detects communities (clusters) in the network and saves them as a node attribute.

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
        str: Status message with the exact saved attribute name and number of communities found.
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
