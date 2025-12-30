from typing import Annotated
from pydantic import Field
from app.core.mcp import mcp
from app.core.database import get_db_context
import logging
import json

logger = logging.getLogger(__name__)

@mcp.tool()
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
        try:
            from app.logic import edit
            result = edit.update_node_label(network_id, node_id, new_label, db)
            return json.dumps(result)
        except Exception as e:
            logger.error(f"update_node_label failed: {e}")
            raise RuntimeError(f"Failed to update node label: {str(e)}") from e
