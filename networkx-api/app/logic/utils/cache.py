import hashlib
import json

from sqlalchemy import or_
from sqlalchemy.orm import Session

from common import models


def compute_graph_state_hash(
    network_id: int, db: Session, dependencies: tuple[tuple[str, str], ...] = ()
) -> str:
    """Hash topology, direction, and imported attributes for calculation caches.

    Derived results are excluded unless explicitly consumed as dependencies.
    """
    nodes = sorted(
        r.node_id
        for r in db.query(models.Node.node_id).filter(
            models.Node.network_id == network_id
        )
    )

    # Build id_map (db pk -> node_id string) for edges
    id_map = {
        r.id: r.node_id
        for r in db.query(models.Node.id, models.Node.node_id).filter(
            models.Node.network_id == network_id
        )
    }

    edges = sorted(
        (e.id, id_map[e.source_node_id], id_map[e.target_node_id], e.weight)
        for e in db.query(models.Edge)
        .filter(models.Edge.network_id == network_id)
        .all()
        if e.source_node_id in id_map and e.target_node_id in id_map
    )

    network = db.get(models.Network, network_id)
    payload = {
        "directed": bool(network and network.is_directed),
        "nodes": nodes,
        "edges": edges,
        "source_attributes": _source_attribute_values(network_id, db, dependencies),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _source_attribute_values(network_id: int, db: Session, dependencies) -> list:
    """Fingerprint imported values used as weights, partitions, or constraints.

    Derived metrics and layout coordinates are excluded: saving a calculation
    must not invalidate that calculation's own cache.
    """
    result = []
    for scope in ("Node", "Edge"):
        attribute = getattr(models, f"{scope}Attribute")
        value = getattr(models, f"{scope}AttributeValue")
        owner_id = getattr(value, f"{scope.lower()}_id")
        for value_type, column_name in (
            ("Float", "float_value"),
            ("Text", "text_value"),
        ):
            typed = getattr(models, f"{scope}{value_type}AttributeValue")
            link = getattr(typed, f"{scope.lower()}_attribute_value_id")
            rows = (
                db.query(
                    attribute.attribute_name, owner_id, getattr(typed, column_name)
                )
                .select_from(value)
                .join(attribute, value.attribute_id == attribute.id)
                .join(typed, link == value.id)
                .filter(
                    attribute.network_id == network_id,
                    or_(
                        attribute.is_derived.is_not(True),
                        attribute.attribute_name.in_(
                            [name for owner, name in dependencies if owner == scope]
                        ),
                    ),
                )
                .order_by(attribute.attribute_name, owner_id)
                .all()
            )
            result.extend((scope, value_type, *row) for row in rows)
    return result
