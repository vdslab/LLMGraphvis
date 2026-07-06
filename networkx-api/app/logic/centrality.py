from typing import Any, Dict, List, Optional

import networkx as nx
from sqlalchemy.orm import Session

from common import models
from app.core.logging import get_logger

from .attributes import (
    bulk_save_node_attributes,
    get_cached_attribute,
    is_cache_valid,
    load_node_attribute_values,
    update_attribute_cache_metadata,
)
from .utils.cache import compute_graph_state_hash

logger = get_logger(__name__)


def calculate_centrality(
    network_id: int,
    centrality_type: str,
    db: Session,
    force: bool = False,
    damping_factor: Optional[float] = None,
    weight: Optional[str] = None,
    normalized: bool = True,
    max_iter: Optional[int] = None,
    tol: Optional[float] = None,
    k: Optional[int] = None,
):
    """
    Calculates a centrality metric for all nodes in the network.

    Args:
        network_id: The ID of the network.
        centrality_type: One of "degree", "betweenness", "closeness", "eigenvector", "pagerank".
        db: Database session.
        force: If True, bypasses the cache and always recomputes.
        damping_factor: PageRank-only. Alpha (damping) parameter, forwarded to
            `nx.pagerank(alpha=...)`. Defaults to networkx's own default (0.85)
            when None/omitted.
        weight: Name of the edge attribute to use as edge weight. Applies to
            "betweenness", "closeness" (forwarded as nx's `distance` kwarg),
            and "eigenvector". Not supported by "degree" (nx.degree_centrality
            has no weight concept) or "pagerank" (has its own weight handling,
            out of scope for this stage). When set, `build_graph_from_db` is
            asked to load edge weights onto the graph.
        normalized: Applies to "degree" (emulated manually — nx.degree_centrality
            has no `normalized` kwarg, so we scale by (n-1) ourselves when False)
            and "betweenness" (nx has a real `normalized` kwarg). NOTE:
            nx.closeness_centrality has no normalization toggle at all (its
            formula is inherently size-normalized), so this has no effect for
            "closeness" and is intentionally not read for that type.
        max_iter: Eigenvector-only. Defaults to 1000 (today's hardcoded value)
            when None.
        tol: Eigenvector-only. Defaults to networkx's own default (1e-06) when
            None (today's code doesn't pass `tol` at all, so this preserves
            that exact behavior).
        k: Betweenness-only. Approximate-sampling parameter forwarded to
            `nx.betweenness_centrality(k=...)`. None (default) computes exactly,
            same as before this parameter existed.
    """
    attr_name = f"{centrality_type}_centrality"

    # --- Cache check ---
    current_hash = compute_graph_state_hash(network_id, db)

    # Build effective_params with only the entries meaningful for this
    # centrality_type, so the cache key stays minimal/stable per algorithm
    # (e.g. `k` is meaningless for "degree" and must not appear there).
    effective_params = {"centrality_type": centrality_type}
    if centrality_type == "pagerank":
        effective_params["damping_factor"] = damping_factor
    if centrality_type in ("betweenness", "closeness", "eigenvector"):
        effective_params["weight"] = weight
    if centrality_type in ("degree", "betweenness"):
        effective_params["normalized"] = normalized
    if centrality_type == "eigenvector":
        effective_params["max_iter"] = max_iter
        effective_params["tol"] = tol
    if centrality_type == "betweenness":
        effective_params["k"] = k

    if not force:
        cached = get_cached_attribute(network_id, attr_name, models.NodeAttribute, db)
        if is_cache_valid(cached, current_hash, effective_params):
            logger.info(
                f"Centrality cache HIT for network {network_id}, type='{centrality_type}' "
                f"(graph_state_hash={current_hash[:12]}...). Skipping recomputation."
            )
            return load_node_attribute_values(network_id, attr_name, db)

    logger.info(
        f"Centrality cache MISS for network {network_id}, type='{centrality_type}'. Recomputing."
    )

    # Reconstruct graph (Optimized). Only ask for edge weights when a `weight`
    # attribute name was actually requested, so the default (fast) path is
    # unaffected when no weight is requested.
    from .utils.graph_builder import build_graph_from_db
    G = build_graph_from_db(network_id, db, include_weights=(weight is not None))

    # Need node_map for saving results later (node_id -> db_id)
    # We can fetch this efficiently or reconstruct it.
    # Since we need to map back to DB IDs for saving, let's fetch map.
    nodes = db.query(models.Node.id, models.Node.node_id).filter(models.Node.network_id == network_id).all()
    node_map = {n.node_id: n.id for n in nodes}

    # Calculate Centrality
    if centrality_type == "degree":
        # NOTE: nx.degree_centrality has no `normalized` kwarg (its formula is
        # always divided by (n-1)); we emulate an "unnormalized" (raw degree
        # count) mode manually when normalized=False, by scaling back up.
        centrality = nx.degree_centrality(G)
        if not normalized:
            n = len(G)
            if n > 1:
                centrality = {node: val * (n - 1) for node, val in centrality.items()}
    elif centrality_type == "betweenness":
        bc_kwargs: Dict[str, Any] = {"normalized": normalized}
        if k is not None:
            bc_kwargs["k"] = k
        if weight is not None:
            bc_kwargs["weight"] = weight
        centrality = nx.betweenness_centrality(G, **bc_kwargs)
    elif centrality_type == "closeness":
        # NOTE: nx.closeness_centrality has no `normalized` kwarg at all (its
        # formula is inherently size-normalized). Its weight-equivalent kwarg
        # is named `distance`, not `weight`.
        cc_kwargs: Dict[str, Any] = {}
        if weight is not None:
            cc_kwargs["distance"] = weight
        centrality = nx.closeness_centrality(G, **cc_kwargs)
    elif centrality_type == "eigenvector":
        ev_kwargs: Dict[str, Any] = {"max_iter": max_iter if max_iter is not None else 1000}
        if tol is not None:
            ev_kwargs["tol"] = tol
        if weight is not None:
            ev_kwargs["weight"] = weight
        centrality = nx.eigenvector_centrality(G, **ev_kwargs)
    elif centrality_type == "pagerank":
        centrality = nx.pagerank(G, alpha=damping_factor if damping_factor is not None else 0.85)
    else:
        raise ValueError(f"Unknown centrality type: {centrality_type}")

    # Prepare data for bulk save (db_node_id -> value)
    data_map = {}
    for node_id, score in centrality.items():
        if node_id in node_map:
            db_node_id = node_map[node_id]
            data_map[db_node_id] = score

    # Save to DB - Bulk Update Strategy
    bulk_save_node_attributes(network_id, attr_name, "float", data_map, db)

    update_attribute_cache_metadata(
        network_id,
        attr_name,
        models.NodeAttribute,
        db,
        graph_state_hash=current_hash,
        computation_params=effective_params,
        is_derived=True,
        derived_from=f"centrality:{centrality_type}",
    )

    return centrality


def get_top_nodes(
    network_id: int, metric: str, k: int, order: str, db: Session
) -> List[Dict[str, Any]]:
    """
    Returns the top k nodes based on the specified centrality metric.
    """
    # Calculate centrality (this also saves to DB, which is fine)
    # We reuse the existing logic.
    centrality = calculate_centrality(network_id, metric, db)

    # Determine reverse flag based on order
    reverse = True
    if order == "asc":
        reverse = False

    # Sort by score
    sorted_nodes = sorted(centrality.items(), key=lambda item: item[1], reverse=reverse)

    # Take top k
    top_nodes = sorted_nodes[:k]

    return [{"node_id": node_id, "score": score} for node_id, score in top_nodes]
