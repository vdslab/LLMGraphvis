from typing import Any, Dict, List

from sqlalchemy.orm import Session

from common import models


def update_network_metadata(
    db: Session, network_id: int, description: str = None, name: str = None
) -> str:
    """Updates the network's name or description."""
    network = db.query(models.Network).filter(models.Network.id == network_id).first()
    if not network:
        raise ValueError(f"Network {network_id} not found.")

    if description is not None:
        network.description = description
    if name is not None:
        network.name = name

    db.commit()
    return f"Network {network_id} metadata updated."


def get_network_metadata(db: Session, network_id: int) -> Dict[str, Any]:
    """Returns network metadata as a dictionary."""
    network = db.query(models.Network).filter(models.Network.id == network_id).first()
    if not network:
        raise ValueError(f"Network {network_id} not found")

    return {
        "id": network.id,
        "name": network.name,
        "description": network.description,
        "created_at": str(network.created_at),
        "visual_state": {
            "last_layout_name": network.last_layout_name,
            "last_node_size_config": network.last_node_size_config,
            "last_node_color_config": network.last_node_color_config,
            "last_edge_width_config": network.last_edge_width_config,
            "last_edge_color_config": network.last_edge_color_config,
            "last_node_label_config": network.last_node_label_config,
        },
    }


def get_network_structure(db: Session, network_id: int) -> Dict[str, Any]:
    """Returns basic structural statistics of the network."""
    node_count = (
        db.query(models.Node).filter(models.Node.network_id == network_id).count()
    )
    edge_count = (
        db.query(models.Edge).filter(models.Edge.network_id == network_id).count()
    )

    # Calculate density (approximate for undirected)
    density = 0
    if node_count > 1:
        possible_edges = node_count * (node_count - 1) / 2
        density = edge_count / possible_edges if possible_edges > 0 else 0

    return {
        "node_count": node_count,
        "edge_count": edge_count,
        "density": density,
        "is_directed": False,
    }


def get_subgraphs(db: Session, network_id: int) -> List[Dict[str, Any]]:
    """List all subgraphs created from the given parent network."""
    subgraphs = (
        db.query(models.Network)
        .filter(models.Network.parent_network_id == network_id)
        .all()
    )
    return [
        {"id": s.id, "name": s.name, "created_at": str(s.created_at)} for s in subgraphs
    ]
