"""Layout orchestration: build the graph, run one layout, cache and store it.

This module is deliberately layout-agnostic — it does not branch on a layout
name anywhere. Everything specific to an algorithm (its networkx call, its
parameters, their auto-tuning, what a weight means to it, any preparation it
needs) is declared with that layout in `logic/layouts/`.
"""

import json

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from common import models

from .layouts import get_spec, layout_names, param_keys, resolve_weight

logger = get_logger(__name__)

# The per-layout parameter allowlist, derived from the registry. Kept under its
# old name because it is the thing tests and docs refer to when explaining why a
# parameter did or did not reach networkx.
LAYOUT_PARAM_KEYS = param_keys()

# Parameters that can hold one entry per node. Replaced by a digest before being
# stored as cache metadata — see the cache_params construction below.
BULKY_PARAM_KEYS = {"pos", "nodes", "node_mass", "node_size", "dist", "fixed", "nlist"}


def determine_layout_params(G, layout_name: str) -> dict:
    """The size-derived defaults for a layout, or {} if it has none.

    Thin wrapper over the registry; the tuning itself lives with each layout.
    """
    spec = get_spec(layout_name)
    return spec.tune(G) if spec.tune else {}


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
            return {
                str(k): canonical(val)
                for k, val in sorted(v.items(), key=lambda kv: str(kv[0]))
            }
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
                   MAX(CASE WHEN a.attribute_name = :x_attr
                            THEN f.float_value END) AS x,
                   MAX(CASE WHEN a.attribute_name = :y_attr
                            THEN f.float_value END) AS y
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


def _resolve_warm_start(spec, network_id: int, overrides: dict, db: Session):
    """Turn our `init_from_layout` into networkx's `pos`, and return its name.

    Warm-starting by layout name (rather than by a literal coordinate dict) is
    what makes this usable from a tool call — no caller can hand over 5000 pairs
    of floats.
    """
    init_from = overrides.pop("init_from_layout", None)
    if not init_from:
        return None

    if not spec.supports_warm_start:
        raise ValueError(
            f"Layout '{spec.name}' cannot be warm-started; init_from_layout is "
            f"only supported for "
            f"{sorted(n for n, keys in LAYOUT_PARAM_KEYS.items() if 'pos' in keys)}."
        )

    start_pos = load_layout_positions(network_id, init_from, db)
    if not start_pos:
        raise ValueError(
            f"No stored '{init_from}' layout for network {network_id}. "
            f"Compute that layout first, or omit init_from_layout."
        )
    overrides["pos"] = start_pos
    return init_from


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
    """Compute one layout and store its coordinates as node attributes.

    Returns a summary of what was actually done — which weight was used, whether
    the cache answered — for the tool layer to report back to the model.
    """
    spec = get_spec(layout_name)  # resolves aliases; raises on an unknown name
    layout_name = spec.name
    raw_overrides = overrides or {}

    # Weighting is resolved first because it decides how the graph is built.
    # Doing it here rather than in the tool layer means every entry point — the
    # upload pipeline, subgraph extraction, the REST endpoint, the MCP tools —
    # gets the same behaviour.
    weight_attribute, weight_note = resolve_weight(
        spec, raw_overrides.get("weight"), network_id, db
    )

    from .utils.graph_builder import build_graph_from_db
    G = build_graph_from_db(network_id, db, weight_attribute=weight_attribute)

    # Need node_map for saving results (str_id -> db_id)
    nodes_query = (
        db.query(models.Node.id, models.Node.node_id)
        .filter(models.Node.network_id == network_id)
        .all()
    )
    node_map = {row.node_id: row.id for row in nodes_query}

    params = spec.tune(G) if spec.tune else {}

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
    # resolve_weight decided, which is also the attribute name now present on the
    # graph. Both the nx call and the cache key have to see the resolved value,
    # or a weighted run would happily reuse an unweighted cached layout.
    if weight_attribute:
        sanitized_overrides["weight"] = weight_attribute
    else:
        sanitized_overrides.pop("weight", None)

    init_from = _resolve_warm_start(spec, network_id, sanitized_overrides, db)

    # Layouts that key off a node attribute translate it into what networkx
    # expects here (see each layout's `prepare` in logic/layouts/structural.py).
    if spec.prepare:
        spec.prepare(G, network_id, sanitized_overrides, db)

    # Filter to the parameters this specific nx layout function accepts, so an
    # unsupported kwarg can never raise TypeError inside networkx and an
    # advertised one can never be silently discarded.
    rejected = set(sanitized_overrides) - spec.params
    if rejected:
        logger.warning(
            f"Ignoring parameters not supported by layout '{layout_name}': "
            f"{sorted(rejected)}"
        )
    params.update(
        {k: v for k, v in sanitized_overrides.items() if k in spec.params}
    )

    # --- Cache check ---
    from .attributes import get_cached_attribute, is_cache_valid
    from .utils.cache import compute_graph_state_hash

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
        f"Layout cache MISS for network {network_id}, "
        f"layout='{layout_name}'. Recomputing."
    )

    pos = spec.compute(G, params)

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


__all__ = [
    "LAYOUT_PARAM_KEYS",
    "calculate_layout",
    "determine_layout_params",
    "format_layout_result",
    "layout_names",
    "load_layout_positions",
]
