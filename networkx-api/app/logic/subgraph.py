from typing import Any, Dict, List

import networkx as nx
from sqlalchemy.orm import Session

from app import models
from app.core.logging import get_logger

from .layout import calculate_layout
from .utils.attribute_copier import AttributeCopier
from .utils.node_utils import resolve_node_id

logger = get_logger(__name__)

# Standard set of topological attributes to exclude by default
# These depend on the graph structure, so they become "stale" in a subgraph.
TOPOLOGICAL_ATTRIBUTES = [
    "degree",
    "in_degree",
    "out_degree",
    "betweenness",
    "closeness",
    "eigenvector",
    "pagerank",
    "modularity_class",
    "x",
    "y",  # Layout depends on topology too
]


def create_subgraph_from_nodes(
    source_network_id: int,
    node_ids: List[str],
    db: Session,
    suffix: str = "Subgraph",
    preserve_layout: bool = False,
    description: str = None,
) -> Dict[str, Any]:
    """
    Creates a new network as a subgraph containing the specified nodes.

    Args:
        preserve_layout (bool):
            If True, copies 'x' and 'y' attributes to keep node positions ("Cutout View").
            If False, excludes 'x' and 'y', forcing a new layout calculation ("Fresh View").

            NOTE: Topological metrics (degree, centrality, etc.) are ALWAYS excluded to ensure correctness.
    """
    logger.info(
        f"Creating subgraph from network {source_network_id} with {len(node_ids)} nodes (suffix='{suffix}', preserve_layout={preserve_layout})"
    )

    # 1. Get Source Network
    source_network = (
        db.query(models.Network).filter(models.Network.id == source_network_id).first()
    )
    if not source_network:
        logger.error(f"Source network {source_network_id} not found")
        raise ValueError(f"Source network {source_network_id} not found")

    # 2. Determine Network Name & Check Existing
    target_name = _determine_subgraph_name(node_ids, suffix)
    existing_network = (
        db.query(models.Network)
        .filter(
            models.Network.parent_network_id == source_network_id,
            models.Network.name == target_name,
        )
        .first()
    )

    if existing_network:
        logger.info(
            f"Returning existing subgraph: {existing_network.id} ({target_name})"
        )
        return {"new_network_id": existing_network.id, "name": existing_network.name}

    # 3. Create New Network
    new_network = models.Network(
        name=target_name, parent_network_id=source_network_id, description=description
    )
    db.add(new_network)
    db.commit()
    db.refresh(new_network)
    new_network_id = new_network.id
    logger.info(f"Created new network ID: {new_network_id}")

    # 4. Copy Nodes
    node_map = _copy_nodes(db, source_network_id, new_network_id, node_ids)
    logger.debug(f"Copied {len(node_map)} nodes")

    # 5. Copy Edges (Induced Subgraph)
    edge_map = _copy_edges(db, source_network_id, new_network_id, node_map)
    logger.debug(f"Copied {len(edge_map)} edges")

    # 6. Copy Attributes Schema & Values
    # Define exclusion list based on whether layout should be preserved
    excluded_attrs = list(TOPOLOGICAL_ATTRIBUTES)

    if preserve_layout:
        # If preserving layout, we DO want x and y, so remove them from exclusion list
        if "x" in excluded_attrs:
            excluded_attrs.remove("x")
        if "y" in excluded_attrs:
            excluded_attrs.remove("y")

    copier = AttributeCopier(db)
    copier.copy_attributes(
        source_network_id,
        new_network_id,
        node_map,
        edge_map,
        excluded_attributes=excluded_attrs,
    )

    # 7. Calculate Initial Layout (only if NOT preserved)
    if not preserve_layout:
        logger.info("Calculating initial layout (spring)...")
        calculate_layout(new_network_id, "spring", db)
    else:
        logger.info("Preserving existing layout (x, y copied).")

    return {"new_network_id": new_network_id, "name": new_network.name}


# --- High Level Helpers ---


def _determine_subgraph_name(node_ids: List[str], suffix: str) -> str:
    if suffix == "Subgraph":
        # Create a deterministic name for ad-hoc subgraphs based on node IDs
        sorted_ids = sorted(node_ids)
        nodes_str = ",".join(sorted_ids)
        if len(nodes_str) > 50:
            nodes_str = nodes_str[:47] + "..."
        return f"Subgraph ({nodes_str})"
    return suffix


