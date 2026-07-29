from typing import Any, Dict, List, Optional, Type

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from common import models
from app.core.logging import get_logger

logger = get_logger(__name__)

# --- Attributes Helper Functions ---


def clear_network_data(network_id: int, db: Session) -> None:
    """
    Clears all graph data (nodes, edges, attribute values) for a network.
    Does NOT delete the Network record itself or Attribute Definitions (to preserve schema if reused).

    Args:
        network_id: The ID of the network to clear.
        db: Database session.
    """
    logger.info(f"Clearing network data for network_id={network_id}")

    # 1. Delete Edge Attribute Values (and their children)
    # Get all EdgeAttributeValue IDs for this network
    edge_attr_val_ids = [
        r[0]
        for r in db.query(models.EdgeAttributeValue.id)
        .join(models.Edge)
        .filter(models.Edge.network_id == network_id)
        .all()
    ]

    if edge_attr_val_ids:
        db.query(models.EdgeFloatAttributeValue).filter(
            models.EdgeFloatAttributeValue.edge_attribute_value_id.in_(
                edge_attr_val_ids
            )
        ).delete(synchronize_session=False)

        db.query(models.EdgeTextAttributeValue).filter(
            models.EdgeTextAttributeValue.edge_attribute_value_id.in_(edge_attr_val_ids)
        ).delete(synchronize_session=False)

        db.query(models.EdgeAttributeValue).filter(
            models.EdgeAttributeValue.id.in_(edge_attr_val_ids)
        ).delete(synchronize_session=False)

    # 2. Delete Node Attribute Values (and their children)
    # Get all NodeAttributeValue IDs
    node_attr_val_ids = [
        r[0]
        for r in db.query(models.NodeAttributeValue.id)
        .join(models.Node)
        .filter(models.Node.network_id == network_id)
        .all()
    ]

    if node_attr_val_ids:
        db.query(models.NodeFloatAttributeValue).filter(
            models.NodeFloatAttributeValue.node_attribute_value_id.in_(
                node_attr_val_ids
            )
        ).delete(synchronize_session=False)

        db.query(models.NodeTextAttributeValue).filter(
            models.NodeTextAttributeValue.node_attribute_value_id.in_(node_attr_val_ids)
        ).delete(synchronize_session=False)

        db.query(models.NodeAttributeValue).filter(
            models.NodeAttributeValue.id.in_(node_attr_val_ids)
        ).delete(synchronize_session=False)

    # 3. Delete Edges
    db.query(models.Edge).filter(models.Edge.network_id == network_id).delete(
        synchronize_session=False
    )

    # 4. Delete Nodes
    db.query(models.Node).filter(models.Node.network_id == network_id).delete(
        synchronize_session=False
    )

    db.commit()


def bulk_save_node_attributes(
    network_id: int,
    attr_name: str,
    attr_type: str,
    data_map: Dict[int, Any],  # db_node_id -> value
    db: Session,
):
    """
    Helper function to bulk save node attributes.
    Handles attribute creation, clearing old values, and bulk insertion.

    Args:
        network_id: The ID of the network.
        attr_name: Name of the attribute to save (e.g., "degree_centrality").
        attr_type: "float" or "string".
        data_map: Dictionary mapping internal DB node ID to the value.
        db: Database session.
    """
    # 1. Get or Create Attribute
    attr = get_or_create_attribute(
        network_id, attr_name, models.NodeAttribute, db, data_type=attr_type
    )

    # 2. Delete existing values
    delete_attribute_values(
        network_id, attr.id, models.NodeAttributeValue, db, commit=False
    )

    if not data_map:
        db.commit()
        return

    # 3. Bulk Insert Mappings (NodeAttributeValue), returning generated IDs directly
    #    instead of a separate round-trip SELECT to fetch them back.
    nav_data = [
        {"node_id": node_id, "attribute_id": attr.id} for node_id in data_map.keys()
    ]
    stmt = (
        insert(models.NodeAttributeValue)
        .values(nav_data)
        .returning(models.NodeAttributeValue.id, models.NodeAttributeValue.node_id)
    )
    result = db.execute(stmt)

    # Map db_node_id -> nav_id
    nav_map = {row.node_id: row.id for row in result}

    # 5. Bulk Insert Values (Float or Text)
    value_data = []
    
    if attr_type == "float":
        for node_id, value in data_map.items():
            nav_id = nav_map.get(node_id)
            if nav_id:
                value_data.append(
                    {"node_attribute_value_id": nav_id, "float_value": float(value)}
                )
        if value_data:
            db.bulk_insert_mappings(models.NodeFloatAttributeValue, value_data)

    elif attr_type == "string":
        for node_id, value in data_map.items():
            nav_id = nav_map.get(node_id)
            if nav_id:
                value_data.append(
                    {"node_attribute_value_id": nav_id, "text_value": str(value)}
                )
        if value_data:
            db.bulk_insert_mappings(models.NodeTextAttributeValue, value_data)
    
    db.commit()


