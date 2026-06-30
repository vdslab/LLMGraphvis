from typing import Annotated, Optional
from pydantic import Field
from app.core.mcp import mcp
from app.core.database import get_db_context
from app.core.decorators import handle_tool_errors
import logging
import json

logger = logging.getLogger(__name__)


@mcp.tool()
@handle_tool_errors
def analysis_shortest_path(
    network_id: Annotated[int, Field(description="The ID of the network.")],
    source_node_id: Annotated[str, Field(description="The string ID of the source node.")],
    target_node_id: Annotated[str, Field(description="The string ID of the target node.")]
) -> str:
    """
    Finds the shortest path between two nodes in the network.

    Returns the sequence of node IDs forming the shortest path, along with the path length.
    If no path exists (disconnected graph), returns an appropriate message.
    Use `node_search` first if you need to find node IDs by label.

    Returns:
        str: JSON with {"path": [node_ids], "length": int} or {"error": str}.
    """
    with get_db_context() as db:
        import networkx as nx
        from app.logic.utils.graph_builder import build_graph_from_db

        G = build_graph_from_db(network_id, db)

        if source_node_id not in G:
            return json.dumps({"error": f"Source node '{source_node_id}' not found in network."})
        if target_node_id not in G:
            return json.dumps({"error": f"Target node '{target_node_id}' not found in network."})

        try:
            path = nx.shortest_path(G, source=source_node_id, target=target_node_id)
            return json.dumps({
                "path": path,
                "length": len(path) - 1,
                "source": source_node_id,
                "target": target_node_id
            })
        except nx.NetworkXNoPath:
            return json.dumps({
                "error": f"No path exists between '{source_node_id}' and '{target_node_id}' (disconnected graph)."
            })
