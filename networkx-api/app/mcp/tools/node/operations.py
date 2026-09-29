from typing import Annotated, List, Optional
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
    Do NOT use this to get node IDs for subgraph creation — use `subgraph_extract_filter` (atomic)
    or `subgraph_create_by_filter` (legacy compound) instead, which avoid context window limits
    by filtering server-side.

    Returns:
        dict: {"count": int (all matches), "truncated": bool (True when more than
        `limit` matched), "nodes": [{"id": str, "label": str}] (at most `limit`)}
    """
    with get_db_context() as db:
        from app.logic import filter as filter_logic
        from app.schemas.filter import AttributeCondition, Range

        condition = AttributeCondition(attribute_name=attribute_name)

        if value is not None:
            # Match the text form and, when it parses, the numeric form: a
            # community label "3" is stored as text, a year 2001 as a float.
            condition.categories = [value]
            try:
                condition.categories.append(float(value))
            except ValueError:
                pass

        if min_value is not None or max_value is not None:
            condition.ranges = [Range(min=min_value, max=max_value)]

        nodes = filter_logic.get_nodes_by_filter(network_id, [condition], db)

        return {
            "count": len(nodes),
            "truncated": len(nodes) > limit,
            "nodes": nodes[:limit],
        }


@mcp.tool()
@handle_tool_errors
def node_get_neighbors(
    network_id: Annotated[int, Field(description="The ID of the network.")],
    node_id: Annotated[str, Field(description="The string ID of the node.")],
    include_attributes: Annotated[bool, Field(description="If True, include each listed neighbour's attributes (layout coordinates excluded). Costly for many neighbours; prefer node_compare on a few chosen IDs.")] = False,
    limit: Annotated[int, Field(ge=1, le=500, description="How many neighbours to list, best-connected first. `degree` always reports the full count.")] = 30,
) -> str:
    """
    Returns the immediate neighbors (1-hop) of a specific node, ignoring edge direction.

    Useful for exploring local graph structure around a node of interest.
    Use `node_search` first to find the node ID if needed. To show the
    neighbourhood on the canvas, use visualization_highlight(node_ids=[node_id],
    neighbor_hops=1, edges='incident').

    Returns:
        str: JSON with `degree`, and `neighbors` (id, label, degree, optionally
        attributes) for the `limit` best-connected neighbours.
    """
    with get_db_context() as db:
        from app.logic import exploration
        from app.logic.utils.graph_builder import build_graph_from_db
        from common import models

        graph = build_graph_from_db(network_id, db).to_undirected(as_view=True)
        if node_id not in graph:
            return json.dumps({"error": f"Node '{node_id}' not found in network {network_id}."})

        ranked = sorted(graph[node_id], key=lambda n: (-graph.degree(n), n))
        listed = [n for n in ranked if n != node_id][:limit]
        if include_attributes and listed:
            rows = exploration.compare_nodes(network_id, db, listed[:25])["nodes"]
            result = [{"id": n, **rows[n]} for n in listed[:25]]
        else:
            labels = dict(
                db.query(models.Node.node_id, models.Node.label)
                .filter(
                    models.Node.network_id == network_id,
                    models.Node.node_id.in_(listed),
                )
                .all()
            )
            result = [
                {"id": n, "label": labels.get(n), "degree": graph.degree(n)}
                for n in listed
            ]

        degree = sum(1 for n in graph[node_id] if n != node_id)
        return json.dumps({
            "node_id": node_id,
            "degree": degree,
            "neighbors": result,
            "omitted": degree - len(result),
        }, default=str)


@mcp.tool()
@handle_tool_errors
def node_common_neighbors(
    network_id: Annotated[int, Field(description="The ID of the network.")],
    node_a: Annotated[str, Field(description="Exact ID of the first node.")],
    node_b: Annotated[str, Field(description="Exact ID of the second node.")],
    limit: Annotated[int, Field(ge=1, le=200, description="How many shared neighbours to list, best-connected first.")] = 30,
) -> dict:
    """
    Returns the nodes connected to both A and B, whether A and B are directly linked, and their Jaccard overlap.

    Answers "what do A and B have in common" or "who links these two".
    Direction is ignored. Read-only.
    """
    with get_db_context() as db:
        from app.logic import exploration
        return exploration.common_neighbors(network_id, db, node_a, node_b, limit)


@mcp.tool()
@handle_tool_errors
def node_compare(
    network_id: Annotated[int, Field(description="The ID of the network.")],
    node_ids: Annotated[List[str], Field(description="Exact IDs of up to 25 nodes to compare.")],
    attributes: Annotated[Optional[List[str]], Field(description="Attributes to include. None includes every node attribute except layout coordinates.")] = None,
) -> dict:
    """
    Returns a side-by-side table (label, degree, attributes) for several nodes in one call.

    Use this instead of calling node_get_details once per node when comparing
    or describing a handful of nodes. Read-only.
    """
    with get_db_context() as db:
        from app.logic import exploration
        return exploration.compare_nodes(network_id, db, node_ids, attributes)


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
