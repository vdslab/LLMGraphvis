"""Create an induced subgraph without layout, context switching, or rendering."""

from sqlalchemy.orm import Session

from common import models

from .subgraph import create_subgraph_from_nodes


def extract_nodes(
    network_id: int, node_ids: list[str], db: Session, description: str = "Subgraph"
) -> dict:
    selected = set(node_ids)
    if not selected:
        raise ValueError("Select at least one node before extracting a subgraph.")
    available = {
        row.node_id
        for row in db.query(models.Node.node_id).filter_by(network_id=network_id)
    }
    missing = selected - available
    if missing:
        raise ValueError(f"Unknown node IDs: {sorted(missing)}")
    result = create_subgraph_from_nodes(
        network_id,
        sorted(selected),
        db,
        description=description,
        initialize_layout=False,
        reuse_existing=False,
    )
    # Legacy new_network_id triggers an automatic view switch in the backend.
    return {
        "created_network_id": result["new_network_id"],
        "source_network_id": network_id,
        "node_count": len(selected),
        "content": "Extracted. Select the network, calculate a layout, then render.",
    }
