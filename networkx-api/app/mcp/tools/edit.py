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
def update_node_label(
    network_id: Annotated[int, Field(description="The ID of the network.")],
    node_id: Annotated[str, Field(description="The ID of the node to update.")],
    new_label: Annotated[str, Field(description="The new label to assign to the node.")]
) -> str:
    """
    Updates the label of a specific node.
    Use this tool when the user wants to rename a node or change its display label.
    
    Returns:
        str: JSON string indicating success or failure.
    """
    with get_db_context() as db:
        from app.logic import edit
        result = edit.update_node_label(network_id, node_id, new_label, db)
        return json.dumps(result)


@mcp.tool()
@handle_tool_errors
def update_network_metadata(
    network_id: Annotated[int, Field(description="The ID of the network.")],
    description: Annotated[Optional[str], Field(description="New description for the network.")] = None,
    name: Annotated[Optional[str], Field(description="New name for the network.")] = None
) -> str:
    """
    Updates the network's name or description.
    
    Returns:
        str: Status message.
    """
    with get_db_context() as db:
        from app.logic import network_metadata
        return network_metadata.update_network_metadata(db, network_id, description, name)
