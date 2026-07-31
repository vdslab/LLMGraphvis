import json
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

    elif layout_name == "arf":
        # ARF is iterative like spring; the nx defaults are reasonable, but
        # max_iter scales with graph size the same way spring's does.
        params = {"max_iter": 1000 if is_small else (500 if is_medium else 200)}

    return params


# Per-layout allowlist of parameter names that may reach the networkx call.
#
# This exists so a parameter a given nx layout function does NOT accept can
# never leak through and raise TypeError (e.g. `scale` on `random_layout`,
# which has no such kwarg), and so a parameter we advertise is never silently
# dropped either. Every layout is listed: the tool layer only exposes what is
# in these sets, and anything not listed for a layout is filtered out here.
#
# Keys are verified against the installed networkx (3.6.x) signatures in
# networkx/drawing/layout.py. `dim` and `store_pos_as` are deliberately
# excluded everywhere: this system is strictly 2D and manages its own attribute
# names ({layout}_x / {layout}_y).
LAYOUT_PARAM_KEYS = {
    "spring": {
        "k", "pos", "fixed", "iterations", "threshold", "weight",
        "scale", "center", "seed", "method", "gravity",
    },
    "forceatlas2": {
        "pos", "max_iter", "jitter_tolerance", "scaling_ratio", "gravity",
        "distributed_action", "strong_gravity", "node_mass", "node_size",
        "weight", "linlog", "seed",
    },
    "kamada_kawai": {"dist", "pos", "weight", "scale", "center"},
    "spectral": {"weight", "scale", "center"},
    "arf": {"pos", "scaling", "a", "etol", "dt", "max_iter", "seed"},
    "circular": {"scale", "center"},
    "shell": {"nlist", "rotate", "scale", "center"},
    "spiral": {"scale", "center", "resolution", "equidistant"},
    # NOTE: nx.random_layout(G, center=None, dim=2, seed=None) has no `scale`
    # parameter, unlike the other three geometric layouts.
    "random": {"center", "seed"},
    "bipartite": {"nodes", "align", "scale", "center", "aspect_ratio"},
    "multipartite": {"subset_key", "align", "scale", "center"},
    "planar": {"scale", "center"},
    "bfs": {"start", "align", "scale", "center"},
}

# Kept as an alias so any external caller of the previous name keeps working.
GEOMETRIC_OVERRIDE_KEYS = {
    name: LAYOUT_PARAM_KEYS[name] for name in ("circular", "shell", "spiral", "random")
}

# Layouts whose result depends on edge weights. build_graph_from_db() attaches
# no weight attribute unless asked, which means nx's own default of
# weight="weight" silently degrades to unweighted — so the graph has to be
# rebuilt with weights for the parameter to mean anything at all.
WEIGHT_AWARE_LAYOUTS = {"spring", "forceatlas2", "kamada_kawai", "spectral"}

# Of those, the ones that are weighted BY DEFAULT whenever the network carries
# informative weights (see summarize_edge_weights). All three read `weight` as
# connection strength, so using it is what a weighted file already means; making
# it opt-in threw that data away on every layout nobody thought to configure.
#
# kamada_kawai is deliberately excluded: its `weight` is the desired *distance*
# between two endpoints, so defaulting it on would push strongly connected nodes
# further apart — the opposite of what a weight normally means here. It stays
# opt-in, and _resolve_weight says so when the network has weights.
WEIGHT_AUTO_LAYOUTS = {"spring", "forceatlas2", "spectral"}

# Values of `weight` that mean "lay this graph out unweighted", overriding the
# automatic default. Now that weighted is the default, this is the only way for
# a caller to ask for the unweighted result.
WEIGHT_OPT_OUT = {"", "none", "no", "off", "false", "unweighted"}

# Parameters that can hold one entry per node. Replaced by a digest before being
# stored as cache metadata — see the cache_params construction below.
BULKY_PARAM_KEYS = {"pos", "nodes", "node_mass", "node_size", "dist", "fixed", "nlist"}


def _digest_param(value):
    """Short, stable fingerprint of a bulky parameter value.

    Rounds floats before hashing so a coordinate dict that survived a float ->
    JSON -> float round trip still compares equal, which would otherwise cause a
    spurious cache miss on every warm-started call.
    """
    import hashlib

    def canonical(v):
        if isinstance(v, float):
            return round(v, 9)
        if isinstance(v, dict):
            return {str(k): canonical(val) for k, val in sorted(v.items(), key=lambda kv: str(kv[0]))}
        if isinstance(v, (list, tuple)):
            return [canonical(item) for item in v]
        return v

    try:
        payload = json.dumps(canonical(value), sort_keys=True, default=str)
    except (TypeError, ValueError):
        payload = repr(value)
    return f"digest:{hashlib.sha256(payload.encode('utf-8')).hexdigest()[:16]}"


