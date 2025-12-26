from typing import List, Set

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from common import models
from app.core.logging import get_logger
from app.logic.subgraph import create_subgraph_from_nodes
from app.schemas.filter import AttributeCondition

logger = get_logger(__name__)


def create_subgraph_by_filter(
    network_id: int,
    conditions: List[AttributeCondition],
    suffix: str,
    db: Session,
    preserve_layout: bool = False,
    description: str = None,
):
    """
    Creates a subgraph based on a list of attribute conditions.
    Conditions are combined with AND logic.
    Within a condition, ranges and categories are combined with OR logic.
    """
    logger.info(
        f"Filtering nodes in network {network_id} with {len(conditions)} conditions (preserve_layout={preserve_layout})"
    )

    # Start with all node IDs in the network
    all_query = db.query(models.Node.node_id).filter(
        models.Node.network_id == network_id
    )
    candidate_node_ids = set([res[0] for res in all_query.all()])

    if not candidate_node_ids:
        logger.warning(f"Network {network_id} has no nodes.")
        raise ValueError("Network has no nodes.")

    # Iterate through each condition and intersect the results (AND logic)
    for condition in conditions:
        matched_ids = _get_nodes_matching_condition(network_id, condition, db)
        candidate_node_ids &= matched_ids

        if not candidate_node_ids:
            logger.info("Filter resulted in 0 nodes.")
            break

    if not candidate_node_ids:
        raise ValueError("No nodes match the specified filter criteria.")

    if description is None:
        description = _generate_filter_description(conditions)

    return create_subgraph_from_nodes(
        network_id,
        list(candidate_node_ids),
        db,
        suffix=suffix,
        preserve_layout=preserve_layout,
        description=description,
    )


def _generate_filter_description(conditions: List[AttributeCondition]) -> str:
    """Generates a human-readable description from filter conditions."""
    desc_parts = []
    for cond in conditions:
        cond_parts = []
        if cond.categories:
            cats = ", ".join([f"'{c}'" for c in cond.categories])
            cond_parts.append(f"IN [{cats}]")

        if cond.ranges:
            for rng in cond.ranges:
                if rng.min is not None and rng.max is not None:
                    cond_parts.append(f"{rng.min} <= x <= {rng.max}")
                elif rng.min is not None:
                    cond_parts.append(f"x >= {rng.min}")
                elif rng.max is not None:
                    cond_parts.append(f"x <= {rng.max}")

        cond_str = " OR ".join(cond_parts)
        desc_parts.append(f"attribute '{cond.attribute_name}' ({cond_str})")

    return "Filtered by: " + " AND ".join(desc_parts)


def _get_nodes_matching_condition(
    network_id: int, condition: AttributeCondition, db: Session
) -> Set[str]:
    """
    Finds node IDs that match a single attribute condition.
    """
    attr_name = condition.attribute_name

    # 1. Find the Attribute ID
    attr_record = (
        db.query(models.NodeAttribute)
        .filter(
            models.NodeAttribute.network_id == network_id,
            models.NodeAttribute.attribute_name == attr_name,
        )
        .first()
    )

    if not attr_record:
        logger.warning(
            f"Attribute '{attr_name}' not found in network {network_id}. Treating as no match."
        )
        return set()

    attr_id = attr_record.id

    # 2. Build Query for Values
    # We join NodeAttributeValue with NodeTextAttributeValue and NodeFloatAttributeValue
    query = (
        db.query(models.Node.node_id)
        .join(
            models.NodeAttributeValue,
            models.Node.id == models.NodeAttributeValue.node_id,
        )
        .filter(models.NodeAttributeValue.attribute_id == attr_id)
    )

    # Collect filters for OR logic
    filters = []

    # Categories (Exact match)
    if condition.categories:
        for cat in condition.categories:
            if isinstance(cat, str):
                filters.append(
                    models.NodeAttributeValue.text_value.has(
                        models.NodeTextAttributeValue.text_value == cat
                    )
                )
            else:
                # Numeric categories (treat as float exact match)
                filters.append(
                    models.NodeAttributeValue.float_value.has(
                        models.NodeFloatAttributeValue.float_value == float(cat)
                    )
                )

    # Ranges (Numeric range)
    if condition.ranges:
        for rng in condition.ranges:
            range_filter = []
            if rng.min is not None:
                range_filter.append(
                    models.NodeFloatAttributeValue.float_value >= rng.min
                )
            if rng.max is not None:
                range_filter.append(
                    models.NodeFloatAttributeValue.float_value <= rng.max
                )

            if range_filter:
                filters.append(
                    models.NodeAttributeValue.float_value.has(and_(*range_filter))
                )

    if not filters:
        # If no specific ranges or categories provided, maybe just presence of attribute?
        # For now, if no criteria, return all nodes having this attribute.
        pass
    else:
        query = query.filter(or_(*filters))

    results = query.all()
    return set([res[0] for res in results])


def get_nodes_by_filter(
    network_id: int, conditions: List[AttributeCondition], db: Session
) -> List[dict]:
    """
    Returns a list of node details (id, label) that match the conditions.
    Does NOT create a subgraph, just lists them.
    """
    # Start with all node IDs in the network
    all_query = db.query(models.Node).filter(models.Node.network_id == network_id)
    
    # Use sets for intersection
    candidate_node_ids = set([node.node_id for node in all_query.all()])
    
    if not candidate_node_ids:
        return []

    for condition in conditions:
        matched_ids = _get_nodes_matching_condition(network_id, condition, db)
        candidate_node_ids &= matched_ids
        
        if not candidate_node_ids:
            return []
            
    # Fetch details for the remaining nodes
    final_nodes = (
        db.query(models.Node)
        .filter(
            models.Node.network_id == network_id,
            models.Node.node_id.in_(candidate_node_ids)
        )
        .all()
    )
    
    return [
        {"id": node.node_id, "label": node.label}
        for node in final_nodes
    ]
