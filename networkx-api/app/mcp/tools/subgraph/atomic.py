"""Extraction tools with no implicit visual side effects."""

from typing import Annotated

from app.core.database import get_db_context
from app.core.decorators import handle_tool_errors
from app.core.mcp import mcp
from app.logic.extraction import extract_nodes
from app.logic.filter import get_nodes_by_filter
from app.schemas.filter import AttributeCondition
from pydantic import Field


@mcp.tool()
@handle_tool_errors
def subgraph_extract_nodes(
    network_id: Annotated[int, Field(description="Source network ID.")],
    node_ids: Annotated[list[str], Field(min_length=1, description="Node IDs to retain, including all edges between them. Unknown IDs are rejected.")],
    description: Annotated[str, Field(description="Purpose of this extracted network.")] = "Subgraph",
) -> dict:
    """Extract an induced subgraph; return created_network_id without switching.

    Copies source attributes but excludes derived metrics and coordinates.
    Each call creates a fresh snapshot; does not reuse an older named result.
    Does not calculate layout, select a network, style, or render. To display it,
    call network_select, a layout tool, then visualization_generate explicitly.
    """
    with get_db_context() as db:
        return extract_nodes(network_id, node_ids, db, description)


@mcp.tool()
@handle_tool_errors
def subgraph_extract_filter(
    network_id: Annotated[int, Field(description="Source network ID.")],
    conditions: Annotated[list[AttributeCondition], Field(min_length=1, description="AND between attribute conditions; OR between categories and numeric ranges within each condition. Use attribute_name for the attribute key.")],
    description: Annotated[str, Field(description="Purpose of this extracted network.")] = "Filtered subgraph",
) -> dict:
    """Extract matching nodes server-side without layout or view changes.

    Returns created_network_id. Empty matches are rejected. Prefer this over
    listing thousands of IDs in chat. Source data is copied, derived metrics
    are excluded; recompute metrics on the extracted network when needed.
    """
    with get_db_context() as db:
        matches = get_nodes_by_filter(network_id, conditions, db)
        return extract_nodes(network_id, [row["id"] for row in matches], db, description)


@mcp.tool()
@handle_tool_errors
def network_select(
    network_id: Annotated[int, Field(description="Existing network to use for subsequent analysis in this chat.")],
) -> dict:
    """Select the analysis context without computing a layout or drawing.

    The canvas retains its previous rendering until visualization_generate.
    Use created_network_id from extraction, or an ID returned by subgraph_list.
    """
    with get_db_context() as db:
        from common import models

        network = db.get(models.Network, network_id)
        if network is None:
            raise ValueError(f"Network {network_id} not found")
        return {"network_id": network_id, "content": "Analysis context selected; not rendered."}