def ensure_attributes(
    network_id: int,
    attr_types: Dict[str, str],
    model_class: Type[models.Base],
    db: Session,
    commit: bool = True,
    descriptions: Optional[Dict[str, str]] = None,
) -> Dict[str, int]:
    """
    Ensure attributes exist for the given keys and return a map of {name: id}.

    Args:
        network_id: The ID of the network.
        attr_types: Dict mapping attribute name to data_type ("float", "string", etc.).
        model_class: The SQLAlchemy model class for the attribute (NodeAttribute or EdgeAttribute).
        db: Database session.
        commit: Whether to commit the transaction.
        descriptions: Optional Dict mapping attribute name to description text.

    Returns:
        A dictionary mapping attribute names to their database IDs.
    """
    keys = set(attr_types.keys())
    if not keys:
        return {}

    # Step 1: Bulk Insert (Ignore duplicates)
    values = [
        {
            "network_id": network_id,
            "attribute_name": key,
            "data_type": attr_types.get(key, "string"),
            "description": descriptions.get(key) if descriptions else None,
        }
        for key in keys
    ]

    stmt = insert(model_class).values(values)

    # If conflict, updated description if provided to ensure it's captured
    update_dict = {}
    if descriptions:
        update_dict = {"description": stmt.excluded.description}

    if update_dict:
        stmt = stmt.on_conflict_do_update(
            index_elements=["network_id", "attribute_name"], set_=update_dict
        )
    else:
        stmt = stmt.on_conflict_do_nothing(
            index_elements=["network_id", "attribute_name"]
        )

    db.execute(stmt)

    # Avoid extra commits when the caller wraps operations in a transaction
    if commit:
        db.commit()
    else:
        db.flush()

    # Step 2: Fetch all IDs (now guaranteed to exist)
    all_attrs = (
        db.query(model_class)
        .filter(
            model_class.network_id == network_id, model_class.attribute_name.in_(keys)
        )
        .all()
    )

    return {attr.attribute_name: attr.id for attr in all_attrs}


def get_or_create_attribute(
    network_id: int,
    name: str,
    model_class: Type[models.Base],
    db: Session,
    data_type: str = "string",
    is_derived: Optional[bool] = None,
    derived_from: Optional[str] = None,
) -> models.Base:
    """
    Get an existing attribute or create a new one if it doesn't exist.

    Args:
        network_id: The ID of the network.
        name: The name of the attribute.
        model_class: The model class (NodeAttribute or EdgeAttribute).
        db: Database session.
        data_type: The data type of the attribute.
        is_derived: If provided, tags the attribute as derived/not-derived at creation
            time (only applied when the attribute is newly created; existing attributes
            are left untouched here — use `update_attribute_cache_metadata` to update
            provenance on an existing attribute).
        derived_from: Optional provenance string (e.g. "layout:forceatlas2") to store
            when the attribute is newly created.

    Returns:
        The attribute object.
    """
    attr = (
        db.query(model_class)
        .filter(
            model_class.network_id == network_id, model_class.attribute_name == name
        )
        .first()
    )

    if not attr:
        kwargs = dict(network_id=network_id, attribute_name=name, data_type=data_type)
        if is_derived is not None:
            kwargs["is_derived"] = is_derived
        if derived_from is not None:
            kwargs["derived_from"] = derived_from
        attr = model_class(**kwargs)
        db.add(attr)
        db.commit()
        db.refresh(attr)
    return attr


def get_cached_attribute(
    network_id: int, attr_name: str, model_class: Type[models.Base], db: Session
) -> Optional[models.Base]:
    """
    Returns the NodeAttribute/EdgeAttribute row if it exists, else None.
    Used to check cache validity before an expensive computation.
    """
    return (
        db.query(model_class)
        .filter(
            model_class.network_id == network_id,
            model_class.attribute_name == attr_name,
        )
        .first()
    )


def is_cache_valid(
    cached_attr: Optional[models.Base],
    current_hash: str,
    current_params: Optional[dict],
) -> bool:
    """
    True if the cached attribute's stored graph_state_hash and computation_params
    match the current graph state / params, meaning the cached values are still valid
    and recomputation can be skipped.
    """
    if cached_attr is None:
        return False
    if cached_attr.graph_state_hash != current_hash:
        return False
    # computation_params stored as JSON; compare as dicts (order-independent)
    return (cached_attr.computation_params or {}) == (current_params or {})