def _copy_nodes(
    db: Session, source_network_id: int, new_network_id: int, node_ids: List[str]
) -> Dict[int, int]:
    """
    Copies nodes from source to new network. Returns map of old_pk -> new_pk.
    """
    source_nodes = (
        db.query(models.Node)
        .filter(
            models.Node.network_id == source_network_id,
            models.Node.node_id.in_(node_ids),
        )
        .all()
    )

    node_map = {}  # old_pk -> new_pk

    new_nodes_data = []
    for node in source_nodes:
        new_nodes_data.append(
            {"network_id": new_network_id, "node_id": node.node_id, "label": node.label}
        )

    if new_nodes_data:
        db.bulk_insert_mappings(models.Node, new_nodes_data)
        db.commit()

        # Build maps
        new_nodes = (
            db.query(models.Node).filter(models.Node.network_id == new_network_id).all()
        )
        # We need to map old source nodes to new nodes.
        source_node_map = {n.node_id: n.id for n in source_nodes}
        for new_node in new_nodes:
            old_pk = source_node_map.get(new_node.node_id)
            if old_pk:
                node_map[old_pk] = new_node.id

    return node_map


def _copy_edges(
    db: Session, source_network_id: int, new_network_id: int, node_map: Dict[int, int]
) -> Dict[int, int]:
    """
    Copies edges where both source and target are in node_map. Returns map of old_pk -> new_pk.
    """
    source_edges = (
        db.query(models.Edge)
        .filter(
            models.Edge.network_id == source_network_id,
            models.Edge.source_node_id.in_(node_map.keys()),
            models.Edge.target_node_id.in_(node_map.keys()),
        )
        .all()
    )

    edge_map = {}  # old_pk -> new_pk
    new_edges_data = []
    for edge in source_edges:
        new_edges_data.append(
            {
                "network_id": new_network_id,
                "edge_id": edge.edge_id,
                "source_node_id": node_map[edge.source_node_id],
                "target_node_id": node_map[edge.target_node_id],
                "weight": edge.weight,
            }
        )

    if new_edges_data:
        db.bulk_insert_mappings(models.Edge, new_edges_data)
        db.commit()

        new_edges = (
            db.query(models.Edge).filter(models.Edge.network_id == new_network_id).all()
        )
        source_edge_map = {e.edge_id: e.id for e in source_edges}
        for new_edge in new_edges:
            old_pk = source_edge_map.get(new_edge.edge_id)
            if old_pk:
                edge_map[old_pk] = new_edge.id

    return edge_map


# --- Other Subgraph Generators ---


def create_ego_network(
    source_network_id: int,
    center_node_id: str,
    radius: int,
    db: Session,
    preserve_layout: bool = False,
    description: str = None,
) -> Dict[str, Any]:
    logger.info(f"Creating ego network for {center_node_id} (r={radius})")
    # Reconstruct graph structure to run ego_graph
    G = nx.Graph()

    edges = (
        db.query(models.Edge).filter(models.Edge.network_id == source_network_id).all()
    )
    nodes = (
        db.query(models.Node).filter(models.Node.network_id == source_network_id).all()
    )

    id_map = {n.id: n.node_id for n in nodes}

    for n in nodes:
        G.add_node(n.node_id)

    for e in edges:
        u = id_map.get(e.source_node_id)
        v = id_map.get(e.target_node_id)
        if u and v:
            G.add_edge(u, v)

    # Resolve node ID
    center_node_id = resolve_node_id(G, center_node_id)

    if center_node_id not in G:
        raise ValueError(f"Node {center_node_id} not found in network")

    ego_G = nx.ego_graph(G, center_node_id, radius=radius)
    node_ids = list(ego_G.nodes())

    if description is None:
        description = f"Ego Network of node '{center_node_id}' with radius {radius}."
    return create_subgraph_from_nodes(
        source_network_id,
        node_ids,
        db,
        suffix=f"Ego {center_node_id} (r={radius})",
        preserve_layout=preserve_layout,
        description=description,
    )


def create_path_subgraph(
    source_network_id: int,
    source_node_id: str,
    target_node_id: str,
    db: Session,
    preserve_layout: bool = False,
    description: str = None,
) -> Dict[str, Any]:
    logger.info(f"Creating path subgraph: {source_node_id} -> {target_node_id}")
    G = nx.Graph()
    edges = (
        db.query(models.Edge).filter(models.Edge.network_id == source_network_id).all()
    )
    nodes = (
        db.query(models.Node).filter(models.Node.network_id == source_network_id).all()
    )
    id_map = {n.id: n.node_id for n in nodes}
    for n in nodes:
        G.add_node(n.node_id)
    for e in edges:
        u = id_map.get(e.source_node_id)
        v = id_map.get(e.target_node_id)
        if u and v:
            G.add_edge(u, v)

    # Resolve node IDs
    source_node_id = resolve_node_id(G, source_node_id)
    target_node_id = resolve_node_id(G, target_node_id)

    try:
        path_nodes = nx.shortest_path(G, source=source_node_id, target=target_node_id)
    except nx.NetworkXNoPath:
        logger.warning(f"No path found between {source_node_id} and {target_node_id}")
        raise ValueError(f"No path between {source_node_id} and {target_node_id}")

    if description is None:
        description = f"Shortest path from '{source_node_id}' to '{target_node_id}'."
    return create_subgraph_from_nodes(
        source_network_id,
        path_nodes,
        db,
        suffix=f"Path {source_node_id}->{target_node_id}",
        preserve_layout=preserve_layout,
        description=description,
    )


