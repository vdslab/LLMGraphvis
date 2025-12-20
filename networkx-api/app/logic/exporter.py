
import networkx as nx
from sqlalchemy.orm import Session

from app import models


def export_network_to_graphml(network_id: int, db: Session) -> str:
    """
    Reconstructs the network from the database and returns it as a GraphML string.
    """
    G = nx.Graph()

    # 1. Fetch Network Info (for consistency check, though largely unused in simple GraphML)
    network = db.query(models.Network).filter(models.Network.id == network_id).first()
    if not network:
        raise ValueError(f"Network {network_id} not found")

    # 2. Fetch Nodes & Attributes
    nodes = db.query(models.Node).filter(models.Node.network_id == network_id).all()

    # Fetch all node attributes for this network
    # We need to map: node_id -> {attr_name: value}
    # Efficient approach: Fetch all values and map them.

    # Map: db_id -> node_id_str
    node_db_id_map = {n.id: n.node_id for n in nodes}

    # Add nodes to graph first
    for n in nodes:
        G.add_node(n.node_id, label=n.label)

    # Fetch Attributes Definitions
    node_attr_defs = (
        db.query(models.NodeAttribute)
        .filter(models.NodeAttribute.network_id == network_id)
        .all()
    )
    node_attr_name_map = {a.id: a.attribute_name for a in node_attr_defs}

    if node_attr_defs:
        # Fetch Values
        # Join NodeAttributeValue with Node to filter by network? Or just filter by attribute IDs which are network-specific.
        attr_ids = [a.id for a in node_attr_defs]

        # We need to join with proper value tables
        # Queries for Float and Text values

        # Float Values
        float_values = (
            db.query(
                models.NodeAttributeValue.node_id,
                models.NodeAttributeValue.attribute_id,
                models.NodeFloatAttributeValue.float_value,
            )
            .join(models.NodeFloatAttributeValue)
            .filter(models.NodeAttributeValue.attribute_id.in_(attr_ids))
            .all()
        )

        for nid, aid, val in float_values:
            if nid in node_db_id_map and aid in node_attr_name_map:
                G.nodes[node_db_id_map[nid]][node_attr_name_map[aid]] = val

        # Text Values
        text_values = (
            db.query(
                models.NodeAttributeValue.node_id,
                models.NodeAttributeValue.attribute_id,
                models.NodeTextAttributeValue.text_value,
            )
            .join(models.NodeTextAttributeValue)
            .filter(models.NodeAttributeValue.attribute_id.in_(attr_ids))
            .all()
        )

        for nid, aid, val in text_values:
            if nid in node_db_id_map and aid in node_attr_name_map:
                G.nodes[node_db_id_map[nid]][node_attr_name_map[aid]] = val

    # 3. Fetch Edges & Attributes
    edges = db.query(models.Edge).filter(models.Edge.network_id == network_id).all()
    edge_db_id_map = {
        e.id: (node_db_id_map[e.source_node_id], node_db_id_map[e.target_node_id])
        for e in edges
        if e.source_node_id in node_db_id_map and e.target_node_id in node_db_id_map
    }

    for e in edges:
        if e.id in edge_db_id_map:
            u, v = edge_db_id_map[e.id]
            G.add_edge(u, v, weight=e.weight, id=e.edge_id)

    # Edge Attributes
    edge_attr_defs = (
        db.query(models.EdgeAttribute)
        .filter(models.EdgeAttribute.network_id == network_id)
        .all()
    )
    edge_attr_name_map = {a.id: a.attribute_name for a in edge_attr_defs}

    if edge_attr_defs:
        attr_ids = [a.id for a in edge_attr_defs]

        # Float Values
        float_values = (
            db.query(
                models.EdgeAttributeValue.edge_id,
                models.EdgeAttributeValue.attribute_id,
                models.EdgeFloatAttributeValue.float_value,
            )
            .join(models.EdgeFloatAttributeValue)
            .filter(models.EdgeAttributeValue.attribute_id.in_(attr_ids))
            .all()
        )

        for eid, aid, val in float_values:
            if eid in edge_db_id_map and aid in edge_attr_name_map:
                u, v = edge_db_id_map[eid]
                # NetworkX lookup for edges is (u, v)
                if G.has_edge(u, v):
                    G.edges[u, v][edge_attr_name_map[aid]] = val

        # Text Values
        text_values = (
            db.query(
                models.EdgeAttributeValue.edge_id,
                models.EdgeAttributeValue.attribute_id,
                models.EdgeTextAttributeValue.text_value,
            )
            .join(models.EdgeTextAttributeValue)
            .filter(models.EdgeAttributeValue.attribute_id.in_(attr_ids))
            .all()
        )

        for eid, aid, val in text_values:
            if eid in edge_db_id_map and aid in edge_attr_name_map:
                u, v = edge_db_id_map[eid]
                if G.has_edge(u, v):
                    G.edges[u, v][edge_attr_name_map[aid]] = val

    # 4. Generate GraphML
    # NetworkX generate_graphml returns an iterator of strings. We join them.
    return "".join(nx.generate_graphml(G))