def update_attribute_cache_metadata(
    network_id: int,
    attr_name: str,
    model_class: Type[models.Base],
    db: Session,
    *,
    graph_state_hash: str,
    computation_params: Optional[dict],
    is_derived: bool = True,
    derived_from: Optional[str] = None,
) -> None:
    """
    Stamps cache metadata onto an existing NodeAttribute/EdgeAttribute row after
    (re)computation. Call AFTER bulk_save_node_attributes/bulk_save_edge_attributes,
    since that is what creates/refreshes the attribute row in the first place.
    """
    attr = get_cached_attribute(network_id, attr_name, model_class, db)
    if attr is None:
        return
    attr.graph_state_hash = graph_state_hash
    attr.computation_params = computation_params
    attr.is_derived = is_derived
    attr.derived_from = derived_from

    from datetime import datetime, timezone

    attr.computed_at = datetime.now(timezone.utc)
    db.commit()


def load_node_attribute_values(
    network_id: int, attr_name: str, db: Session
) -> Dict[str, Any]:
    """
    Loads existing computed values for a NodeAttribute back into a {node_id_str: value}
    dict, matching the shape that calculate_centrality currently returns, so a
    cache-hit path can return identically-shaped data to a cache-miss (freshly
    computed) path.

    Handles both float and text attribute value types. Uses the same bulk-join
    query pattern as `fetch_attribute_values` to avoid an N+1 lazy-load per row.
    """
    attr = (
        db.query(models.NodeAttribute)
        .filter(
            models.NodeAttribute.network_id == network_id,
            models.NodeAttribute.attribute_name == attr_name,
        )
        .first()
    )
    if attr is None:
        return {}

    node_id_map = {
        n.id: n.node_id
        for n in db.query(models.Node.id, models.Node.node_id)
        .filter(models.Node.network_id == network_id)
        .all()
    }

    result: Dict[str, Any] = {}

    q_float = (
        db.query(models.NodeAttributeValue.node_id, models.NodeFloatAttributeValue.float_value)
        .join(
            models.NodeFloatAttributeValue,
            models.NodeAttributeValue.id
            == models.NodeFloatAttributeValue.node_attribute_value_id,
        )
        .filter(models.NodeAttributeValue.attribute_id == attr.id)
        .all()
    )
    for node_pk, value in q_float:
        node_id_str = node_id_map.get(node_pk)
        if node_id_str is not None:
            result[node_id_str] = value

    q_text = (
        db.query(models.NodeAttributeValue.node_id, models.NodeTextAttributeValue.text_value)
        .join(
            models.NodeTextAttributeValue,
            models.NodeAttributeValue.id
            == models.NodeTextAttributeValue.node_attribute_value_id,
        )
        .filter(models.NodeAttributeValue.attribute_id == attr.id)
        .all()
    )
    for node_pk, value in q_text:
        node_id_str = node_id_map.get(node_pk)
        if node_id_str is not None:
            result[node_id_str] = value

    return result


def delete_attribute_values(
    network_id: int, attribute_id: int, model_val_class: Type[models.Base], db: Session, commit: bool = True
) -> None:
    """
    Delete all attribute values for a specific attribute in a network.

    Args:
        network_id: The ID of the network (unused currently but kept for potential future scoping).
        attribute_id: The ID of the attribute definition.
        model_val_class: The model class for values (NodeAttributeValue or EdgeAttributeValue).
        db: Database session.
        commit: Whether to commit the transaction (default: True).
    """
    # Delete children first (safe approach)
    # Find IDs to delete
    subquery = db.query(model_val_class.id).filter(
        model_val_class.attribute_id == attribute_id
    )

    # Delete Float/Text values
    if model_val_class == models.NodeAttributeValue:
        db.query(models.NodeFloatAttributeValue).filter(
            models.NodeFloatAttributeValue.node_attribute_value_id.in_(subquery)
        ).delete(synchronize_session=False)

        db.query(models.NodeTextAttributeValue).filter(
            models.NodeTextAttributeValue.node_attribute_value_id.in_(subquery)
        ).delete(synchronize_session=False)

    elif model_val_class == models.EdgeAttributeValue:
        db.query(models.EdgeFloatAttributeValue).filter(
            models.EdgeFloatAttributeValue.edge_attribute_value_id.in_(subquery)
        ).delete(synchronize_session=False)

        db.query(models.EdgeTextAttributeValue).filter(
            models.EdgeTextAttributeValue.edge_attribute_value_id.in_(subquery)
        ).delete(synchronize_session=False)

    # Delete parent values
    db.query(model_val_class).filter(
        model_val_class.attribute_id == attribute_id
    ).delete(synchronize_session=False)
    
    if commit:
        db.commit()


