import hashlib

from sqlalchemy.orm import Session

from common import models


def compute_graph_state_hash(network_id: int, db: Session) -> str:
    """
    Computes a stable hash of a network's topology (node IDs + edge source/target/weight),
    used to detect whether cached computation results (layout/centrality/community) are
    still valid. Any change to nodes or edges (add/remove/reweight) changes this hash.
    """
    nodes = sorted(
        r.node_id
        for r in db.query(models.Node.node_id).filter(
            models.Node.network_id == network_id
        )
    )

    # Build id_map (db pk -> node_id string) for edges
    id_map = {
        r.id: r.node_id
        for r in db.query(models.Node.id, models.Node.node_id).filter(
            models.Node.network_id == network_id
        )
    }

    edges = sorted(
        (id_map[e.source_node_id], id_map[e.target_node_id], e.weight)
        for e in db.query(models.Edge).filter(models.Edge.network_id == network_id).all()
        if e.source_node_id in id_map and e.target_node_id in id_map
    )

    payload = "|".join(nodes) + "##" + "|".join(f"{u},{v},{w}" for u, v, w in edges)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
