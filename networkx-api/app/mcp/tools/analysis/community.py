from typing import Annotated
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
    )] = "louvain"
) -> str:
    """
    Detects communities (clusters) in the network and saves them as a 'community' node attribute.

    Community detection finds groups of nodes that are more densely connected to each other
    than to the rest of the network. Results can be used to color nodes by community
    using `visualization_set_node_color` with attribute='community'.

    Saved attribute name: 'community'

    Returns:
        str: Status message with number of communities found.
    """
    with get_db_context() as db:
        from app.logic import community
        community.calculate_community(network_id, algorithm, db)
        return f"Communities detected using '{algorithm}' and saved as 'community' attribute."