def create_k_core_subgraph(
    source_network_id: int,
    k: int,
    db: Session,
    preserve_layout: bool = False,
    description: str = None,
) -> Dict[str, Any]:
    logger.info(f"Creating k-core subgraph (k={k})")
    G = nx.Graph()
    edges = (
        db.query(models.Edge).filter(models.Edge.network_id == source_network_id).all()
    )
    nodes = (
        db.query(models.Node).filter(models.Node.network_id == source_network_id).all()
    )
    id_map = {n.id: n.node_id for n in nodes}
    for n in nodes:
        G.add_node(n.node_id)
    for e in edges:
        u = id_map.get(e.source_node_id)
        v = id_map.get(e.target_node_id)
        if u and v:
            G.add_edge(u, v)

    # Remove self-loops as k-core is defined for simple graphs usually
    G.remove_edges_from(nx.selfloop_edges(G))

    k_core_G = nx.k_core(G, k=k)
    node_ids = list(k_core_G.nodes())

    if not node_ids:
        logger.warning(f"No k-core found for k={k}")
        raise ValueError(f"No k-core found for k={k}")

    if description is None:
        description = f"k-Core subgraph with k={k}."
    return create_subgraph_from_nodes(
        source_network_id,
        node_ids,
        db,
        suffix=f"K-Core (k={k})",
        preserve_layout=preserve_layout,
        description=description,
    )


def create_largest_component_subgraph(
    source_network_id: int,
    db: Session,
    preserve_layout: bool = False,
    description: str = None,
) -> Dict[str, Any]:
    logger.info("Creating largest component subgraph")
    G = nx.Graph()
    edges = (
        db.query(models.Edge).filter(models.Edge.network_id == source_network_id).all()
    )
    nodes = (
        db.query(models.Node).filter(models.Node.network_id == source_network_id).all()
    )
    id_map = {n.id: n.node_id for n in nodes}
    for n in nodes:
        G.add_node(n.node_id)
    for e in edges:
        u = id_map.get(e.source_node_id)
        v = id_map.get(e.target_node_id)
        if u and v:
            G.add_edge(u, v)

    components = list(nx.connected_components(G))
    if not components:
        raise ValueError("Network is empty")

    largest_component = max(components, key=len)
    node_ids = list(largest_component)

    if description is None:
        description = "Largest connected component of the network."
    return create_subgraph_from_nodes(
        source_network_id,
        node_ids,
        db,
        suffix="Largest Component",
        preserve_layout=preserve_layout,
        description=description,
    )


def create_component_containing_node(
    source_network_id: int,
    node_id: str,
    db: Session,
    preserve_layout: bool = False,
    description: str = None,
) -> Dict[str, Any]:
    logger.info(f"Creating component subgraph containing node {node_id}")
    G = nx.Graph()
    edges = (
        db.query(models.Edge).filter(models.Edge.network_id == source_network_id).all()
    )
    nodes = (
        db.query(models.Node).filter(models.Node.network_id == source_network_id).all()
    )
    id_map = {n.id: n.node_id for n in nodes}
    for n in nodes:
        G.add_node(n.node_id)
    for e in edges:
        u = id_map.get(e.source_node_id)
        v = id_map.get(e.target_node_id)
        if u and v:
            G.add_edge(u, v)

    # Resolve node ID
    node_id = resolve_node_id(G, node_id)

    if node_id not in G:
        logger.warning(f"Node {node_id} not found in network {source_network_id}")
        raise ValueError(f"Node {node_id} not found in network")

    component_nodes = nx.node_connected_component(G, node_id)
    node_ids = list(component_nodes)

    if description is None:
        description = f"Connected component containing node '{node_id}'."
    return create_subgraph_from_nodes(
        source_network_id,
        node_ids,
        db,
        suffix=f"Component ({node_id})",
        preserve_layout=preserve_layout,
        description=description,
    )