def load_layout_positions(network_id: int, layout_name: str, db: Session) -> dict:
    """Read a previously computed layout's coordinates as `{node_id: (x, y)}`.

    Used to warm-start an iterative layout from an existing one. Coordinates
    live as the float node attributes `{layout_name}_x` / `{layout_name}_y`
    (see the save path at the bottom of calculate_layout).
    """
    from sqlalchemy import text

    rows = db.execute(
        text(
            """
            SELECT n.node_id,
                   MAX(CASE WHEN a.attribute_name = :x_attr THEN f.float_value END) AS x,
                   MAX(CASE WHEN a.attribute_name = :y_attr THEN f.float_value END) AS y
              FROM nodes n
              JOIN node_attribute_values v ON v.node_id = n.id
              JOIN node_attributes a ON a.id = v.attribute_id
              JOIN node_float_attribute_values f ON f.node_attribute_value_id = v.id
             WHERE n.network_id = :nid
               AND a.network_id = :nid
               AND a.attribute_name IN (:x_attr, :y_attr)
             GROUP BY n.node_id
            """
        ),
        {
            "nid": network_id,
            "x_attr": f"{layout_name}_x",
            "y_attr": f"{layout_name}_y",
        },
    ).all()

    return {
        row.node_id: (float(row.x), float(row.y))
        for row in rows
        if row.x is not None and row.y is not None
    }


def _resolve_partition_params(
    G, network_id: int, layout_name: str, overrides: dict, db: Session
) -> None:
    """Turn attribute-based partition arguments into what networkx expects.

    Mutates `overrides` in place:
    - bipartite: `partition_attribute` (+ optional `partition_value`) -> `nodes`,
      the list of nodes forming one side.
    - multipartite: `subset_attribute` -> the attribute is attached to the graph's
      nodes and `subset_key` is set to its name.
    """
    from .attributes import load_node_attribute_values

    partition_attr = overrides.pop("partition_attribute", None)
    partition_value = overrides.pop("partition_value", None)
    subset_attr = overrides.pop("subset_attribute", None)

    if layout_name == "bipartite":
        if overrides.get("nodes"):
            return
        if not partition_attr:
            raise ValueError(
                "layout_bipartite needs either `partition_attribute` (the node "
                "attribute that splits the graph into two sides) or an explicit "
                "`nodes` list."
            )
        values = load_node_attribute_values(network_id, partition_attr, db)
        if not values:
            raise ValueError(
                f"Node attribute '{partition_attr}' has no values on network "
                f"{network_id}."
            )
        distinct = sorted({str(v) for v in values.values()})
        if partition_value is None:
            if len(distinct) != 2:
                raise ValueError(
                    f"'{partition_attr}' has {len(distinct)} distinct values "
                    f"({', '.join(distinct[:5])}...), so it does not define two sides. "
                    f"Pass `partition_value` to choose which value forms one side, or "
                    f"use layout_multipartite for more than two groups."
                )
            partition_value = distinct[0]

        side = [n for n in G.nodes if str(values.get(n)) == str(partition_value)]
        if not side or len(side) == len(G.nodes):
            raise ValueError(
                f"No usable split: '{partition_attr}' == '{partition_value}' selects "
                f"{len(side)} of {len(G.nodes)} nodes. One side would be empty."
            )
        overrides["nodes"] = side
        return

    if layout_name == "multipartite":
        if overrides.get("subset_key"):
            return
        if not subset_attr:
            raise ValueError(
                "layout_multipartite needs `subset_attribute`: the node attribute "
                "whose distinct values define the layers."
            )
        values = load_node_attribute_values(network_id, subset_attr, db)
        if not values:
            raise ValueError(
                f"Node attribute '{subset_attr}' has no values on network {network_id}."
            )
        missing = [n for n in G.nodes if n not in values]
        if missing:
            # nx raises an opaque KeyError if any node lacks the subset key.
            raise ValueError(
                f"{len(missing)} of {len(G.nodes)} nodes have no '{subset_attr}' value, "
                f"so they cannot be assigned to a layer. Use an attribute that every "
                f"node has, or extract a subgraph where it is fully populated."
            )
        for node in G.nodes:
            G.nodes[node][subset_attr] = values[node]
        overrides["subset_key"] = subset_attr


