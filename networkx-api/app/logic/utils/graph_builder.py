from typing import Any, Dict, Optional

import networkx as nx
from sqlalchemy import func
from sqlalchemy.orm import Session

from common import models
from app.core.logging import get_logger

logger = get_logger(__name__)

# Edge strength imported from the source file lives on the edges table itself
# (models.Edge.weight), not as an EdgeAttribute row — importer.py skips the
# `weight` key when it writes edge attributes. That is why a weighted network
# shows no `weight` in the edge-attribute listing, and why this name has to be
# special-cased everywhere weights are resolved.
WEIGHT_COLUMN = "weight"


def summarize_edge_weights(network_id: int, db: Session) -> Dict[str, Any]:
    """Describe a network's edge weights, and whether they are worth using.

    Weights only carry information when they vary: a graph whose edges all weigh
    the same lays out identically weighted or unweighted, so `is_informative` is
    False there and callers can take the cheaper unweighted path. Non-positive
    weights are reported as uninformative too — force-directed layouts read a
    weight as attraction strength, where zero or negative has no meaning.
    """
    total, non_null, distinct_count, min_w, max_w = (
        db.query(
            func.count(models.Edge.id),
            func.count(models.Edge.weight),
            func.count(func.distinct(models.Edge.weight)),
            func.min(models.Edge.weight),
            func.max(models.Edge.weight),
        )
        .filter(models.Edge.network_id == network_id)
        .one()
    )

    null_count = (total or 0) - (non_null or 0)
    # A NULL weight is read as 1.0 when the graph is built, so a mix of NULLs and
    # one distinct stored value is still uniform only if that value is 1.0.
    is_uniform = distinct_count == 0 or (
        min_w == max_w and (null_count == 0 or min_w == 1.0)
    )
    has_non_positive = min_w is not None and min_w <= 0

    summary: Dict[str, Any] = {
        "edge_count": total or 0,
        "weighted_edge_count": non_null or 0,
        "distinct_values": distinct_count or 0,
        "min": float(min_w) if min_w is not None else None,
        "max": float(max_w) if max_w is not None else None,
        "is_uniform": bool(is_uniform),
        "is_informative": bool(not is_uniform and not has_non_positive),
    }
    if is_uniform:
        summary["reason"] = "every edge carries the same weight"
    elif has_non_positive:
        summary["reason"] = f"weights include non-positive values (min {min_w})"
    return summary


def numeric_edge_attribute_names(network_id: int, db: Session) -> list:
    """Names of the network's numeric edge attributes, excluding the weight column."""
    rows = (
        db.query(models.EdgeAttribute.attribute_name)
        .filter(
            models.EdgeAttribute.network_id == network_id,
            models.EdgeAttribute.data_type == "float",
        )
        .all()
    )
    return [row.attribute_name for row in rows if row.attribute_name != WEIGHT_COLUMN]


def _load_edge_attribute_weights(
    network_id: int, attribute_name: str, db: Session
) -> Dict[int, float]:
    """Read a numeric edge attribute as `{edge_db_id: value}`.

    Raises ValueError rather than returning an empty mapping when the attribute
    does not exist or is not numeric: silently falling back to an unweighted
    graph is exactly the failure this whole path exists to prevent.
    """
    attr = (
        db.query(models.EdgeAttribute)
        .filter(
            models.EdgeAttribute.network_id == network_id,
            models.EdgeAttribute.attribute_name == attribute_name,
        )
        .first()
    )
    if attr is None:
        available = numeric_edge_attribute_names(network_id, db)
        usable = f"'{WEIGHT_COLUMN}' (the imported edge weight)"
        if available:
            usable += ", " + ", ".join(f"'{name}'" for name in available)
        raise ValueError(
            f"Network {network_id} has no edge attribute '{attribute_name}'. "
            f"Usable edge weights: {usable}."
        )

    rows = (
        db.query(
            models.EdgeAttributeValue.edge_id,
            models.EdgeFloatAttributeValue.float_value,
        )
        .join(
            models.EdgeFloatAttributeValue,
            models.EdgeAttributeValue.id
            == models.EdgeFloatAttributeValue.edge_attribute_value_id,
        )
        .filter(models.EdgeAttributeValue.attribute_id == attr.id)
        .all()
    )
    values = {
        row.edge_id: float(row.float_value)
        for row in rows
        if row.float_value is not None
    }
    if not values:
        raise ValueError(
            f"Edge attribute '{attribute_name}' holds no numeric values, so it "
            f"cannot be used as an edge weight."
        )
    return values


def build_graph_from_db(
    network_id: int, db: Session, weight_attribute: Optional[str] = None
) -> nx.Graph:
    """
    Reconstructs a NetworkX graph from the database for a given network_id.
    Optimized to fetch only necessary ID columns.

    Args:
        network_id: The ID of the network.
        db: Database session.
        weight_attribute: Name under which edge weights are attached to the
            graph, or None (default) for a graph with no weight attribute at
            all. `"weight"` reads `models.Edge.weight` (what the importer wrote,
            defaulting a NULL to 1.0); any other name reads that numeric edge
            attribute and raises if it does not exist. The attached attribute is
            named after this argument, so passing it straight through to a
            networkx `weight=` kwarg works. Leaving it None keeps the common
            (unweighted) path exactly as fast as it was.
    """
    G = nx.Graph()

    # Optimized Node Query: Fetch only id (pk) and node_id (string id)
    nodes_query = (
        db.query(models.Node.id, models.Node.node_id)
        .filter(models.Node.network_id == network_id)
        .all()
    )

    id_map = {row.id: row.node_id for row in nodes_query}  # db_id -> str_id

    for row in nodes_query:
        G.add_node(row.node_id)

    logger.info(
        f"GraphBuilder: Loaded {len(G.nodes)} nodes for Network {network_id}."
    )

    # Weights from an edge attribute are keyed by edge db id, so that column has
    # to come back from the edge query as well.
    attribute_weights = (
        _load_edge_attribute_weights(network_id, weight_attribute, db)
        if weight_attribute and weight_attribute != WEIGHT_COLUMN
        else None
    )

    # Optimized Edge Query: Fetch only source/target IDs (plus what weighting needs)
    columns = [models.Edge.source_node_id, models.Edge.target_node_id]
    if weight_attribute:
        columns.append(models.Edge.id)
        if attribute_weights is None:
            columns.append(models.Edge.weight)
    edges_query = (
        db.query(*columns).filter(models.Edge.network_id == network_id).all()
    )

    edge_count = 0
    for row in edges_query:
        u = id_map.get(row.source_node_id)
        v = id_map.get(row.target_node_id)
        if u and v:
            if weight_attribute:
                if attribute_weights is not None:
                    value = attribute_weights.get(row.id, 1.0)
                else:
                    value = row.weight if row.weight is not None else 1.0
                G.add_edge(u, v, **{weight_attribute: value})
            else:
                G.add_edge(u, v)
            edge_count += 1
        else:
            # This might happen if edges point to non-existent nodes
            # (shouldn't happen with FKs but good to be safe)
            pass

    logger.info(
        f"GraphBuilder: Loaded {edge_count} edges for Network {network_id}"
        + (f" weighted by '{weight_attribute}'." if weight_attribute else ".")
    )

    return G