def get_attribute_stats(
    network_id: int,
    model_attr: Type[models.Base],
    model_val: Type[models.Base],
    model_float: Type[models.Base],
    model_text: Type[models.Base],
    db: Session,
) -> List[Dict[str, Any]]:
    """
    Fetch attributes with statistics to help LLM decide visualization types.

    Args:
        network_id: The ID of the network.
        model_attr: Attribute definition model (NodeAttribute/EdgeAttribute).
        model_val: Attribute value linking model (NodeAttributeValue/EdgeAttributeValue).
        model_float: Float value model.
        model_text: Text value model.
        db: Database session.

    Returns:
        List of dictionaries containing attribute metadata and statistics.
    """
    attributes = db.query(model_attr).filter(model_attr.network_id == network_id).all()
    result = []

    for attr in attributes:
        attr_data = {
            "name": attr.attribute_name,
            "data_type": attr.data_type,
            "description": attr.description,
        }

        try:
            if attr.data_type == "float":
                # Get Min/Max
                # Determine join condition based on model type
                if model_val == models.NodeAttributeValue:
                    join_cond = model_val.id == model_float.node_attribute_value_id
                else:
                    join_cond = model_val.id == model_float.edge_attribute_value_id

                stats = (
                    db.query(
                        func.min(model_float.float_value),
                        func.max(model_float.float_value),
                    )
                    .join(model_val, join_cond)
                    .filter(model_val.attribute_id == attr.id)
                    .first()
                )

                if stats and stats[0] is not None:
                    attr_data["stats"] = {
                        "min": float(stats[0]),
                        "max": float(stats[1]),
                    }

            elif attr.data_type == "string":
                # Get unique count and top values
                if model_val == models.NodeAttributeValue:
                    join_cond = model_val.id == model_text.node_attribute_value_id
                else:
                    join_cond = model_val.id == model_text.edge_attribute_value_id

                # Unique Count
                unique_count = (
                    db.query(func.count(func.distinct(model_text.text_value)))
                    .join(model_val, join_cond)
                    .filter(model_val.attribute_id == attr.id)
                    .scalar()
                )

                # Top 10 unique values
                top_values = (
                    db.query(
                        model_text.text_value,
                        func.count(model_text.text_value).label("count"),
                    )
                    .join(model_val, join_cond)
                    .filter(model_val.attribute_id == attr.id)
                    .group_by(model_text.text_value)
                    .order_by(func.count(model_text.text_value).desc())
                    .limit(10)
                    .all()
                )

                attr_data["stats"] = {
                    "unique_count": unique_count,
                    "top_values": [v[0] for v in top_values],
                }
        except Exception as e:
            # Fallback if calculation fails, just return name/type to avoid blocking response
            logger.error(
                f"Error calculating stats for {attr.attribute_name} in network {network_id}: {e}"
            )
            pass

        result.append(attr_data)

    # Inject Core Attributes (that are not in Attribute tables)
    if model_attr == models.EdgeAttribute:
        try:
            # Weight
            w_stats = (
                db.query(func.min(models.Edge.weight), func.max(models.Edge.weight))
                .filter(models.Edge.network_id == network_id)
                .first()
            )
            if w_stats and w_stats[0] is not None:
                result.append(
                    {
                        "name": "weight",
                        "data_type": "float",
                        "description": "Edge weight (core attribute)",
                        "stats": {"min": float(w_stats[0]), "max": float(w_stats[1])},
                    }
                )
        except Exception as e:
            logger.error(f"Error fetching weight stats: {e}")

    elif model_attr == models.NodeAttribute:
        try:
            # Label
            unique_count = (
                db.query(func.count(func.distinct(models.Node.label)))
                .filter(models.Node.network_id == network_id)
                .scalar()
            )
            # Top values
            top_vals = (
                db.query(models.Node.label, func.count(models.Node.label))
                .filter(models.Node.network_id == network_id)
                .group_by(models.Node.label)
                .order_by(func.count(models.Node.label).desc())
                .limit(10)
                .all()
            )

            result.append(
                {
                    "name": "label",
                    "data_type": "string",
                    "description": "Node label (core attribute)",
                    "stats": {
                        "unique_count": unique_count,
                        "top_values": [v[0] for v in top_vals],
                    },
                }
            )
        except Exception as e:
             logger.error(f"Error fetching label stats: {e}")

    return result


