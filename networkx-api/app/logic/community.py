from typing import Optional

import networkx as nx
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from common import models

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
    weight: Optional[str] = None,
    cutoff: Optional[int] = None,
    threshold: Optional[float] = None,
    max_level: Optional[int] = None,
) -> str:
    """Persist one partition; accepted options are shared by execution and cache.

    Algorithms have distinct contracts. Invalid combinations are rejected instead
    of being ignored, and a missing implementation never changes the algorithm.
    """
    algorithms = {
        "louvain": (
            nx.community.louvain_communities,
            {"weight", "resolution", "seed", "threshold", "max_level"},
        ),
        "greedy_modularity": (
            nx.community.greedy_modularity_communities,
            {"weight", "resolution", "cutoff", "best_n"},
        ),
        "label_propagation": (nx.community.label_propagation_communities, set()),
    }
    if algorithm not in algorithms:
        raise ValueError(f"Unknown community algorithm: {algorithm}")
    function, allowed = algorithms[algorithm]
    supplied = {
        "resolution": resolution,
        "seed": seed,
        "best_n": best_n,
        "weight": weight,
        "cutoff": cutoff,
        "threshold": threshold,
        "max_level": max_level,
    }
    parameters = {key: value for key, value in supplied.items() if value is not None}
    unsupported = set(parameters) - allowed
    if unsupported:
        raise ValueError(
            f"Unsupported parameters for {algorithm}: {sorted(unsupported)}"
        )
    if "weight" in allowed:
        parameters["weight"] = None if weight == "none" else weight
    attr_name = f"{algorithm}_community"
    dependencies = (("Edge", weight),) if weight and weight != "none" else ()
    current_hash = compute_graph_state_hash(network_id, db, dependencies)
    effective_params = {"algorithm": algorithm, **parameters}

    if not force:
        cached = get_cached_attribute(network_id, attr_name, models.NodeAttribute, db)
        if is_cache_valid(cached, current_hash, effective_params):
            logger.info(
                f"Community cache HIT for network {network_id}, "
                f"algorithm='{algorithm}' "
                f"(graph_state_hash={current_hash[:12]}...). Skipping recomputation."
            )
            return attr_name

    logger.info(
        f"Community cache MISS for network {network_id}, "
        f"algorithm='{algorithm}'. Recomputing."
    )

    from .utils.graph_builder import build_graph_from_db

    G = build_graph_from_db(network_id, db, weight_attribute=parameters.get("weight"))
    nodes = db.query(models.Node).filter(models.Node.network_id == network_id).all()
    node_map = {node.node_id: node.id for node in nodes}

    partition = function(G, **parameters)

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
