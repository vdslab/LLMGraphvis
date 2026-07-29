from typing import Dict, Any
from sqlalchemy.orm import Session
from common import models
from app.core.logging import get_logger

logger = get_logger(__name__)

def update_node_label(network_id: int, node_id: str, new_label: str, db: Session) -> Dict[str, Any]:
    """
    Updates the label of a specific node in a network.

    Args:
        network_id: The ID of the network.
        node_id: The ID of the node to update.
        new_label: The new label for the node.
        db: Database session.

    Returns:
        A dictionary containing the success status and the updated node details.
    """
    node = (
        db.query(models.Node)
        .filter(models.Node.network_id == network_id, models.Node.node_id == node_id)
        .first()
    )

    if not node:
        return {"error": f"Node '{node_id}' not found in network {network_id}"}

    old_label = node.label
    node.label = new_label
    db.commit()
    db.refresh(node)

    logger.info(f"Updated node label: Network={network_id}, Node={node_id}, '{old_label}' -> '{new_label}'")

    return {
        "status": "success",
        "message": f"Updated label for node '{node_id}' from '{old_label}' to '{new_label}'",
        "node": {
            "id": node.node_id,
            "label": node.label
        }
    }
