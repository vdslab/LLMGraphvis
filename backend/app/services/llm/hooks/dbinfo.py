"""Read-only graph metadata lookups used by hooks.

Hooks need to answer "does this attribute exist?" and "how big is this graph?"
before a tool runs. Going through MCP for that would cost a round trip per
check, and both services share the same database (`common/models.py`), so these
read straight from Postgres.

Results are cached per (network_id) for the lifetime of a turn by the caller —
see `guards`/`normalize`, which stash them in `HookContext.turn_state`.
"""

from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import func

from app.core.logging import get_logger
from common import models

logger = get_logger(__name__)


def node_attribute_names(db: Any, network_id: int) -> List[str]:
    if not db or not network_id:
        return []
    rows = (
        db.query(models.NodeAttribute.attribute_name)
        .filter(models.NodeAttribute.network_id == network_id)
        .all()
    )
    return [r[0] for r in rows]


def edge_attribute_names(db: Any, network_id: int) -> List[str]:
    if not db or not network_id:
        return []
    rows = (
        db.query(models.EdgeAttribute.attribute_name)
        .filter(models.EdgeAttribute.network_id == network_id)
        .all()
    )
    return [r[0] for r in rows]


def graph_size(db: Any, network_id: int) -> Tuple[int, int]:
    """(node_count, edge_count). Returns (0, 0) when unknown.

    `networks` stores no denormalized counts, so this is two indexed COUNT(*)s.
    """
    if not db or not network_id:
        return (0, 0)
    try:
        nodes = (
            db.query(func.count(models.Node.id))
            .filter(models.Node.network_id == network_id)
            .scalar()
        ) or 0
        edges = (
            db.query(func.count(models.Edge.id))
            .filter(models.Edge.network_id == network_id)
            .scalar()
        ) or 0
        return (int(nodes), int(edges))
    except Exception as e:
        logger.warning(f"graph_size lookup failed for network {network_id}: {e}")
        return (0, 0)


# --- turn-scoped caching ---


def cached_attribute_names(
    turn_state: Dict[str, Any], db: Any, network_id: int, *, edges: bool = False
) -> List[str]:
    """Attribute names for a network, memoized for the current turn.

    A turn can make many attribute-taking calls; without this each one would
    re-query. Invalidation is not needed within a turn for the common case, but
    tools like `analysis_detect_communities` do create attributes mid-turn, so
    `invalidate_attributes()` is called from the POST_TOOL audit hook.
    """
    kind = "edge" if edges else "node"
    key = f"_attrs_{kind}_{network_id}"
    if key not in turn_state:
        turn_state[key] = (
            edge_attribute_names(db, network_id)
            if edges
            else node_attribute_names(db, network_id)
        )
    names: List[str] = turn_state[key]
    return names


def invalidate_attributes(
    turn_state: Dict[str, Any], network_id: Optional[int] = None
) -> None:
    """Drop memoized attribute lists after a tool that may have created one."""
    prefix = "_attrs_"
    suffix = f"_{network_id}" if network_id is not None else ""
    for key in [
        k
        for k in turn_state
        if k.startswith(prefix) and (not suffix or k.endswith(suffix))
    ]:
        turn_state.pop(key, None)


def cached_graph_size(
    turn_state: Dict[str, Any], db: Any, network_id: int
) -> Tuple[int, int]:
    key = f"_size_{network_id}"
    if key not in turn_state:
        turn_state[key] = graph_size(db, network_id)
    size: Tuple[int, int] = turn_state[key]
    return size
