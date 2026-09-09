import math
from typing import Any, Dict, List, Optional

import networkx as nx
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from common import models

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
    seed: Optional[int] = 42,
    endpoints: bool = False,
    wf_improved: bool = True,
    nstart: Optional[dict] = None,
    personalization: Optional[dict] = None,
    dangling: Optional[dict] = None,
):
    """Compute and persist one metric, keyed by its effective parameters.

    Weights are distances for betweenness/closeness and strengths for
    eigenvector/PageRank. Node distributions use exact string node IDs.
    NetworkX handles convergence; failures never create a successful cache entry.
    """
    attr_name = (
        "pagerank" if centrality_type == "pagerank" else f"{centrality_type}_centrality"
    )
    if weight == "none":
        weight = None

    # --- Cache check ---
    dependencies = (("Edge", weight),) if weight and weight != "none" else ()
    current_hash = compute_graph_state_hash(network_id, db, dependencies)

    # Build effective_params with only the entries meaningful for this
    # centrality_type, so the cache key stays minimal/stable per algorithm
    # (e.g. `k` is meaningless for "degree" and must not appear there).
    effective_params = {"centrality_type": centrality_type}
    if centrality_type == "pagerank":
        effective_params.update(
            {
                "damping_factor": damping_factor,
                "personalization": personalization,
                "dangling": dangling,
            }
        )
    if centrality_type in ("betweenness", "closeness", "eigenvector", "pagerank"):
        effective_params["weight"] = weight
    if centrality_type in ("degree", "in_degree", "out_degree", "betweenness"):
        effective_params["normalized"] = normalized
    if centrality_type in ("eigenvector", "pagerank"):
        effective_params["max_iter"] = max_iter
        effective_params["tol"] = tol
        effective_params["nstart"] = nstart
    if centrality_type == "betweenness":
        effective_params.update({"k": k, "seed": seed, "endpoints": endpoints})
    if centrality_type == "closeness":
        effective_params["wf_improved"] = wf_improved

    if not force:
        cached = get_cached_attribute(network_id, attr_name, models.NodeAttribute, db)
        if is_cache_valid(cached, current_hash, effective_params):
            logger.info(
                f"Centrality cache HIT for network {network_id}, "
                f"type='{centrality_type}' "
                f"(graph_state_hash={current_hash[:12]}...). Skipping recomputation."
            )
            return load_node_attribute_values(network_id, attr_name, db)

    logger.info(
        f"Centrality cache MISS for network {network_id}, "
        f"type='{centrality_type}'. Recomputing."
    )

    # Reconstruct graph (Optimized). Only ask for edge weights when a `weight`
    # attribute name was actually requested, so the default (fast) path is
    # unaffected when no weight is requested. Passing the name through means a
    # weight other than the imported `weight` column resolves to that edge
    # attribute instead of silently producing an unweighted graph.
    from .utils.graph_builder import build_graph_from_db

    G = build_graph_from_db(network_id, db, weight_attribute=weight)

    for name, vector in (
        ("nstart", nstart),
        ("personalization", personalization),
        ("dangling", dangling),
    ):
        if vector is None:
            continue
        unknown = set(vector) - set(G)
        if unknown:
            raise ValueError(f"{name} contains unknown node IDs: {sorted(unknown)}")
        if not vector or any(not math.isfinite(v) or v < 0 for v in vector.values()):
            raise ValueError(f"{name} requires finite nonnegative values")
        if sum(vector.values()) <= 0:
            raise ValueError(f"{name} requires a positive sum")
    if weight and centrality_type in {"betweenness", "closeness"}:
        if any(
            not math.isfinite(d[weight]) or d[weight] <= 0
            for _, _, d in G.edges(data=True)
        ):
            raise ValueError(
                "Distance weights for this centrality must be finite and positive"
            )

    # Need node_map for saving results later (node_id -> db_id)
    # We can fetch this efficiently or reconstruct it.
    # Since we need to map back to DB IDs for saving, let's fetch map.
    nodes = (
        db.query(models.Node.id, models.Node.node_id)
        .filter(models.Node.network_id == network_id)
        .all()
    )
    node_map = {n.node_id: n.id for n in nodes}

    # Calculate Centrality
    if centrality_type in ("degree", "in_degree", "out_degree"):
        functions = {
            "degree": nx.degree_centrality,
            "in_degree": nx.in_degree_centrality,
            "out_degree": nx.out_degree_centrality,
        }
        if normalized:
            centrality = functions[centrality_type](G)
        else:
            if centrality_type != "degree" and not G.is_directed():
                raise ValueError("In/out degree requires a directed graph")
            centrality = dict(getattr(G, centrality_type)())
    elif centrality_type == "betweenness":
        bc_kwargs: Dict[str, Any] = {
            "normalized": normalized,
            "endpoints": endpoints,
            "seed": seed,
        }
        if k is not None:
            bc_kwargs["k"] = k
        if weight is not None:
            bc_kwargs["weight"] = weight
        centrality = nx.betweenness_centrality(G, **bc_kwargs)
    elif centrality_type == "closeness":
        # NOTE: nx.closeness_centrality has no `normalized` kwarg at all (its
        # formula is inherently size-normalized). Its weight-equivalent kwarg
        # is named `distance`, not `weight`.
        cc_kwargs: Dict[str, Any] = {"wf_improved": wf_improved}
        if weight is not None:
            cc_kwargs["distance"] = weight
        centrality = nx.closeness_centrality(G, **cc_kwargs)
    elif centrality_type == "eigenvector":
        ev_kwargs: Dict[str, Any] = {
            "max_iter": max_iter if max_iter is not None else 1000
        }
        if tol is not None:
            ev_kwargs["tol"] = tol
        if weight is not None:
            ev_kwargs["weight"] = weight
        if nstart is not None:
            ev_kwargs["nstart"] = nstart
        centrality = nx.eigenvector_centrality(G, **ev_kwargs)
    elif centrality_type == "pagerank":
        centrality = nx.pagerank(
            G,
            alpha=damping_factor if damping_factor is not None else 0.85,
            personalization=personalization,
            dangling=dangling,
            nstart=nstart,
            weight=weight,
            max_iter=max_iter if max_iter is not None else 100,
            tol=tol if tol is not None else 1e-6,
        )
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
    Returns the top k nodes based on an already-computed numeric node attribute.

    `metric` is the exact saved attribute name (e.g. "degree_centrality",
    "pagerank", "clustering") as reported by the analysis tool that computed
    it — not the short internal centrality_type used by `calculate_centrality`.
    """
    values = load_node_attribute_values(network_id, metric, db)
    if not values:
        raise ValueError(
            f"Attribute '{metric}' has not been computed for network {network_id} yet. "
            "Run the relevant analysis tool first (e.g. analysis_degree_centrality, "
            "analysis_pagerank) and use its exact saved attribute name."
        )

    if k <= 0:
        raise ValueError(f"n must be a positive integer, got {k}")

    if order not in ("asc", "desc"):
        raise ValueError(f"order must be 'asc' or 'desc', got '{order}'")
    reverse = order == "desc"

    # Sort by score, skipping non-numeric values defensively (e.g. a text attribute
    # accidentally passed as `metric`).
    numeric_items = [
        (node_id, score)
        for node_id, score in values.items()
        if isinstance(score, (int, float))
    ]
    sorted_nodes = sorted(numeric_items, key=lambda item: item[1], reverse=reverse)

    # Take top k
    top_nodes = sorted_nodes[:k]

    return [{"node_id": node_id, "score": score} for node_id, score in top_nodes]
