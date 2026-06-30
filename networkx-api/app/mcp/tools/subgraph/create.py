from typing import Annotated, Any, Dict, List, Optional
from pydantic import Field
from app.core.mcp import mcp
from app.core.database import get_db_context
from app.core.decorators import handle_tool_errors
import logging
import traceback

logger = logging.getLogger(__name__)


@mcp.tool()
@handle_tool_errors
def subgraph_list(
    network_id: Annotated[int, Field(description="The ID of the parent network.")]
) -> dict:
    """
    Lists all subgraphs derived from the given parent network.

    Use this to discover previously created subgraphs before navigating to them
    with `visualization_switch_network`.

    Returns:
        dict: {"subgraphs": [{"id": int, "name": str, "created_at": str}]}
    """
    with get_db_context() as db:
        from app.logic import network_metadata
        subgraphs = network_metadata.get_subgraphs(db, network_id)
        return {"subgraphs": subgraphs}


@mcp.tool()
@handle_tool_errors
def subgraph_create_from_nodes(
    network_id: Annotated[int, Field(description="The ID of the source network.")],
    node_ids: Annotated[List[str], Field(description="Explicit list of node string IDs to include in the subgraph.")],
    description: Annotated[str, Field(description="Description for the new subgraph.")] = "Custom subgraph",
    preserve_layout: Annotated[bool, Field(description="If True, copies x,y coordinates from the source network.")] = True
) -> dict:
    """
    Creates a new subgraph from an explicit list of node IDs.

    Use this ONLY when the user provides a specific list of node IDs (e.g., "create a subgraph
    for nodes A, B, and C"). For attribute-based filtering, use `subgraph_create_by_filter` instead.

    After creation, call `visualization_switch_network(new_network_id)` to display the result.

    Returns:
        dict: {"new_network_id": int, "content": str}
    """
    with get_db_context() as db:
        from app.logic import subgraph
        result = subgraph.create_subgraph_from_nodes(
            source_network_id=network_id,
            node_ids=node_ids,
            db=db,
            suffix="Subgraph",
            preserve_layout=preserve_layout,
            description=description
        )
        return {
            "new_network_id": result["new_network_id"],
            "content": f"Subgraph created (ID: {result['new_network_id']}) with {len(node_ids)} nodes."
        }


@mcp.tool()
@handle_tool_errors
def subgraph_create_by_filter(
    network_id: Annotated[int, Field(description="The ID of the network.")],
    conditions: Annotated[List[Dict[str, Any]], Field(
        description=(
            "List of filter conditions combined with AND logic. "
            "Each condition: {\"attribute\": \"Name\", \"categories\": [\"A\", \"B\"], \"ranges\": [{\"min\": 10, \"max\": 20}]}. "
            "Within a condition, categories and ranges are combined with OR."
        )
    )],
    preserve_layout: Annotated[bool, Field(description="If True, keeps x,y positions from source network.")] = True,
    description: Annotated[Optional[str], Field(description="Description for the new subgraph.")] = None
) -> dict:
    """
    Creates a new subgraph by filtering nodes based on attribute conditions.

    Preferred over `subgraph_create_from_nodes` for attribute-based filtering because
    it handles large result sets server-side without hitting context window limits.

    Condition schema:
    - "attribute": attribute name (e.g., "country", "community", "degree_centrality")
    - "categories": list of exact string/numeric matches (OR within condition)
    - "ranges": list of {"min": float, "max": float} numeric ranges (OR within condition)
    Multiple conditions are combined with AND.

    After creation, call `visualization_switch_network(new_network_id)` to display.

    Returns:
        dict: {"new_network_id": int, "content": str}
    """
    with get_db_context() as db:
        try:
            from app.logic import filter as filter_logic
            from app.schemas.filter import AttributeCondition, Range

            parsed_conditions = []
            for cond_dict in conditions:
                attr_name = cond_dict.get("attribute")
                if not attr_name:
                    continue

                categories = cond_dict.get("categories")
                ranges_data = cond_dict.get("ranges")
                parsed_ranges = None
                if ranges_data:
                    parsed_ranges = [Range(min=r.get("min"), max=r.get("max")) for r in ranges_data]

                parsed_conditions.append(AttributeCondition(
                    attribute_name=attr_name,
                    categories=categories,
                    ranges=parsed_ranges
                ))

            if not parsed_conditions:
                raise ValueError("No valid conditions provided.")

            result = filter_logic.create_subgraph_by_filter(
                network_id=network_id,
                conditions=parsed_conditions,
                suffix="Filtered",
                db=db,
                preserve_layout=preserve_layout,
                description=description or "Custom filtered subgraph"
            )

            return {
                "new_network_id": result["new_network_id"],
                "content": f"Subgraph created (ID: {result['new_network_id']}) based on filters."
            }

        except Exception as e:
            logger.error(f"subgraph_create_by_filter failed: {e}\n{traceback.format_exc()}")
            raise RuntimeError(f"Subgraph creation by filter failed: {str(e)}") from e