def get_specific_attribute_stats(
    network_id: int,
    attribute_name: str,
    model_attr: Type[models.Base],
    model_val: Type[models.Base],
    model_float: Type[models.Base],
    model_text: Type[models.Base],
    db: Session,
) -> Optional[Dict[str, Any]]:
    """
    Fetch statistics for a SINGLE specific attribute.
    """
    attr = (
        db.query(model_attr)
        .filter(
            model_attr.network_id == network_id,
            model_attr.attribute_name == attribute_name,
        )
        .first()
    )

    if not attr:
        return None

    attr_data = {
        "name": attr.attribute_name,
        "data_type": attr.data_type,
        "description": attr.description,
    }

    try:
        if attr.data_type == "float":
            if model_val == models.NodeAttributeValue:
                join_cond = model_val.id == model_float.node_attribute_value_id
            else:
                join_cond = model_val.id == model_float.edge_attribute_value_id

            stats = (
                db.query(
                    func.min(model_float.float_value), func.max(model_float.float_value)
                )
                .join(model_val, join_cond)
                .filter(model_val.attribute_id == attr.id)
                .first()
            )

            if stats and stats[0] is not None:
                attr_data["stats"] = {"min": float(stats[0]), "max": float(stats[1])}

        elif attr.data_type == "string":
            if model_val == models.NodeAttributeValue:
                join_cond = model_val.id == model_text.node_attribute_value_id
            else:
                join_cond = model_val.id == model_text.edge_attribute_value_id

            unique_count = (
                db.query(func.count(func.distinct(model_text.text_value)))
                .join(model_val, join_cond)
                .filter(model_val.attribute_id == attr.id)
                .scalar()
            )

            # For specific attribute text stats, we can return MORE top values (e.g. 20)
            top_values = (
                db.query(
                    model_text.text_value,
                    func.count(model_text.text_value).label("count"),
                )
                .join(model_val, join_cond)
                .filter(model_val.attribute_id == attr.id)
                .group_by(model_text.text_value)
                .order_by(func.count(model_text.text_value).desc())
                .limit(20)
                .all()
            )  # Higher limit for detailed inspection

            attr_data["stats"] = {
                "unique_count": unique_count,
                "top_values": [v[0] for v in top_values],
            }
    except Exception as e:
        logger.error(
            f"Error calculating stats for {attr.attribute_name} in network {network_id}: {e}"
        )
        pass

    return attr_data


def fetch_attribute_values(
    db: Session,
    model_val: Type[models.Base],
    model_float: Type[models.Base],
    model_text: Type[models.Base],
    attr_ids: List[int],
) -> Dict[int, Dict[int, Any]]:
    """
    Fetch values for specified attributes.

    Args:
        db: Database session.
        model_val: The attribute value model (NodeAttributeValue or EdgeAttributeValue).
        model_float: The float value model (NodeFloatAttributeValue or EdgeFloatAttributeValue).
        model_text: The text value model (NodeTextAttributeValue or EdgeTextAttributeValue).
        attr_ids: List of attribute IDs to fetch values for.

    Returns:
        A dictionary mapping entity_id (node_id or edge_id) to a dictionary of {attribute_id: value}.
        Example: {1: {10: 0.5, 11: "label"}}
    """
    if not attr_ids:
        return {}

    # Determine entity_id column based on model type
    if model_val == models.NodeAttributeValue:
        entity_id_col = model_val.node_id
        join_cond_float = model_val.id == model_float.node_attribute_value_id
        join_cond_text = model_val.id == model_text.node_attribute_value_id
    else:
        entity_id_col = model_val.edge_id
        join_cond_float = model_val.id == model_float.edge_attribute_value_id
        join_cond_text = model_val.id == model_text.edge_attribute_value_id

    q_float = (
        db.query(
            entity_id_col,
            model_val.attribute_id,
            model_float.float_value,
        )
        .join(model_float, join_cond_float)
        .filter(model_val.attribute_id.in_(attr_ids))
        .all()
    )

    q_text = (
        db.query(
            entity_id_col,
            model_val.attribute_id,
            model_text.text_value,
        )
        .join(model_text, join_cond_text)
        .filter(model_val.attribute_id.in_(attr_ids))
        .all()
    )

    result = {}
    for entity_id, attr_id, val in q_float:
        if entity_id not in result:
            result[entity_id] = {}
        result[entity_id][attr_id] = val

    for entity_id, attr_id, val in q_text:
        if entity_id not in result:
            result[entity_id] = {}
        result[entity_id][attr_id] = val

    return result