def _resolve_weight(layout_name: str, requested, network_id: int, db: Session):
    """Decide which edge attribute, if any, this layout should be weighted by.

    Returns `(weight_attribute, note)`. `note` is a sentence for the tool's
    return message: a caller that never asked for weights still has to be told
    they were used, otherwise "weighted by default" is just another silent
    behaviour — the mirror image of the bug this replaces.
    """
    from .utils.graph_builder import WEIGHT_COLUMN, summarize_edge_weights

    if layout_name not in WEIGHT_AWARE_LAYOUTS:
        return None, ""

    if isinstance(requested, str) and requested.strip().lower() in WEIGHT_OPT_OUT:
        return None, "Edge weights were ignored, as requested."

    if requested:
        return requested, f"Weighted by the '{requested}' edge attribute."

    summary = summarize_edge_weights(network_id, db)
    if not summary["is_informative"]:
        return None, ""

    span = f"{summary['min']:.3g}–{summary['max']:.3g}"
    if layout_name not in WEIGHT_AUTO_LAYOUTS:
        # kamada_kawai: weights mean distance here, so the choice is the user's.
        return None, (
            f"Note: this network has edge weights (range {span}), which this layout "
            f"would read as target distances (heavier = further apart). It was "
            f"computed unweighted; pass weight='weight' to use them as distances."
        )

    logger.info(
        f"Layout '{layout_name}' on network {network_id}: using imported edge "
        f"weights automatically (range {span}, "
        f"{summary['distinct_values']} distinct values)."
    )
    return WEIGHT_COLUMN, (
        f"Edge weights were used automatically (range {span}); "
        f"pass weight='none' for an unweighted layout."
    )


def format_layout_result(info, headline: str, follow_up: str = "") -> str:
    """Assemble a layout tool's return message, including any weight note."""
    note = (info or {}).get("weight_note") or ""
    return " ".join(part for part in (headline, note, follow_up) if part)


