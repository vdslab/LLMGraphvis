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
def network_list_all() -> str:
    """
    Lists all networks stored in the database, including parent networks and their subgraphs.
    Use this to discover available network IDs before working on them.

    Returns:
        str: JSON list of networks with id, name, description, parent_network_id, and node/edge counts.
    """
    with get_db_context() as db:
        from common import models
        networks = db.query(models.Network).all()
        result = []
        for net in networks:
            node_count = db.query(models.Node).filter(models.Node.network_id == net.id).count()
            edge_count = db.query(models.Edge).filter(models.Edge.network_id == net.id).count()
            result.append({
                "id": net.id,
                "name": net.name,
                "description": net.description,
                "parent_network_id": net.parent_network_id,
                "node_count": node_count,
                "edge_count": edge_count,
                "last_layout": net.last_layout_name,
                "created_at": str(net.created_at),
            })
        return json.dumps(result, default=str)


@mcp.tool()
@handle_tool_errors
def network_get_info(
    network_id: Annotated[int, Field(description="The ID of the network.")]
) -> str:
    """
    Returns a full summary of the network: node/edge counts, density, metadata (name, description),
    and the current visual state (layout, color/size configs).
    Use this before performing heavy operations to understand the dataset.

    Returns:
        str: JSON with structure stats and metadata.
    """
    with get_db_context() as db:
        from app.logic import network_metadata
        structure = network_metadata.get_network_structure(db, network_id)
        metadata = network_metadata.get_network_metadata(db, network_id)
        return json.dumps({**structure, **metadata}, default=str)


@mcp.tool()
@handle_tool_errors
def network_list_node_attributes(
    network_id: Annotated[int, Field(description="The ID of the network.")]
) -> str:
    """
    Lists all available node attributes in the network (e.g., 'degree_centrality', 'community', 'country').
    Use this before coloring/sizing nodes to discover what attributes exist.

    Returns:
        str: JSON list of attribute names and their types/stats.
    """
    with get_db_context() as db:
        from app.logic import network_metadata
        return json.dumps(network_metadata.list_node_attributes(db, network_id), default=str)


@mcp.tool()
@handle_tool_errors
def network_list_edge_attributes(
    network_id: Annotated[int, Field(description="The ID of the network.")]
) -> str:
    """
    Lists all available edge attributes in the network (e.g., 'weight', 'type').
    Use this before styling edges to discover what attributes exist.

    Returns:
        str: JSON list of attribute names and their types/stats.
    """
    with get_db_context() as db:
        from app.logic import network_metadata
        return json.dumps(network_metadata.list_edge_attributes(db, network_id), default=str)


@mcp.tool()
@handle_tool_errors
def network_update_metadata(
    network_id: Annotated[int, Field(description="The ID of the network.")],
    name: Annotated[Optional[str], Field(description="New name for the network.")] = None,
    description: Annotated[Optional[str], Field(description="New description for the network.")] = None
) -> str:
    """
    Updates the network's name or description.
    At least one of name or description must be provided.

    Returns:
        str: Status message.
    """
    with get_db_context() as db:
        from app.logic import network_metadata
        return network_metadata.update_network_metadata(db, network_id, description, name)
