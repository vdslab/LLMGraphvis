import math

import networkx as nx
from sqlalchemy.orm import Session

from common import models

from .attributes import delete_attribute_values, get_or_create_attribute
from app.core.logging import get_logger

logger = get_logger(__name__)



def determine_layout_params(G, layout_name: str):
    """
    Dynamically determine layout parameters based on graph size (scale).
    Prioritizes 'Beautiful' high-quality layouts over speed.
    """
    num_nodes = len(G.nodes)
    params = {}
    
    # Scale Categories
    is_small = num_nodes < 500
    is_medium = 500 <= num_nodes < 2000
    is_large = num_nodes >= 2000

    if layout_name == "spring" or layout_name == "fruchterman_reingold":
        # k: Optimal distance between nodes. 
        # Increase slightly (2.0/sqrt(N)) to reduce overlap.
        k = 2.0 / math.sqrt(num_nodes) if num_nodes > 0 else None
        
        if is_small:
            # High iterations, strict threshold for beautiful convergence
            iterations = 1000
            threshold = 1e-6
        elif is_medium:
            iterations = 500
            threshold = 1e-5
        else: # Large
            iterations = 200
            threshold = 1e-4

        params = {
            "k": k,
            "iterations": iterations,
            "threshold": threshold,
            "seed": 42
        }

    elif layout_name == "forceatlas2":
        # Native NetworkX ForceAtlas2 optimization
        # Dynamic iterations based on graph size.
        # Each iteration is O(N^2) (dense pairwise force computation, no
        # Barnes-Hut approximation), so iteration count directly dominates
        # upload/layout latency for large graphs. Floor/cap kept well above
        # networkx's own default (100) for layout quality, but far below the
        # previous 1000-5000 range that made large uploads extremely slow.
        # Formula: max_iter = max(200, min(2000, num_nodes))
        max_iter = max(200, min(2000, num_nodes))

        # Dynamic Scaling Ratio for Overlap Reduction
        # Use Average Degree as a proxy for local density clumping
        num_edges = len(G.edges)
        avg_degree = (2 * num_edges) / num_nodes if num_nodes > 0 else 0
        
        # If avg_degree is high, nodes are pulled tighter. We increase scaling to compensate.
        # Base scaling is 2.0. Cap at 10.0.
        # Formula: scaling_ratio = max(2.0, min(10.0, avg_degree * 0.5))
        scaling_ratio = max(2.0, min(10.0, avg_degree * 0.5))

        # Force Constants
        params = {
            "max_iter": max_iter,
            "scaling_ratio": scaling_ratio, 
            "gravity": 1.0,        # Standard gravity
            "jitter_tolerance": 1.0, # Standard tolerance for better convergence
            "seed": 42
        }

    elif layout_name == "kamada_kawai":
        # O(N^2) but excellent global structure
        params = {"scale": 1.0} # Standard
        
    return params


# Per-layout allowlist of override keys accepted for the geometric layouts
# (Step 6). Keeps the override-merge generic while ensuring a parameter that
# a given networkx layout function doesn't actually support (e.g. `scale` on
# `random_layout`, which has no such kwarg) never leaks through and blows up
# the nx call, and never gets silently ignored after being advertised either
# (see force_directed/geometric tool layer, which only exposes params that
# are in these sets).
GEOMETRIC_OVERRIDE_KEYS = {
    "circular": {"scale", "center"},
    "shell": {"scale", "center", "nlist"},
    "spiral": {"scale", "center"},
    # NOTE: nx.random_layout(G, center=None, dim=2, seed=None) has no `scale`
    # parameter, unlike the other three geometric layouts.
    "random": {"center"},
}