def calculate_layout(
    network_id: int,
    layout_name: str,
    db: Session,
    overrides: dict = None,
    force: bool = False,
) -> dict:
    # Normalize layout name up front (needed for both cache-check and compute paths)
    if layout_name in ["forceatlas2_layout", "force-directed", "force_directed"]:
        layout_name = "forceatlas2"
    elif layout_name in ["fruchterman_reingold"]:
        layout_name = "spring"
    elif layout_name in ["circle"]:
        layout_name = "circular"

    raw_overrides = overrides or {}

    # Resolve weighting before anything else: it decides how the graph is built.
    # Doing it here rather than in the tool layer means every entry point — the
    # upload pipeline, subgraph extraction, the REST endpoint, the MCP tools —
    # gets the same weighted-by-default behaviour.
    weight_attribute, weight_note = _resolve_weight(
        layout_name, raw_overrides.get("weight"), network_id, db
    )

    # Reconstruct graph from DB
    from .utils.graph_builder import build_graph_from_db
    G = build_graph_from_db(network_id, db, weight_attribute=weight_attribute)

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
        for k, v in raw_overrides.items()
        if v is not None
    }

    # `weight` is no longer whatever the caller passed — it is what
    # _resolve_weight decided, which is also the attribute name now present on
    # the graph. Both the nx call and the cache key have to see the resolved
    # value, or a weighted run would happily reuse an unweighted cached layout.
    if weight_attribute:
        sanitized_overrides["weight"] = weight_attribute
    else:
        sanitized_overrides.pop("weight", None)

    # `init_from_layout` is ours, not networkx's: it names a previously computed
    # layout whose stored coordinates become the starting positions. Resolved to
    # nx's `pos` here and removed so it never reaches the nx call. Warm-starting
    # by name (rather than by a literal coordinate dict) is what makes this
    # usable from a tool call — no caller can hand over 5000 pairs of floats.
    init_from = sanitized_overrides.pop("init_from_layout", None)
    if init_from:
        if "pos" not in LAYOUT_PARAM_KEYS.get(layout_name, set()):
            raise ValueError(
                f"Layout '{layout_name}' cannot be warm-started; "
                f"init_from_layout is only supported for "
                f"{sorted(n for n, keys in LAYOUT_PARAM_KEYS.items() if 'pos' in keys)}."
            )
        start_pos = load_layout_positions(network_id, init_from, db)
        if not start_pos:
            raise ValueError(
                f"No stored '{init_from}' layout for network {network_id}. "
                f"Compute that layout first, or omit init_from_layout."
            )
        sanitized_overrides["pos"] = start_pos

    # Partition-based layouts key off a node attribute, but build_graph_from_db
    # loads no attributes onto the graph — so the attribute has to be fetched and
    # attached here before networkx can see it. `partition_attribute` /
    # `partition_value` / `subset_attribute` are ours; nx sees `nodes` /
    # `subset_key`.
    _resolve_partition_params(G, network_id, layout_name, sanitized_overrides, db)

    # Filter to the parameters this specific nx layout function accepts, so an
    # unsupported kwarg can never raise TypeError inside networkx and an
    # advertised one can never be silently discarded.
    allowed = LAYOUT_PARAM_KEYS.get(layout_name)
    if allowed is not None:
        rejected = set(sanitized_overrides) - allowed
        if rejected:
            logger.warning(
                f"Ignoring parameters not supported by layout '{layout_name}': "
                f"{sorted(rejected)}"
            )
        params.update({k: v for k, v in sanitized_overrides.items() if k in allowed})
    else:
        params.update(sanitized_overrides)

    # --- Cache check ---
    from .utils.cache import compute_graph_state_hash
    from .attributes import get_cached_attribute, is_cache_valid

    current_hash = compute_graph_state_hash(network_id, db)
    # Several parameters can hold one entry per node (`pos`, `nodes`, `node_mass`,
    # `node_size`, `dist`, `fixed`). Storing them verbatim would bloat
    # computation_params and make every cache comparison walk the whole graph, so
    # they are reduced to a digest — which still changes when their contents
    # change, keeping cache invalidation correct.
    cache_params = {
        k: (_digest_param(v) if k in BULKY_PARAM_KEYS else v)
        for k, v in params.items()
    }
    if init_from:
        cache_params["init_from_layout"] = init_from
    effective_params = {"layout_name": layout_name, **cache_params}

    result = {
        "layout_name": layout_name,
        "weight": weight_attribute,
        "weight_note": weight_note,
    }

    if not force:
        cached_x = get_cached_attribute(
            network_id, f"{layout_name}_x", models.NodeAttribute, db
        )
        if is_cache_valid(cached_x, current_hash, effective_params):
            logger.info(
                f"Layout cache HIT for network {network_id}, layout='{layout_name}' "
                f"(graph_state_hash={current_hash[:12]}...). Skipping recomputation."
            )
            return {**result, "cached": True}

    logger.info(
        f"Layout cache MISS for network {network_id}, layout='{layout_name}'. Recomputing."
    )

    pos = None

    if layout_name == "spring":
        pos = nx.spring_layout(G, **params)

    elif layout_name == "forceatlas2":
        # Use native NetworkX implementation
        # Note: Checked availability in NetworkX 3.6+
        pos = nx.forceatlas2_layout(G, **params)

    elif layout_name == "circular":
        pos = nx.circular_layout(G, **params)

    elif layout_name == "kamada_kawai":
        pos = nx.kamada_kawai_layout(G, **params)

    elif layout_name == "shell":
        pos = nx.shell_layout(G, **params)

    elif layout_name == "spectral":
        # NOTE: params were previously dropped here, so `weight`, `scale` and
        # `center` had no effect whatsoever on a spectral layout.
        pos = nx.spectral_layout(G, **params)

    elif layout_name == "spiral":
        pos = nx.spiral_layout(G, **params)

    elif layout_name == "random":
        # `seed` used to be hardcoded here, which also made passing it as an
        # override raise TypeError for a duplicate keyword argument. It is now
        # an ordinary parameter defaulted below.
        pos = nx.random_layout(G, **{"seed": 42, **params})

    elif layout_name == "arf":
        pos = nx.arf_layout(G, **params)

    elif layout_name == "bipartite":
        pos = nx.bipartite_layout(G, **params)

    elif layout_name == "multipartite":
        pos = nx.multipartite_layout(G, **params)

    elif layout_name == "planar":
        try:
            pos = nx.planar_layout(G, **params)
        except nx.NetworkXException as e:
            # nx raises for non-planar input. Most real graphs are non-planar, so
            # this is the expected failure rather than an exceptional one, and it
            # deserves a message that says what to do instead.
            raise ValueError(
                "This graph is not planar, so it cannot be drawn without edge "
                "crossings. Use a force-directed layout (forceatlas2 or spring) "
                f"instead. (networkx: {e})"
            ) from e

    elif layout_name == "bfs":
        pos = nx.bfs_layout(G, **params)

    else:
        raise ValueError(
            f"Unknown layout algorithm: {layout_name}. "
            f"Supported: {', '.join(sorted(LAYOUT_PARAM_KEYS))}."
        )

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

    return {**result, "cached": False}
