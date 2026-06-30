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
def node_search(
    network_id: Annotated[int, Field(description="The ID of the network.")],
    query: Annotated[str, Field(description="Search string matched against node ID and label (case-insensitive partial match).")],
    limit: Annotated[int, Field(description="Maximum number of results to return.")] = 10
) -> str:
    """
    Searches for nodes whose ID or label contains the query string.

    Returns a ranked list of matching nodes with their IDs and labels.
    Use this to find node IDs when you know a name but not the exact ID.

    Returns:
        str: JSON list of matching nodes with id, label, and match info.
    """
    with get_db_context() as db:
        from app.logic import search
        results = search.search_nodes(network_id, query, limit=limit, db=db)
        return json.dumps(results, default=str)


@mcp.tool()
@handle_tool_errors
def node_get_details(
    network_id: Annotated[int, Field(description="The ID of the network.")],
    node_id: Annotated[str, Field(description="The string ID of the node (as returned by node_search).")]
) -> str:
    """
    Retrieves all attributes and metadata for a specific node.

    Returns the full attribute set: computed metrics (centrality, community),
    original GraphML attributes, and layout coordinates.
    Use `node_search` first if you need to look up the node ID.

    Returns:
        str: JSON with id, label, description, and all attributes.
    """
    with get_db_context() as db:
        from app.logic import search
        result = search.get_node_details(network_id, node_id, db)
        if result is None:
            return json.dumps({"error": f"Node '{node_id}' not found in network {network_id}."})
        return json.dumps(result, default=str)


@mcp.tool()
@handle_tool_errors
def node_get_top_ranked(
    network_id: Annotated[int, Field(description="The ID of the network.")],
    metric: Annotated[str, Field(description="Node attribute to rank by (e.g., 'degree_centrality', 'pagerank', 'betweenness_centrality'). Calculate it first if needed.")],
    n: Annotated[int, Field(description="Number of top nodes to return.")] = 10,
    order: Annotated[str, Field(description="'desc' (highest first, default) or 'asc' (lowest first).")] = "desc"
) -> str:
    """
    Returns the top N nodes ranked by a specific numeric attribute.

    Use this to find the most central, influential, or highly-scored nodes.
    The metric must already exist as a node attribute — call the relevant analysis
    tool first (e.g., `analysis_degree_centrality`, `analysis_pagerank`).

    Returns:
        str: JSON list of {"node_id": str, "score": float} sorted by score.
    """
    with get_db_context() as db:
        from app.logic import centrality
        return json.dumps(centrality.get_top_nodes(network_id, metric, n, order, db), default=str)


@mcp.tool()
@handle_tool_errors
def node_filter(
    network_id: Annotated[int, Field(description="The ID of the network.")],
    attribute_name: Annotated[str, Field(description="Attribute name to filter by (e.g., 'country', 'community').")],
    value: Annotated[Optional[str], Field(description="Exact match value (text or numeric as string).")] = None,
    min_value: Annotated[Optional[float], Field(description="Minimum numeric value (inclusive).")] = None,
    max_value: Annotated[Optional[float], Field(description="Maximum numeric value (inclusive).")] = None,
    limit: Annotated[int, Field(description="Maximum number of nodes to return.")] = 100
) -> dict:
    """
    Lists nodes matching a specific attribute condition WITHOUT creating a new network.

    Use this for inspection/reporting (e.g., "list all Austrian composers", "find nodes with degree > 10").
    Do NOT use this to get node IDs for subgraph creation — use `subgraph_create_by_filter` instead,
    which avoids context window limits by filtering server-side.

    Returns:
        dict: {"count": int, "truncated": bool, "nodes": [{"id": str, "label": str}]}
    """
    with get_db_context() as db:
        from app.logic import filter as filter_logic
        from app.schemas.filter import AttributeCondition, Range

        condition = AttributeCondition(attribute_name=attribute_name)

        if value is not None:
            try:
                condition.categories = [float(value)]
            except ValueError:
                condition.categories = [value]

        if min_value is not None or max_value is not None:
            condition.ranges = [Range(min=min_value, max=max_value)]

        nodes = filter_logic.get_nodes_by_filter(network_id, [condition], db)

        truncated = False
        if len(nodes) > limit:
            nodes = nodes[:limit]
            truncated = True

        return {
            "count": len(nodes),
            "truncated": truncated,
            "nodes": nodes
        }


@mcp.tool()
@handle_tool_errors
def node_get_neighbors(
    network_id: Annotated[int, Field(description="The ID of the network.")],
    node_id: Annotated[str, Field(description="The string ID of the node.")],
    include_attributes: Annotated[bool, Field(description="If True, include all attributes for each neighbor node.")] = False
) -> str:
    """
    Returns the immediate neighbors (1-hop) of a specific node.

    Useful for exploring local graph structure around a node of interest.
    Use `node_search` first to find the node ID if needed.

    Returns:
        str: JSON list of neighbor nodes with id, label, and optionally attributes.
    """
    with get_db_context() as db:
        from common import models

        node = db.query(models.Node).filter(
            models.Node.network_id == network_id,
            models.Node.node_id == node_id
        ).first()

        if not node:
            return json.dumps({"error": f"Node '{node_id}' not found in network {network_id}."})

        edges = db.query(models.Edge).filter(
            models.Edge.network_id == network_id,
            (models.Edge.source_node_id == node.id) | (models.Edge.target_node_id == node.id)
        ).all()

        neighbor_db_ids = set()
        for e in edges:
            if e.source_node_id != node.id:
                neighbor_db_ids.add(e.source_node_id)
            if e.target_node_id != node.id:
                neighbor_db_ids.add(e.target_node_id)

        neighbors = db.query(models.Node).filter(
            models.Node.id.in_(neighbor_db_ids)
        ).all()

        if include_attributes:
            from app.logic import search
            result = [search.get_node_details(network_id, n.node_id, db) for n in neighbors]
        else:
            result = [{"id": n.node_id, "label": n.label} for n in neighbors]

        return json.dumps({
            "node_id": node_id,
            "degree": len(result),
            "neighbors": result
        }, default=str)


@mcp.tool()
@handle_tool_errors
def node_update_label(
    network_id: Annotated[int, Field(description="The ID of the network.")],
    node_id: Annotated[str, Field(description="The string ID of the node to rename.")],
    new_label: Annotated[str, Field(description="The new display label to assign.")]
) -> str:
    """
    Updates the display label of a specific node.

    Use this when the user wants to rename a node or correct its display name.
    The node's ID remains unchanged; only the visible label is updated.

    Returns:
        str: JSON status indicating success or failure.
    """
    with get_db_context() as db:
        from app.logic import edit
        result = edit.update_node_label(network_id, node_id, new_label, db)
        return json.dumps(result)