def calculate_layout(
    network_id: int,
    layout_name: str,
    db: Session,
    overrides: dict = None,
    force: bool = False,
):
    # Normalize layout name up front (needed for both cache-check and compute paths)
    if layout_name in ["forceatlas2_layout", "force-directed", "force_directed"]:
        layout_name = "forceatlas2"

    # Reconstruct graph from DB
    from .utils.graph_builder import build_graph_from_db
    G = build_graph_from_db(network_id, db)

    # Need node_map for saving results (str_id -> db_id)
    nodes_query = db.query(models.Node.id, models.Node.node_id).filter(models.Node.network_id == network_id).all()
    node_map = {row.node_id: row.id for row in nodes_query}

    num_nodes = len(G.nodes)
    params = determine_layout_params(G, layout_name)

    # Merge caller-supplied overrides on top of the auto-computed params.
    # `None` values in `overrides` mean "use the auto-default" and are filtered
    # out; anything else wins. Tuple values (e.g. `center=(x, y)`) are converted
    # to lists so the resulting dict is JSON-serializable — this same dict is
    # reused below as (part of) `effective_params`/`computation_params`, and a
    # tuple would silently become a list on DB round-trip, causing a spurious
    # cache-miss on the very next call if we stored the tuple form.
    sanitized_overrides = {
        k: (list(v) if isinstance(v, tuple) else v)
        for k, v in (overrides or {}).items()
        if v is not None
    }

    if layout_name in GEOMETRIC_OVERRIDE_KEYS:
        # circular / shell / spiral / random: params starts empty (these
        # layouts have no auto-computed params today), so only accept the
        # override keys each specific nx layout function actually supports.
        allowed = GEOMETRIC_OVERRIDE_KEYS[layout_name]
        params.update({k: v for k, v in sanitized_overrides.items() if k in allowed})
    else:
        # spring / forceatlas2 / kamada_kawai: the tool layer only ever builds
        # an `overrides` dict containing keys relevant to the layout it calls,
        # so a direct merge on top of the auto-computed params is sufficient.
        params.update(sanitized_overrides)

    # --- Cache check ---
    from .utils.cache import compute_graph_state_hash
    from .attributes import get_cached_attribute, is_cache_valid

    current_hash = compute_graph_state_hash(network_id, db)
    effective_params = {"layout_name": layout_name, **params}

    if not force:
        cached_x = get_cached_attribute(
            network_id, f"{layout_name}_x", models.NodeAttribute, db
        )
        if is_cache_valid(cached_x, current_hash, effective_params):
            logger.info(
                f"Layout cache HIT for network {network_id}, layout='{layout_name}' "
                f"(graph_state_hash={current_hash[:12]}...). Skipping recomputation."
            )
            return

    logger.info(
        f"Layout cache MISS for network {network_id}, layout='{layout_name}'. Recomputing."
    )

    pos = None

    if layout_name == "spring" or layout_name == "fruchterman_reingold":
        pos = nx.spring_layout(G, **params)

    elif layout_name == "forceatlas2":
        # Use native NetworkX implementation
        # Note: Checked availability in NetworkX 3.6+
        pos = nx.forceatlas2_layout(G, **params)

    elif layout_name == "circular" or layout_name == "circle":
        pos = nx.circular_layout(G, **params)

    elif layout_name == "kamada_kawai":
        pos = nx.kamada_kawai_layout(G, **params)

    elif layout_name == "shell":
        pos = nx.shell_layout(G, **params)

    elif layout_name == "spectral":
        pos = nx.spectral_layout(G)

    elif layout_name == "spiral":
        pos = nx.spiral_layout(G, **params)

    elif layout_name == "random":
        pos = nx.random_layout(G, seed=42, **params)

    else:
        raise ValueError(f"Unknown layout algorithm: {layout_name}")

    # Save to DB - Bulk Update Strategy
    # We save two attributes: {layout_name}_x and {layout_name}_y
    
    # Prepare data maps
    data_map_x = {}
    data_map_y = {}

    for node_id, (x, y) in pos.items():
        if node_id in node_map:
            db_node_id = node_map[node_id]
            data_map_x[db_node_id] = float(x)
            data_map_y[db_node_id] = float(y)

    from .attributes import bulk_save_node_attributes, update_attribute_cache_metadata

    # Save X
    bulk_save_node_attributes(
        network_id, f"{layout_name}_x", "float", data_map_x, db
    )

    # Save Y
    bulk_save_node_attributes(
        network_id, f"{layout_name}_y", "float", data_map_y, db
    )

    # Stamp cache metadata on both x/y attributes so future calls can detect a cache hit
    derived_from = f"layout:{layout_name}"
    update_attribute_cache_metadata(
        network_id,
        f"{layout_name}_x",
        models.NodeAttribute,
        db,
        graph_state_hash=current_hash,
        computation_params=effective_params,
        is_derived=True,
        derived_from=derived_from,
    )
    update_attribute_cache_metadata(
        network_id,
        f"{layout_name}_y",
        models.NodeAttribute,
        db,
        graph_state_hash=current_hash,
        computation_params=effective_params,
        is_derived=True,
        derived_from=derived_from,
    )

    # 4. Update Network Record with last layout name
    from sqlalchemy import text

    try:
        db.execute(
            text("UPDATE networks SET last_layout_name = :algo WHERE id = :nid"),
            {"algo": layout_name, "nid": network_id},
        )
        db.commit()
    except Exception as e:
        db.rollback()
        logger.warning(f"Failed to update last_layout_name: {e}")
        # non-critical, proceed
