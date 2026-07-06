from typing import Any, Dict, List, Optional

import networkx as nx
from sqlalchemy.orm import Session

from common import models
from app.core.logging import get_logger

from .attributes import (
    bulk_save_node_attributes,
    get_cached_attribute,
    is_cache_valid,
    update_attribute_cache_metadata,
)
from .utils.cache import compute_graph_state_hash

logger = get_logger(__name__)


def calculate_community(
    network_id: int,
    algorithm: str,
    db: Session,
    force: bool = False,
    resolution: Optional[float] = None,
    seed: Optional[int] = None,
    best_n: Optional[int] = None,
) -> str:
    """
    Calculates communities for the network and saves them as a categorical node attribute.

    Args:
        network_id: The ID of the network.
        algorithm: "louvain", "greedy_modularity", "label_propagation"
        db: Database session.
        force: If True, bypasses the cache and always recomputes.
        resolution: Louvain-only. Higher resolution favors smaller communities.
            Forwarded to `nx.community.louvain_communities(resolution=...)`.
            Ignored (with a debug log) for other algorithms rather than raising,
            since it's simply not meaningful for them. Defaults to networkx's
            own default (1) when None.
        seed: Louvain-only. Forwarded to `nx.community.louvain_communities(seed=...)`
            for reproducible results. Not supported by "label_propagation"
            (networkx's label_propagation_communities has no seed parameter —
            it is inherently non-deterministic) or "greedy_modularity" (which
            uses `best_n` instead, see below). Ignored (with a debug log) if
            passed for those algorithms.
        best_n: Greedy-modularity-only. Forwarded to
            `nx.community.greedy_modularity_communities(best_n=...)` to force
            a specific number of communities. Ignored (with a debug log) for
            other algorithms.

    Returns:
        The name of the attribute created (e.g., "louvain_community").
    """
    attr_name = f"{algorithm}_community"

    # --- Cache check ---
    current_hash = compute_graph_state_hash(network_id, db)

    # Build effective_params with only the entries meaningful for this
    # algorithm, to keep the cache key minimal/stable per algorithm (e.g.
    # `best_n` must not appear in the cache key for "louvain" calls).
    effective_params = {"algorithm": algorithm}
    if algorithm == "louvain":
        effective_params["resolution"] = resolution
        effective_params["seed"] = seed
    elif algorithm == "greedy_modularity":
        effective_params["best_n"] = best_n
    # "label_propagation" (and any unknown algorithm) needs no extra params;
    # unknown algorithms fall through to the ValueError raised further below.

    if resolution is not None and algorithm != "louvain":
        logger.debug(
            f"calculate_community: 'resolution' param is not applicable to "
            f"algorithm='{algorithm}' and will be ignored."
        )
    if seed is not None and algorithm != "louvain":
        logger.debug(
            f"calculate_community: 'seed' param is not applicable to "
            f"algorithm='{algorithm}' and will be ignored."
        )
    if best_n is not None and algorithm != "greedy_modularity":
        logger.debug(
            f"calculate_community: 'best_n' param is not applicable to "
            f"algorithm='{algorithm}' and will be ignored."
        )

    if not force:
        cached = get_cached_attribute(network_id, attr_name, models.NodeAttribute, db)
        if is_cache_valid(cached, current_hash, effective_params):
            logger.info(
                f"Community cache HIT for network {network_id}, algorithm='{algorithm}' "
                f"(graph_state_hash={current_hash[:12]}...). Skipping recomputation."
            )
            return attr_name

    logger.info(
        f"Community cache MISS for network {network_id}, algorithm='{algorithm}'. Recomputing."
    )

    # Reconstruct graph
    G = nx.Graph()
    nodes = db.query(models.Node).filter(models.Node.network_id == network_id).all()
    # Map internal ID -> database ID
    id_map = {n.id: n.node_id for n in nodes}
    # Map database ID -> internal ID (for saving)
    node_map = {n.node_id: n.id for n in nodes}

    for n in nodes:
        G.add_node(n.node_id)

    edges = db.query(models.Edge).filter(models.Edge.network_id == network_id).all()
    for e in edges:
        u = id_map.get(e.source_node_id)
        v = id_map.get(e.target_node_id)
        if u and v:
            G.add_edge(u, v)

    # Detect Communities
    # Returns list of sets of nodes, e.g. [{n1, n2}, {n3, n4}]
    partition = []
    
    if algorithm == "louvain":
        # nx.community.louvain_communities returns list of sets.
        # Only thread resolution/seed into the actual louvain call — never
        # into the greedy_modularity fallback below, which may not accept
        # them the same way (and greedy_modularity has its own `best_n` knob
        # that's simply not relevant to a louvain request).
        louvain_kwargs: Dict[str, Any] = {}
        if resolution is not None:
            louvain_kwargs["resolution"] = resolution
        if seed is not None:
            louvain_kwargs["seed"] = seed
        try:
             partition = nx.community.louvain_communities(G, **louvain_kwargs)
        except AttributeError:
             # Fallback for older NetworkX versions or if not available
             partition = nx.community.greedy_modularity_communities(G)
    elif algorithm == "greedy_modularity":
        gm_kwargs: Dict[str, Any] = {}
        if best_n is not None:
            gm_kwargs["best_n"] = best_n
        partition = nx.community.greedy_modularity_communities(G, **gm_kwargs)
    elif algorithm == "label_propagation":
        partition = nx.community.label_propagation_communities(G)
    else:
        raise ValueError(f"Unknown community algorithm: {algorithm}")

    # Prepare data for bulk insert
    # db_node_id -> community_id (string)
    data_map = {}
    
    for i, community_nodes in enumerate(partition):
        cluster_id = str(i)
        for node_id in community_nodes:
            if node_id in node_map:
                db_node_id = node_map[node_id]
                data_map[db_node_id] = cluster_id

    # Save to DB
    bulk_save_node_attributes(network_id, attr_name, "string", data_map, db)

    update_attribute_cache_metadata(
        network_id,
        attr_name,
        models.NodeAttribute,
        db,
        graph_state_hash=current_hash,
        computation_params=effective_params,
        is_derived=True,
        derived_from=f"community:{algorithm}",
    )

    return attr_name
